import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from langchain_core.callbacks.base import AsyncCallbackHandler
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)


def _timestamp() -> str:
    """Return a compact ISO-style timestamp for log messages."""
    return datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]


class StreamingCallbackHandler(AsyncCallbackHandler):
    """
    Intercepts every LangChain agent lifecycle event and streams structured
    messages to an asyncio.Queue so they can be forwarded to an SSE endpoint
    in real time.

    Usage:
        queue = asyncio.Queue()
        handler = StreamingCallbackHandler(queue)
        agent_executor.invoke(..., config={"callbacks": [handler]})
    """

    def __init__(self, queue: asyncio.Queue) -> None:
        super().__init__()
        self.queue = queue
        self._active_tool: Optional[str] = None
        self._llm_token_buffer: List[str] = []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _emit(self, payload: Dict[str, Any]) -> None:
        """Safely put a payload onto the queue without blocking the event loop."""
        try:
            payload.setdefault("timestamp", _timestamp())
            await self.queue.put(payload)
        except Exception as exc:
            logger.warning(f"[StreamingCallback] Failed to emit payload: {exc}")

    @staticmethod
    def _truncate(text: str, limit: int = 200) -> str:
        """Truncate long strings and append an ellipsis."""
        text = str(text)
        return text[:limit] + "…" if len(text) > limit else text

    # ------------------------------------------------------------------
    # LLM events
    # ------------------------------------------------------------------

    async def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        **kwargs: Any,
    ) -> None:
        """Called when the LLM begins generating a response."""
        try:
            model_name = (
                serialized.get("kwargs", {}).get("model_name")
                or serialized.get("name", "LLM")
            )
            message = f"🤖 AI is thinking... (model: {model_name})"
            logger.info(f"[{_timestamp()}] on_llm_start — {model_name}")
            await self._emit({"type": "llm_start", "message": message})
        except Exception as exc:
            logger.warning(f"[StreamingCallback] on_llm_start error: {exc}")

    async def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """Called for each streamed token — enables real-time code display."""
        try:
            self._llm_token_buffer.append(token)
            await self._emit({"type": "token", "data": token})
        except Exception as exc:
            logger.warning(f"[StreamingCallback] on_llm_new_token error: {exc}")

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Called when the LLM finishes generating."""
        try:
            buffered = "".join(self._llm_token_buffer)
            self._llm_token_buffer.clear()
            preview = self._truncate(buffered, 120) if buffered else "(streamed)"
            message = f"💡 LLM generation complete. Output preview: {preview}"
            logger.info(f"[{_timestamp()}] on_llm_end")
            await self._emit({"type": "llm_end", "message": message})
        except Exception as exc:
            logger.warning(f"[StreamingCallback] on_llm_end error: {exc}")

    # ------------------------------------------------------------------
    # Tool events
    # ------------------------------------------------------------------

    async def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        **kwargs: Any,
    ) -> None:
        """Called when the agent decides to invoke a tool."""
        try:
            tool_name = (
                serialized.get("name")
                or serialized.get("id", ["unknown"])[-1]
                or "unknown_tool"
            )
            self._active_tool = tool_name

            message = f"🔍 Calling {tool_name}..."
            if input_str and len(input_str) <= 120:
                message += f" with input: {input_str}"

            logger.info(f"[{_timestamp()}] on_tool_start — {tool_name}")
            await self._emit(
                {
                    "type": "tool_start",
                    "tool": tool_name,
                    "message": message,
                }
            )
        except Exception as exc:
            logger.warning(f"[StreamingCallback] on_tool_start error: {exc}")

    async def on_tool_end(self, output: str, **kwargs: Any) -> None:
        """Called when a tool finishes executing."""
        try:
            truncated = self._truncate(output, 200)
            message = f"✅ Tool completed. Result: {truncated}"
            logger.info(f"[{_timestamp()}] on_tool_end — {self._active_tool}")
            self._active_tool = None
            await self._emit({"type": "tool_end", "message": message})
        except Exception as exc:
            logger.warning(f"[StreamingCallback] on_tool_end error: {exc}")

    async def on_tool_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        **kwargs: Any,
    ) -> None:
        """Called when a tool raises an exception."""
        try:
            message = f"❌ Tool error ({self._active_tool}): {self._truncate(str(error), 200)}"
            logger.error(f"[{_timestamp()}] on_tool_error — {error}")
            self._active_tool = None
            await self._emit({"type": "tool_error", "message": message})
        except Exception as exc:
            logger.warning(f"[StreamingCallback] on_tool_error error: {exc}")

    # ------------------------------------------------------------------
    # Chain events
    # ------------------------------------------------------------------

    async def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Called when an agent reasoning chain begins."""
        try:
            chain_name = serialized.get("name", "Chain")
            message = f"🧠 Starting reasoning chain... ({chain_name})"
            logger.info(f"[{_timestamp()}] on_chain_start — {chain_name}")
            await self._emit({"type": "chain_start", "message": message})
        except Exception as exc:
            logger.warning(f"[StreamingCallback] on_chain_start error: {exc}")

    async def on_chain_end(
        self,
        outputs: Dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Called when an agent reasoning chain finishes."""
        try:
            message = "✨ Reasoning complete"
            logger.info(f"[{_timestamp()}] on_chain_end")
            await self._emit({"type": "chain_end", "message": message})
        except Exception as exc:
            logger.warning(f"[StreamingCallback] on_chain_end error: {exc}")

    async def on_chain_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        **kwargs: Any,
    ) -> None:
        """Called when a chain raises an exception."""
        try:
            message = f"🔥 Chain error: {self._truncate(str(error), 200)}"
            logger.error(f"[{_timestamp()}] on_chain_error — {error}")
            await self._emit({"type": "chain_error", "message": message})
        except Exception as exc:
            logger.warning(f"[StreamingCallback] on_chain_error error: {exc}")

    # ------------------------------------------------------------------
    # Agent decision events
    # ------------------------------------------------------------------

    async def on_agent_action(
        self,
        action: AgentAction,
        **kwargs: Any,
    ) -> None:
        """Called when the agent commits to its next action."""
        try:
            tool_input_preview = self._truncate(str(action.tool_input), 120)
            message = f"💭 Agent decision: {action.tool} — {tool_input_preview}"
            logger.info(f"[{_timestamp()}] on_agent_action — tool={action.tool}")
            await self._emit(
                {
                    "type": "agent_action",
                    "tool": action.tool,
                    "tool_input": tool_input_preview,
                    "message": message,
                }
            )
        except Exception as exc:
            logger.warning(f"[StreamingCallback] on_agent_action error: {exc}")

    async def on_agent_finish(
        self,
        finish: AgentFinish,
        **kwargs: Any,
    ) -> None:
        """Called when the agent has produced its final answer."""
        try:
            output = finish.return_values.get("output", "")
            output_preview = self._truncate(output, 200)
            message = f"🎉 Agent execution complete. Summary: {output_preview}"
            logger.info(f"[{_timestamp()}] on_agent_finish")
            await self._emit(
                {
                    "type": "agent_finish",
                    "output": output_preview,
                    "message": message,
                }
            )
            # Signal SSE consumer that the stream is done
            await self._emit({"type": "done", "message": "Stream closed."})
        except Exception as exc:
            logger.warning(f"[StreamingCallback] on_agent_finish error: {exc}")
