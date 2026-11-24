"""
backend/utils/code_agent_with_tools.py

Agentic code fixer that uses LangGraph's create_react_agent (the modern
replacement for the deprecated AgentExecutor + create_tool_calling_agent).

The agent reads project files before writing — eliminating hallucinations.
Provides both sync and async streaming execution paths.
"""

import os
import re
import logging
import threading
from typing import Any, Dict, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from llm_router import get_coding_llm
from utils.streaming_callback import StreamingCallbackHandler
from utils.langchain_tools import ALL_TOOLS  # read_file, write_file, list_directory

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are a senior software engineer executing a SURGICAL code change task.

You have access to filesystem tools: read_file, list_directory, search_codebase, replace_in_file.

WORKFLOW:
1. ALWAYS read the target file first with read_file before making any edits.
2. Read any related files if needed (imports, shared components, config).
3. Identify the EXACT lines to change. Do NOT regenerate the whole file.
4. Use replace_in_file to apply the surgical change. This is the ONLY edit tool available.
5. Confirm ONLY what you changed and why.

CRITICAL INSTRUCTIONS FOR SURGICAL FIXES:
- You MUST use replace_in_file for ALL edits. write_file does NOT exist. Do not attempt to use it.
- PREFER THE replace_in_file TOOL. Find the specific block of code that is broken, and use replace_in_file to swap it out.
- You are performing a SURGICAL FIX. You are STRICTLY FORBIDDEN from modifying unrelated logic, BUT you MUST update surrounding layout or structural classes (like grid columns or flex containers) if they need to be adjusted to gracefully accommodate your requested change.
- PRESERVE ALL EXISTING FORMATTING. Do not drop hyphens, change quotes, alter indentations, or reformat code in the rest of the file.
- Double-check your output against the original file provided. Collateral damage to unrelated code is considered a critical system failure.
- Do NOT hallucinate file contents — always read first.
- Do NOT remove comments, tests, or unrelated logic.
- If a file doesn't exist, say so and stop — never invent a path.
"""


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

# (prompt is now a method on the class — see create_prompt below)


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class CodeAgentWithTools:
    """
    Agentic code fixer powered by LangGraph's create_react_agent.

    Provides:
      - fix_with_context()           — synchronous single-shot execution
      - fix_with_context_streaming() — async streaming via astream_events()
    """

    # ------------------------------------------------------------------
    # Safeguard limits (equivalent to AgentExecutor.max_iterations /
    # max_execution_time).  Adjust here to tune quota vs. thoroughness.
    # ------------------------------------------------------------------
    MAX_ITERATIONS     = 5   # LangGraph recursion_limit: max tool-call round-trips
    MAX_EXECUTION_TIME = 45  # Wall-clock seconds before thread is abandoned

    def __init__(self) -> None:
        self.model = get_coding_llm(temperature=0.0)

        # Build the LangGraph react agent (replaces AgentExecutor)
        self._agent = create_react_agent(
            model=self.model,
            tools=ALL_TOOLS,
            prompt=_SYSTEM_PROMPT,
        )

        logger.info(
            f"[CodeAgentWithTools] Initialized with {getattr(self.model, 'model', 'llm')} + langgraph "
            f"(max_iterations={self.MAX_ITERATIONS}, timeout={self.MAX_EXECUTION_TIME}s)"
        )

    # ------------------------------------------------------------------
    # Prompt builder
    # ------------------------------------------------------------------

    def create_prompt(
        self,
        bug_description: str,
        target_file_path: str,
        build_plan: Optional[str] = None,
    ) -> str:
        plan_section = f"Plan: {build_plan}" if build_plan else ""
        return f"""Fix this bug: {bug_description}

File: {target_file_path}
{plan_section}

INSTRUCTIONS:
1. Read the file with read_file
2. Find the EXACT text to replace
3. Use replace_in_file with exact old/new text
4. Be precise - match exact whitespace and formatting

Tools available:
- read_file(path)
- replace_in_file(path, old_text, new_text)

DO NOT regenerate entire files. Only replace what needs changing.
"""


    def fix_with_context(
        self,
        bug_description: str,
        target_file_path: str,
        build_plan: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Synchronous agent run with hard limits:
          - recursion_limit  : caps the number of LangGraph node iterations
                               (≈ max tool-call round-trips).
          - MAX_EXECUTION_TIME: kills the agent thread if it hangs past the
                               wall-clock deadline (equivalent to
                               AgentExecutor.max_execution_time).
        """
        prompt = self.create_prompt(bug_description, target_file_path, build_plan)

        # Container for thread result / exception
        outcome: Dict[str, Any] = {}
        exc_holder: list = []

        def _invoke() -> None:
            try:
                result = self._agent.invoke(
                    {"messages": [HumanMessage(content=prompt)]},
                    config={"recursion_limit": self.MAX_ITERATIONS},  # ← hard iteration cap
                )

                final_output = ""
                if "messages" in result and result["messages"]:
                    raw_content = result["messages"][-1].content
                    if isinstance(raw_content, list):
                        final_output = "".join([p.get("text", "") if isinstance(p, dict) else str(p) for p in raw_content])
                    else:
                        final_output = str(raw_content) if raw_content else str(result["messages"][-1])

                logger.info(
                    f"[CodeAgentWithTools] fix_with_context complete. "
                    f"Output length: {len(final_output)}"
                )
                outcome["result"] = {"success": True, "output": final_output, "error": None}
            except Exception as exc:
                exc_holder.append(exc)

        worker = threading.Thread(target=_invoke, daemon=True)
        worker.start()
        worker.join(timeout=self.MAX_EXECUTION_TIME)  # ← wall-clock timeout

        if worker.is_alive():
            # Thread is still running → timed out
            logger.error(
                f"[CodeAgentWithTools] ⏱ Agent timed out after {self.MAX_EXECUTION_TIME}s "
                f"— aborting tool-based attempt."
            )
            return {"success": False, "output": "", "error": f"Agent timed out after {self.MAX_EXECUTION_TIME}s"}

        if exc_holder:
            err = exc_holder[0]
            logger.error(f"[CodeAgentWithTools] fix_with_context error: {err}")
            return {"success": False, "output": "", "error": str(err)}

        return outcome.get("result", {"success": False, "output": "", "error": "No result captured"})

    # ------------------------------------------------------------------
    # Fallback execution (direct LLM when tools malfunction)
    # ------------------------------------------------------------------

    def fix_with_fallback(
        self,
        bug_description: str,
        target_file_path: str,
        build_plan: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Attempt tool-based fix first. If the agent fails to call write_file
        (e.g., MALFORMED_FUNCTION_CALL), fall back to asking Gemini to generate
        the fixed code directly and write it ourselves.
        """
        logger.info(f"[CodeAgentWithTools] 🔧 Attempting tool-based fix for {target_file_path}")

        # ── Attempt 1: ReAct agent with tools ────────────────────────────
        try:
            result = self.fix_with_context(bug_description, target_file_path, build_plan)
            out_str = str(result.get("output", ""))

            if result.get("success") and any(phrase in out_str for phrase in ["Successfully wrote", "Successfully replaced", "✅"]):
                logger.info("[CodeAgentWithTools] ✅ Tool-based fix succeeded")
                return {"success": True, "method": "tools", "output": out_str, "error": None}

            logger.warning(
                "[CodeAgentWithTools] ⚠️ Agent ran but write_file / replace_in_file was not confirmed. "
                f"Output: {out_str[:200]}"
            )
        except Exception as exc:
            logger.warning(f"[CodeAgentWithTools] ⚠️ Tool-based fix raised: {exc}")

        # ── Attempt 2: Direct LLM generation fallback ─────────────────────
        logger.info("[CodeAgentWithTools] 🔄 Falling back to direct code generation")
        try:
            repo_path = os.getenv("REPO_PATH", ".")
            file_full_path = os.path.join(repo_path, target_file_path)

            with open(file_full_path, "r", encoding="utf-8") as fh:
                current_content = fh.read()

            direct_prompt = (
                f"You are a senior software engineer performing a SURGICAL code fix.\n\n"
                f"TASK: {bug_description}\n\n"
                f"CURRENT FILE ({target_file_path}):\n"
                f"```\n{current_content}\n```\n\n"
                f"CRITICAL INSTRUCTIONS FOR SURGICAL FIXES:\n"
                f"- You are performing a SURGICAL FIX. You must return the entire file content, but you are STRICTLY FORBIDDEN from modifying any lines of code, CSS classes, variables, or logic that are not directly related to the requested bug fix.\n"
                f"- PRESERVE ALL EXISTING FORMATTING. Do not drop hyphens, change quotes, alter indentations, or reformat code in the rest of the file. (e.g., If a Tailwind class is `grid-cols-1`, it MUST remain exactly `grid-cols-1`).\n"
                f"- Double-check your output against the original file provided. Collateral damage to unrelated code is considered a critical system failure. Return ONLY the raw code, with no markdown code block wrappers."
            )
            if build_plan:
                direct_prompt += f"\n\nBUILD PLAN (for context only — do not deviate from SURGICAL RULES):\n{build_plan}"

            # Call LLM without tools — plain generation using self.model
            response = self.model.invoke([HumanMessage(content=direct_prompt)])
            if isinstance(response.content, list):
                raw_output = "".join([p.get("text", "") if isinstance(p, dict) else str(p) for p in response.content])
            else:
                raw_output = str(response.content)

            # Extract the code block from the response
            import re
            code_match = re.search(r"```(?:\w+)?\n([\s\S]*?)```", raw_output)
            if not code_match:
                # No fenced block — treat the whole response as code
                new_content = raw_output.strip()
            else:
                new_content = code_match.group(1).strip()

            if not new_content.strip():
                return {
                    "success": False,
                    "method": "direct",
                    "output": "",
                    "error": "Direct generation returned empty content",
                }

            # Write the file ourselves
            with open(file_full_path, "w", encoding="utf-8") as fh:
                fh.write(new_content)

            byte_count = len(new_content.encode("utf-8"))
            logger.info(
                f"[CodeAgentWithTools] ✅ Direct fallback wrote {byte_count:,} bytes "
                f"to {target_file_path!r}"
            )
            return {
                "success": True,
                "method": "direct",
                "output": f"✅ Successfully wrote {len(new_content):,} chars ({byte_count:,} bytes) to '{target_file_path}'",
                "error": None,
            }

        except Exception as exc:
            logger.error(f"[CodeAgentWithTools] ❌ Direct fallback error: {exc}")
            return {"success": False, "method": "direct", "output": "", "error": str(exc)}

    # ------------------------------------------------------------------
    # Async streaming execution
    # ------------------------------------------------------------------

    async def fix_with_context_streaming(
        self,
        bug_description: str,
        target_file_path: str,
        build_plan: Optional[str],
        callback_handler: StreamingCallbackHandler,
    ) -> Dict[str, Any]:
        """
        Async agent run that streams every lifecycle event through the provided
        callback_handler into its asyncio.Queue, enabling SSE real-time delivery.

        IMPORTANT: This method is async — callers must await it.
        """
        prompt = self.create_prompt(bug_description, target_file_path, build_plan)
        final_output = ""

        try:
            async for event in self._agent.astream_events(
                {"messages": [HumanMessage(content=prompt)]},
                version="v2",
                config={"callbacks": [callback_handler]},
            ):
                kind = event.get("event", "")

                # Capture final answer
                if kind == "on_chain_end":
                    data = event.get("data", {})
                    output_val = data.get("output", {})
                    if isinstance(output_val, dict):
                        msgs = output_val.get("messages", [])
                        if msgs:
                            raw_c = msgs[-1].content
                            if isinstance(raw_c, list):
                                final_output = "".join([p.get("text", "") if isinstance(p, dict) else str(p) for p in raw_c])
                            else:
                                final_output = str(raw_c)
                    elif isinstance(output_val, list):
                        final_output = "".join([p.get("text", "") if isinstance(p, dict) else str(p) for p in output_val])
                    elif isinstance(output_val, str):
                        final_output = output_val

                # Stream individual tokens to the queue
                elif kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        await callback_handler.queue.put(
                            {"type": "token", "data": chunk.content}
                        )

            logger.info("[CodeAgentWithTools] fix_with_context_streaming complete")
            return {"success": True, "output": final_output, "error": None}

        except Exception as exc:
            logger.error(f"[CodeAgentWithTools] fix_with_context_streaming error: {exc}")
            try:
                await callback_handler.queue.put(
                    {"type": "error", "message": f"❌ Agent execution failed: {exc}"}
                )
                await callback_handler.queue.put(
                    {"type": "done", "message": "Stream closed due to error."}
                )
            except Exception:
                pass
            return {"success": False, "output": "", "error": str(exc)}
