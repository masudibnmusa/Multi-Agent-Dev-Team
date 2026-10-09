from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from team.sandbox.docker_manager import DockerManager
from team.tools import file_tools as ft
from team.tools import git_tools, static_analysis
from team.tools.test_runner import run_tests


@dataclass
class ToolContext:
    workspace: Path
    sandbox: DockerManager
    base_branch: str = "main"


# ---------- schema helpers ----------
def _str(desc: str) -> dict:
    return {"type": "string", "description": desc}


def _int(desc: str) -> dict:
    return {"type": "integer", "description": desc}


def _strs(desc: str) -> dict:
    return {"type": "array", "items": {"type": "string"}, "description": desc}


def _tool(name: str, description: str, properties: dict | None = None, required: tuple = ()) -> dict:
    return {
        "name": name,
        "description": description,
        "input_schema": {"type": "object", "properties": properties or {}, "required": list(required)},
    }


_TASK = {
    "type": "object",
    "properties": {
        "id": _str("Short unique id, e.g. T1"),
        "title": _str("Short title"),
        "description": _str("What to build"),
        "files": _strs("Files to create or modify"),
        "interfaces": _strs("Exact signatures / import paths that other code and tests rely on"),
        "acceptance_criteria": _strs("Concrete, testable statements"),
        "depends_on": _strs("Ids of tasks that must finish first"),
    },
    "required": ["id", "title", "description", "acceptance_criteria"],
}

_COMMENT = {
    "type": "object",
    "properties": {
        "file": _str("File path"),
        "line": _int("Line number, if applicable"),
        "severity": {"type": "string", "enum": ["blocker", "major", "minor", "nit"]},
        "comment": _str("Specific, actionable comment"),
    },
    "required": ["comment"],
}

SCHEMAS: dict[str, dict] = {s["name"]: s for s in [
    _tool("list_files", "List files in the workspace (optionally under a subdirectory).",
          {"path": _str("Subdirectory, default '.'")}),
    _tool("read_file", "Read a file with line numbers.",
          {"path": _str("File path"), "start_line": _int("First line"), "end_line": _int("Last line")}, ("path",)),
    _tool("search_code", "Regex search across workspace files.",
          {"pattern": _str("Python regex"), "path": _str("Subdirectory, default '.'")}, ("pattern",)),
    _tool("write_file", "Create or overwrite a file.",
          {"path": _str("File path"), "content": _str("Full file content")}, ("path", "content")),
    _tool("edit_file", "Replace a string that occurs exactly once in a file.",
          {"path": _str("File path"), "old_str": _str("Exact text to replace"), "new_str": _str("Replacement")},
          ("path", "old_str", "new_str")),
    _tool("write_test_file", "Create or overwrite a pytest file. Path must be tests/test_*.py.",
          {"path": _str("tests/test_<name>.py"), "content": _str("Full test file content")}, ("path", "content")),
    _tool("run_tests", "Run pytest in the sandbox.",
          {"target": _str("File or directory, default 'tests'")}),
    _tool("run_static_analysis", "Run linters / syntax checks over the workspace."),
    _tool("git_diff", "Show the full diff of the current task branch against the base branch."),

    # ----- terminal tools (end the agent's turn and carry its structured output) -----
    _tool("submit_plan", "Submit the final plan.", {
        "summary": _str("One-paragraph plan summary"),
        "conventions": _strs("Coding conventions to follow"),
        "tasks": {"type": "array", "items": _TASK},
    }, ("summary", "tasks")),
    _tool("submit_implementation", "Submit your finished implementation for review.", {
        "summary": _str("What you changed and why"),
        "files_changed": _strs("Files created or modified"),
    }, ("summary",)),
    _tool("submit_review", "Submit your review verdict.", {
        "verdict": {"type": "string", "enum": ["approve", "request_changes"]},
        "summary": _str("Overall assessment"),
        "comments": {"type": "array", "items": _COMMENT},
    }, ("verdict", "summary")),
    _tool("submit_tests_written", "Report which test files you wrote.", {
        "files": _strs("Test file paths"),
        "summary": _str("What the tests cover"),
    }, ("files",)),
    _tool("submit_test_report", "Submit your testing report.", {
        "summary": _str("What passed/failed and the likely cause of any failure"),
    }, ("summary",)),
    _tool("submit_arbitration", "Submit your arbitration decision.", {
        "decision": {"type": "string", "enum": ["accept_work", "coder_must_fix", "escalate"]},
        "rationale": _str("Why"),
        "instruction": _str("Precise instruction for the coder (if coder_must_fix)"),
    }, ("decision", "rationale")),
]}

TERMINAL_TOOLS = {
    "submit_plan", "submit_implementation", "submit_review",
    "submit_tests_written", "submit_test_report", "submit_arbitration",
}

READ_TOOLS = ["list_files", "read_file", "search_code"]

# Per-role tool permissions. Only the coder (and the single-agent baseline) can write source files.
PROFILES: dict[str, list[str]] = {
    "planner": READ_TOOLS + ["submit_plan"],
    "planner_arbiter": READ_TOOLS + ["submit_arbitration"],
    "coder": READ_TOOLS + ["write_file", "edit_file", "submit_implementation"],
    "reviewer": READ_TOOLS + ["run_static_analysis", "git_diff", "submit_review"],
    "tester_write": ["write_test_file", "submit_tests_written"],            # blind: no read access
    "tester_write_open": READ_TOOLS + ["write_test_file", "submit_tests_written"],
    "tester_run": READ_TOOLS + ["write_test_file", "run_tests", "submit_test_report"],
    "single": READ_TOOLS + ["write_file", "edit_file", "run_tests", "submit_implementation"],
}


def _truncate(text: str, limit: int = 12000) -> str:
    if len(text) <= limit:
        return text
    half = limit // 2
    return text[:half] + f"\n... [{len(text) - limit} chars truncated] ...\n" + text[-half:]


class ToolRegistry:
    def __init__(self, ctx: ToolContext) -> None:
        self.ctx = ctx

    def schemas(self, profile: str) -> list[dict]:
        return [SCHEMAS[name] for name in PROFILES[profile]]

    def execute(self, profile: str, name: str, args: dict[str, Any]) -> str:
        if name not in PROFILES[profile]:
            return f"ERROR: tool '{name}' is not permitted for profile '{profile}'"
        ws = self.ctx.workspace

        if name == "list_files":
            out = ft.list_files(ws, args.get("path", "."))
        elif name == "read_file":
            out = ft.read_file(ws, args["path"], args.get("start_line"), args.get("end_line"))
        elif name == "search_code":
            out = ft.search_code(ws, args["pattern"], args.get("path", "."))
        elif name == "write_file":
            out = ft.write_file(ws, args["path"], args["content"])
        elif name == "edit_file":
            out = ft.edit_file(ws, args["path"], args["old_str"], args["new_str"])
        elif name == "write_test_file":
            out = ft.write_test_file(ws, args["path"], args["content"])
        elif name == "run_tests":
            run = run_tests(self.ctx.sandbox, ws, args.get("target", "tests"))
            out = f"{'PASSED' if run.passed else 'FAILED'}: {run.summary}\n{run.output_tail}"
        elif name == "run_static_analysis":
            out = static_analysis.run_static_analysis(ws)
        elif name == "git_diff":
            out = git_tools.diff_against(ws, self.ctx.base_branch) or "(no changes)"
        else:
            out = f"ERROR: unknown tool {name}"
        return _truncate(out)