"""Tools exposed to the model during a chat session."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BugFinding, BugHunt, BugHuntJob, ChatSession, Difficulty
from app.services.challenges import (
    Challenge,
    ChallengeCatalog,
    ChallengeNotFoundError,
    normalise_source_path,
)
from app.services.code_edits import ChangeNotApplicableError, locate_change
from app.services.jobs import close_job, find_active_job, start_job
from app.services.scoring import ScoringService

MAX_SEARCH_RESULTS = 100
DIFFICULTY_ORDER = {difficulty: index for index, difficulty in enumerate(Difficulty)}


class ToolError(Exception):
    """An error reported back to the model as the tool result."""


@dataclass
class ToolContext:
    db: Session
    chat_session: ChatSession
    catalog: ChallengeCatalog
    scoring: ScoringService
    output_limit: int

    def active_job(self) -> BugHuntJob | None:
        return find_active_job(self.db, self.chat_session.id)

    def require_job(self) -> tuple[BugHuntJob, Challenge]:
        job = self.active_job()
        if job is None:
            raise ToolError("No bug hunt is in progress. Call start_bug_hunt first.")
        return job, self.catalog.get(job.bug_hunt.slug)


ToolHandler = Callable[[ToolContext, dict[str, Any]], str]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def _object_schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required}


def _string_argument(arguments: dict[str, Any], name: str, *, required: bool = True) -> str:
    value = arguments.get(name)
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ToolError(f"Argument '{name}' must be a string.")
    if required and not value.strip():
        raise ToolError(f"Missing required argument '{name}'.")
    return value


def _integer_argument(arguments: dict[str, Any], name: str, default: int | None = None) -> int:
    value = arguments.get(name, default)
    if value is None:
        raise ToolError(f"Missing required argument '{name}'.")
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ToolError(f"Argument '{name}' must be an integer.") from None


def _list_bug_hunts(context: ToolContext, _arguments: dict[str, Any]) -> str:
    hunts = sorted(
        context.db.scalars(select(BugHunt).where(BugHunt.is_available)),
        key=lambda hunt: (DIFFICULTY_ORDER[hunt.difficulty], hunt.slug),
    )
    if not hunts:
        return "No bug hunts are available."
    return "\n".join(f"- {hunt.slug}: {hunt.title} ({hunt.difficulty})" for hunt in hunts)


def _start_bug_hunt(context: ToolContext, arguments: dict[str, Any]) -> str:
    slug = _string_argument(arguments, "slug").strip().lower()
    active = context.active_job()
    if active is not None:
        raise ToolError(
            f"Bug hunt '{active.bug_hunt.slug}' is already in progress. "
            "Call finish_bug_hunt before starting another."
        )
    try:
        challenge = context.catalog.get(slug)
    except ChallengeNotFoundError:
        raise ToolError(f"Unknown bug hunt '{slug}'. Call list_bug_hunts to see options.") from None

    bug_hunt = context.db.scalars(select(BugHunt).where(BugHunt.slug == challenge.slug)).one()
    job = start_job(context.db, context.chat_session, bug_hunt)
    context.db.commit()

    files = "\n".join(f"- {path}" for path in challenge.source_files())
    return (
        f"Bug hunt '{challenge.slug}' started as job {job.id}.\n\n"
        f"Project files:\n{files}\n\n"
        "Inspect the code, report each defect with report_bug, then call finish_bug_hunt."
    )


def _list_files(context: ToolContext, _arguments: dict[str, Any]) -> str:
    _, challenge = context.require_job()
    lines = []
    for path in challenge.source_files():
        line_count = len(
            challenge.resolve_source_path(path).read_text(encoding="utf-8").splitlines()
        )
        lines.append(f"- {path} ({line_count} lines)")
    return "\n".join(lines)


def _read_file(context: ToolContext, arguments: dict[str, Any]) -> str:
    _, challenge = context.require_job()
    path = normalise_source_path(_string_argument(arguments, "path"))
    try:
        content = challenge.resolve_source_path(path).read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ToolError(str(exc)) from None

    lines = content.splitlines()
    start = max(1, _integer_argument(arguments, "start_line", 1))
    end = min(len(lines), _integer_argument(arguments, "end_line", len(lines)))
    if start > end:
        return f"{path} has {len(lines)} lines; the requested range is empty."
    width = len(str(end))
    numbered = (f"{number:>{width}} | {lines[number - 1]}" for number in range(start, end + 1))
    return f"{path} (lines {start}-{end} of {len(lines)})\n" + "\n".join(numbered)


def _search_code(context: ToolContext, arguments: dict[str, Any]) -> str:
    _, challenge = context.require_job()
    query = _string_argument(arguments, "query")
    needle = query.lower()
    results = []
    for path in challenge.source_files():
        content = challenge.resolve_source_path(path).read_text(encoding="utf-8")
        for number, line in enumerate(content.splitlines(), start=1):
            if needle in line.lower():
                results.append(f"{path}:{number}: {line.strip()}")
    if not results:
        return f"No matches for '{query}'."
    shown = results[:MAX_SEARCH_RESULTS]
    if len(results) > MAX_SEARCH_RESULTS:
        shown.append(f"... {len(results) - MAX_SEARCH_RESULTS} more matches omitted.")
    return "\n".join(shown)


def _report_bug(context: ToolContext, arguments: dict[str, Any]) -> str:
    job, challenge = context.require_job()
    path = normalise_source_path(_string_argument(arguments, "file_path"))
    line = _integer_argument(arguments, "line")
    description = _string_argument(arguments, "description")
    original = _string_argument(arguments, "original")
    replacement = _string_argument(arguments, "replacement", required=False)

    try:
        content = challenge.resolve_source_path(path).read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ToolError(str(exc)) from None
    if line < 1:
        raise ToolError("Argument 'line' must be a positive line number.")
    if original == replacement:
        raise ToolError("The replacement is identical to the original code.")
    try:
        locate_change(content, original, line)
    except ChangeNotApplicableError:
        raise ToolError(
            f"The original code was not found in {path}. Copy it exactly from read_file "
            "output, without the line number prefix."
        ) from None

    finding = BugFinding(
        job=job,
        file_path=path,
        line=line,
        description=description.strip(),
        original=original,
        replacement=replacement,
    )
    context.db.add(finding)
    context.db.commit()
    return f"Finding {finding.id} recorded for {path}:{line}."


def _finish_bug_hunt(context: ToolContext, arguments: dict[str, Any]) -> str:
    job, _ = context.require_job()
    summary = _string_argument(arguments, "summary", required=False)
    close_job(job, summary.strip() or None)
    context.db.commit()
    context.scoring.schedule(job.id)
    return (
        f"Bug hunt finished with {len(job.findings)} findings submitted for scoring. "
        "Let the user know the hunt is complete."
    )


TOOLS: dict[str, Tool] = {
    tool.name: tool
    for tool in (
        Tool(
            name="list_bug_hunts",
            description="List the bug hunts that can be started.",
            parameters=_object_schema({}, []),
            handler=_list_bug_hunts,
        ),
        Tool(
            name="start_bug_hunt",
            description="Start a bug hunt. Returns the project's files.",
            parameters=_object_schema(
                {"slug": {"type": "string", "description": "Bug hunt slug."}}, ["slug"]
            ),
            handler=_start_bug_hunt,
        ),
        Tool(
            name="list_files",
            description="List the files in the current bug hunt project.",
            parameters=_object_schema({}, []),
            handler=_list_files,
        ),
        Tool(
            name="read_file",
            description="Read a project file. Each line is prefixed with its line number.",
            parameters=_object_schema(
                {
                    "path": {"type": "string", "description": "File path from list_files."},
                    "start_line": {"type": "integer", "description": "First line, default 1."},
                    "end_line": {"type": "integer", "description": "Last line, default end."},
                },
                ["path"],
            ),
            handler=_read_file,
        ),
        Tool(
            name="search_code",
            description="Case-insensitive text search across the project files.",
            parameters=_object_schema(
                {"query": {"type": "string", "description": "Text to search for."}}, ["query"]
            ),
            handler=_search_code,
        ),
        Tool(
            name="report_bug",
            description=(
                "Report one defect and its fix. The fix replaces the original code with the "
                "replacement code."
            ),
            parameters=_object_schema(
                {
                    "file_path": {"type": "string", "description": "File containing the bug."},
                    "line": {"type": "integer", "description": "Line number of the defect."},
                    "description": {"type": "string", "description": "What is wrong and why."},
                    "original": {
                        "type": "string",
                        "description": "Exact code to replace, copied without line numbers.",
                    },
                    "replacement": {"type": "string", "description": "Corrected code."},
                },
                ["file_path", "line", "description", "original", "replacement"],
            ),
            handler=_report_bug,
        ),
        Tool(
            name="finish_bug_hunt",
            description="Finish the current bug hunt and submit all findings for scoring.",
            parameters=_object_schema(
                {"summary": {"type": "string", "description": "Short summary of the review."}},
                [],
            ),
            handler=_finish_bug_hunt,
        ),
    )
}


def tool_schemas() -> list[dict[str, Any]]:
    return [tool.schema() for tool in TOOLS.values()]


def execute_tool(context: ToolContext, name: str, raw_arguments: str) -> str:
    """Run a tool and return its textual result. Errors are returned, not raised."""
    tool = TOOLS.get(name)
    if tool is None:
        return f"Error: unknown tool '{name}'."
    try:
        arguments = json.loads(raw_arguments or "{}")
    except json.JSONDecodeError as exc:
        return f"Error: arguments are not valid JSON ({exc.msg})."
    if not isinstance(arguments, dict):
        return "Error: arguments must be a JSON object."

    try:
        result = tool.handler(context, arguments)
    except ToolError as exc:
        context.db.rollback()
        return f"Error: {exc}"

    if len(result) > context.output_limit:
        omitted = len(result) - context.output_limit
        result = f"{result[: context.output_limit]}\n... output truncated ({omitted} characters)."
    return result
