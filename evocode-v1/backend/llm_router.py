"""
backend/llm_router.py

Multi-Provider Free Failover LLM Router for EvoCode V2.
- Primary: Gemini (gemini-2.5-flash or gemini-3.8-flash via ChatGoogleGenerativeAI)
- Fast Triage: Groq (llama-3.1-8b-instant) if GROQ_API_KEY is configured
- Failover: OpenRouter (:free) if OPENROUTER_API_KEY is configured
- Exponential backoff with jitter on 429 / ResourceExhausted (1s, 2s, max 2 retries)
- Security: Never logs API keys.
"""

import os
import time
import json
import logging
from typing import Optional, List, Any
from dotenv import load_dotenv

from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage

# Google Generative AI
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    import google.api_core.exceptions as google_exceptions
except ImportError:
    ChatGoogleGenerativeAI = None
    google_exceptions = None

# Groq (optional fast triage)
try:
    from langchain_groq import ChatGroq
except ImportError:
    ChatGroq = None

# OpenRouter / OpenAI compatible (optional free failover)
try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None

load_dotenv()
logger = logging.getLogger("llm_router")


def get_coding_llm(temperature: float = 0.0) -> Any:
    """
    Returns the primary LangChain chat model used by the CodeAgent.
    Uses GEMINI_PRIMARY_MODEL (defaulting to gemini-2.5-flash).
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing from environment / .env")

    model_name = os.getenv("GEMINI_PRIMARY_MODEL", "gemini-3.5-flash")

    if not ChatGoogleGenerativeAI:
        raise RuntimeError("langchain-google-genai package is not installed")

    return ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=temperature,
        max_output_tokens=8192,
        convert_system_message_to_human=True,
        safety_settings={
            "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
            "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
            "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
            "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
        },
    )


def get_triage_llm(temperature: float = 0.0) -> Any:
    """
    Returns a fast model for low-latency triage (comment deduplication, clustering, vagueness check).
    Prefers Groq (llama-3.1-8b-instant) if GROQ_API_KEY is set.
    Otherwise falls back to Gemini Lite / Primary.
    """
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key and ChatGroq:
        logger.info("[llm_router] Using Groq llama-3.1-8b-instant for fast triage")
        return ChatGroq(
            model_name="llama-3.1-8b-instant",
            groq_api_key=groq_key,
            temperature=temperature,
            max_tokens=1024,
        )

    # Fallback to Gemini Lite or Primary
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing from environment / .env")

    model_name = os.getenv("GEMINI_LITE_MODEL", os.getenv("GEMINI_PRIMARY_MODEL", "gemini-3.5-flash"))
    logger.info(f"[llm_router] Using Gemini ({model_name}) for triage")
    return ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=temperature,
        max_output_tokens=2048,
        convert_system_message_to_human=True,
    )


def _get_openrouter_llm(temperature: float = 0.0) -> Optional[Any]:
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if not openrouter_key or not ChatOpenAI:
        return None
    return ChatOpenAI(
        model_name="meta-llama/llama-3.1-8b-instruct:free",
        openai_api_key=openrouter_key,
        openai_api_base="https://openrouter.ai/api/v1",
        temperature=temperature,
        max_tokens=2048,
    )


def is_daily_quota_exhausted(err: Exception) -> bool:
    """Checks whether error is a hard daily quota exhaustion."""
    err_str = str(err).lower()
    return "per day" in err_str or "daily" in err_str or "requests per day" in err_str or "quotafailure" in err_str


def is_rate_limit_error(err: Exception) -> bool:
    """Checks whether the exception is an HTTP 429 or ResourceExhausted rate limit."""
    err_str = str(err).lower()
    if "429" in err_str or "resourceexhausted" in err_str or "quota" in err_str or "rate limit" in err_str:
        return True
    if google_exceptions and isinstance(err, google_exceptions.ResourceExhausted):
        return True
    return False


def call_with_fallback(
    prompt: str,
    system_prompt: Optional[str] = None,
    purpose: str = "triage",
    temperature: float = 0.0,
    max_retries: int = 2,
) -> str:
    """
    Executes an LLM call across configured providers with automatic exponential backoff
    on 429/ResourceExhausted, falling over to secondary/tertiary providers.
    Never logs any API keys.
    """
    messages: List[BaseMessage] = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=prompt))

    # Build provider sequence based on purpose
    providers = []
    if purpose == "triage":
        if os.getenv("GROQ_API_KEY") and ChatGroq:
            providers.append(("Groq (llama-3.1-8b)", lambda: get_triage_llm(temperature)))
        providers.append(("Gemini Triage", lambda: get_triage_llm(temperature)))
        providers.append(("Gemini Primary Fallback", lambda: get_coding_llm(temperature)))
        if os.getenv("OPENROUTER_API_KEY") and ChatOpenAI:
            providers.append(("OpenRouter", lambda: _get_openrouter_llm(temperature)))
    else:
        providers.append(("Gemini Primary", lambda: get_coding_llm(temperature)))
        if os.getenv("GROQ_API_KEY") and ChatGroq:
            providers.append(("Groq", lambda: get_triage_llm(temperature)))
        if os.getenv("OPENROUTER_API_KEY") and ChatOpenAI:
            providers.append(("OpenRouter", lambda: _get_openrouter_llm(temperature)))

    last_error: Optional[Exception] = None

    for provider_name, get_model_fn in providers:
        try:
            model = get_model_fn()
            if model is None:
                continue

            # Retry loop for transient 429 rate spikes on this provider
            backoff = 1.0
            for attempt in range(max_retries + 1):
                try:
                    logger.debug(f"[llm_router] Calling {provider_name} (attempt {attempt + 1})")
                    resp = model.invoke(messages)
                    content = resp.content if hasattr(resp, "content") else str(resp)
                    if isinstance(content, list):
                        # Handle content blocks
                        text_parts = [p.get("text", "") if isinstance(p, dict) else str(p) for p in content]
                        return "".join(text_parts).strip()
                    return str(content).strip()
                except Exception as e:
                    if is_daily_quota_exhausted(e):
                        logger.warning(f"[llm_router] Daily quota exhausted on {provider_name}. Immediately falling over to next provider.")
                        raise e
                    elif is_rate_limit_error(e) and attempt < max_retries:
                        logger.warning(
                            f"[llm_router] Rate limit (429) hit on {provider_name}. "
                            f"Backing off {backoff:.1f}s before retry..."
                        )
                        time.sleep(backoff)
                        backoff *= 2.0
                    else:
                        raise e

        except Exception as e:
            last_error = e
            logger.warning(f"[llm_router] Provider {provider_name} failed: {type(e).__name__}. Trying next fallback...")
            continue

    # If all providers fail
    logger.error(f"[llm_router] All LLM providers exhausted. Last error: {last_error}")
    raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")
