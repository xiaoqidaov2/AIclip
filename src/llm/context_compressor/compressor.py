from __future__ import annotations

import logging
from typing import Any, Callable, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------

_encoder_cache: Any = None


def _get_encoder():
    """Return a tiktoken encoder, or None if unavailable (cached)."""
    global _encoder_cache  # noqa: PLW0603
    if _encoder_cache is None:
        try:
            import tiktoken

            try:
                _encoder_cache = tiktoken.encoding_for_model("gpt-4o-mini")
            except KeyError:
                _encoder_cache = tiktoken.get_encoding("cl100k_base")
        except Exception:
            _encoder_cache = False  # sentinel
    return _encoder_cache if _encoder_cache is not False else None


def _count_tokens(text: str) -> int:
    """Token count via tiktoken if available, else character estimation."""
    if not text:
        return 0
    enc = _get_encoder()
    if enc is not None:
        try:
            return len(enc.encode(text))
        except Exception:
            pass
    # Fallback: ~4 chars / token for ASCII, ~2 for CJK
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    non_ascii = len(text) - ascii_chars
    return (ascii_chars // 4) + (non_ascii // 2) + 1


def _message_tokens(msg: Any) -> int:
    """Estimate token count for a single LangChain message."""
    overhead = 5  # role markers and formatting overhead
    if isinstance(msg, HumanMessage):
        return overhead + _count_tokens(str(msg.content or ""))
    if isinstance(msg, AIMessage):
        total = overhead + _count_tokens(str(msg.content or ""))
        for tc in getattr(msg, "tool_calls", None) or []:
            if isinstance(tc, dict):
                total += _count_tokens(str(tc.get("name", "")))
                total += _count_tokens(str(tc.get("args", "") or tc.get("arguments", "")))
        return total
    if isinstance(msg, (ToolMessage, SystemMessage)):
        return overhead + _count_tokens(str(msg.content or ""))
    return overhead + _count_tokens(str(msg))


def estimate_tokens(messages: List[Any]) -> int:
    """Estimate total tokens for a list of messages."""
    return sum(_message_tokens(m) for m in messages)


# ---------------------------------------------------------------------------
# Summarization helpers
# ---------------------------------------------------------------------------

def _truncated(text: str, limit: int = 300) -> str:
    if not text:
        return ""
    s = str(text).strip()
    if len(s) <= limit:
        return s
    return s[:limit].rstrip() + "..."


def _format_for_summary(messages: List[Any]) -> str:
    """Format a batch of messages into readable text for the summarizer LLM."""
    lines: List[str] = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            lines.append(f"[User]\n{msg.content}")
        elif isinstance(msg, AIMessage):
            blocks: List[str] = []
            for tc in getattr(msg, "tool_calls", None) or []:
                if isinstance(tc, dict):
                    args = str(tc.get("args", "") or tc.get("arguments", ""))
                    blocks.append(f"  → tool_call: {tc.get('name', '?')}({_truncated(args, 200)})")
            if msg.content:
                blocks.append(f"  response: {_truncated(str(msg.content), 400)}")
            if blocks:
                lines.append("[Agent]\n" + "\n".join(blocks))
        elif isinstance(msg, ToolMessage):
            lines.append(f"[Tool: {getattr(msg, 'name', '?')}]\n{_truncated(str(msg.content or ''), 200)}")
        elif isinstance(msg, SystemMessage):
            content = str(msg.content or "")
            if len(content) > 200:
                lines.append(f"[Context]\n{_truncated(content, 200)}")
    return "\n\n".join(lines)


_SUMMARY_SYSTEM_PROMPT = (
    "You are a conversation history summarizer for an AI video editing assistant. "
    "Summarize the following conversation turns concisely. Preserve:\n"
    "1. What the user requested\n"
    "2. What actions the agent took (tools called and why)\n"
    "3. Key results and state changes (project paths, render outputs)\n"
    "4. Any decisions or preferences expressed\n\n"
    "Use the same language as the conversation. Be specific about file paths and tool names. "
    "Keep the summary under 3000 characters."
)


# ---------------------------------------------------------------------------
# ContextCompressor
# ---------------------------------------------------------------------------

class ContextCompressor:
    """Compress conversation history to stay within token limits.

    Parameters
    ----------
    llm_factory : callable, optional
        Zero-arg callable that returns a chat LLM used for summarization.
        If ``None``, a purely extractive fallback is used.
    soft_limit : int
        Token count at which compression activates (default ``70000``).
    hard_limit : int
        Token count for aggressive compression (default ``90000``).
    target_ratio : float
        Fraction of current tokens to aim for after compression (default ``0.45``).
    min_messages : int
        Minimum history length before compression is attempted (default ``8``).
    keep_last : int
        Minimum number of most-recent messages *never* compressed (default ``8``).
    """

    def __init__(
        self,
        llm_factory: Optional[Callable[[], Any]] = None,
        soft_limit: int = 70000,
        hard_limit: int = 90000,
        target_ratio: float = 0.45,
        min_messages: int = 8,
        keep_last: int = 8,
    ) -> None:
        self.llm_factory = llm_factory
        self.soft_limit = soft_limit
        self.hard_limit = hard_limit
        self.target_ratio = target_ratio
        self.min_messages = min_messages
        self.keep_last = keep_last
        self.total_compressed = 0
        self._stats: dict = {"runs": 0, "compressions": 0, "freed_tokens": 0}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compress(self, history: List[Any]) -> bool:
        """Compress *history* in-place if token usage exceeds limits.

        Returns ``True`` when messages were replaced with a summary.
        """
        self._stats["runs"] += 1

        if len(history) < self.min_messages:
            return False

        total = estimate_tokens(history)
        if total < self.soft_limit:
            return False

        # --- pick a target --------------------------------------------
        if total > self.hard_limit:
            target = int(total * 0.35)  # free 65%
        else:
            target = int(total * self.target_ratio)

        target = max(target, 25000)
        need_to_free = total - target

        # --- select oldest compressible messages ----------------------
        keep = max(self.keep_last, int(len(history) * 0.3))
        compressible = history[:-keep] if len(history) > keep else []

        to_compress: List[Any] = []
        freed = 0
        for msg in compressible:
            if freed >= need_to_free and len(to_compress) >= 2:
                break
            to_compress.append(msg)
            freed += _message_tokens(msg)

        if len(to_compress) < 2:
            return False

        # --- summarise ------------------------------------------------
        summary = self._summarize(to_compress)

        # --- replace in-place -----------------------------------------
        summary_msg = SystemMessage(content=f"[Compressed Conversation History]\n{summary}")
        idx = len(to_compress)
        history[:idx] = [summary_msg]

        after = estimate_tokens(history)
        self.total_compressed += freed
        self._stats["compressions"] += 1
        self._stats["freed_tokens"] += freed

        logger.info(
            "Context compressed: freed ~%d tokens (%d → %d), %d messages → %d",
            freed,
            total,
            after,
            idx,
            len(history),
        )
        return True

    @property
    def stats(self) -> dict:
        """Read-only snapshot of compression statistics."""
        return dict(self._stats)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _summarize(self, messages: List[Any]) -> str:
        """LLM summarization with fallback to extractive truncation."""
        if self.llm_factory is not None:
            text = _format_for_summary(messages)
            if len(text) > 800:  # only worth an LLM call
                try:
                    llm = self.llm_factory()
                    if llm is not None:
                        resp = llm.invoke([
                            SystemMessage(content=_SUMMARY_SYSTEM_PROMPT),
                            HumanMessage(content=text),
                        ])
                        content = getattr(resp, "content", resp)
                        if isinstance(content, str) and len(content.strip()) > 20:
                            return content.strip()
                except Exception as exc:
                    logger.warning("LLM summarization failed, using fallback: %s", exc)

        return self._fallback_summary(messages)

    @staticmethod
    def _fallback_summary(messages: List[Any]) -> str:
        """Extractive summary — no LLM call needed."""
        parts: List[str] = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                parts.append(f"User asked: {_truncated(str(msg.content), 240)}")
            elif isinstance(msg, AIMessage) and msg.content:
                parts.append(f"Agent replied: {_truncated(str(msg.content), 240)}")
            elif isinstance(msg, ToolMessage):
                name = getattr(msg, "name", "tool")
                parts.append(f"[{name}]: {_truncated(str(msg.content or ''), 120)}")
        return "\n".join(parts)
