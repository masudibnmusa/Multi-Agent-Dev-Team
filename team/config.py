from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = "claude-sonnet-5-5"
ROLES = ("planner", "coder", "reviewer", "tester")


def _default_models() -> dict[str, str]:
    return {r: os.getenv(f"TEAM_MODEL_{r.upper()}", DEFAULT_MODEL) for r in ROLES}


@dataclass
class Config:
    # Models per role
    models: dict[str, str] = field(default_factory=_default_models)

    # Loop limits
    max_revision_rounds: int = 3      # coder rounds per task before arbitration
    max_tasks: int = 8                # max tasks the planner may create
    max_agent_turns: int = 30         # max LLM turns in a single agent run
    max_tokens_per_call: int = 8000

    # Budgets
    cost_budget_usd: float = 5.0
    token_budget: int = 2_000_000

    # Sandbox
    sandbox_timeout: int = 120
    use_docker: bool = os.getenv("USE_DOCKER", "false").lower() == "true"
    docker_image: str = "team-sandbox:latest"

    # Behaviour toggles (used by ablations)
    enable_reviewer: bool = True
    blind_tests: bool = True          # tester writes tests without seeing the implementation

    # Paths
    workspace_dir: Path = ROOT / "workspace"
    runs_dir: Path = ROOT / "data" / "runs"
    prompts_dir: Path = ROOT / "team" / "llm" / "prompts"

    max_diff_chars: int = 30000