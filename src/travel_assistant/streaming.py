"""Render agent stream events (stream_mode='updates') as concise CLI lines."""
from typing import Any


def format_stream_event(event: Any) -> list[str]:
    """Best-effort, never-raising formatting of one updates event.

    updates events are dicts: {node_name: state_delta}. We surface the node
    and any tool/message hints. Unknown shapes degrade to a compact repr.
    """
    lines: list[str] = []
    if not isinstance(event, dict):
        return [f"· {event!r}"]
    for node, delta in event.items():
        lines.append(f"· {node}")
        if isinstance(delta, dict):
            msgs = delta.get("messages")
            if isinstance(msgs, list):
                for m in msgs:
                    name = type(m).__name__
                    tc = getattr(m, "tool_calls", None)
                    if tc:
                        for call in tc:
                            cn = call.get("name") if isinstance(call, dict) else None
                            lines.append(f"    → tool call: {cn}")
                    else:
                        content = getattr(m, "content", "")
                        snippet = str(content).strip().replace("\n", " ")[:80]
                        if snippet:
                            lines.append(f"    {name}: {snippet}")
    return lines
