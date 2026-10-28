"""System prompt and conversion of stored messages into chat completion requests."""

from collections.abc import Sequence
from typing import Any

from app.models import ChatMessage, MessageRole

SYSTEM_PROMPT = """\
You are a software engineering agent taking part in a bug hunting benchmark.

When the user asks you to run a bug hunt, call start_bug_hunt with the matching slug. \
If you are unsure which bug hunts exist, call list_bug_hunts first.

During a bug hunt:
- Inspect the project with list_files, read_file and search_code. You cannot run code.
- Report each defect separately with report_bug. Give the line number where the defect is, \
a short explanation, the exact original code copied from the file without line numbers, \
and the corrected code that should replace it. Keep the original snippet as small as possible \
while still being unique.
- Only report genuine defects. Incorrect reports reduce the score.
- When you have reviewed the whole project, call finish_bug_hunt with a short summary.

Outside a bug hunt, answer the user's questions normally."""


def build_conversation(messages: Sequence[ChatMessage]) -> list[dict[str, Any]]:
    """Convert stored messages into the OpenAI chat format.

    Tool calls without a recorded result, which can occur if a turn was interrupted, are
    omitted so the conversation remains valid.
    """
    answered = {message.tool_call_id for message in messages if message.role is MessageRole.TOOL}
    conversation: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]

    for message in messages:
        if message.role is MessageRole.USER:
            conversation.append({"role": "user", "content": message.content or ""})
        elif message.role is MessageRole.ASSISTANT:
            entry: dict[str, Any] = {"role": "assistant", "content": message.content or ""}
            calls = [call for call in message.tool_calls or [] if call["id"] in answered]
            if calls:
                entry["tool_calls"] = [
                    {
                        "id": call["id"],
                        "type": "function",
                        "function": {"name": call["name"], "arguments": call["arguments"]},
                    }
                    for call in calls
                ]
            conversation.append(entry)
        elif message.role is MessageRole.TOOL:
            conversation.append(
                {
                    "role": "tool",
                    "tool_call_id": message.tool_call_id,
                    "content": message.content or "",
                }
            )
    return conversation
