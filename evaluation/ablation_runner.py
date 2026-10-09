"""Usage:
python -m evaluation.ablation_runner --modes team_full team_no_reviewer single_agent \
    --features slugify lru_cache --repeats 3
"""
from __future__ import annotations

import argparse
import copy
import time
from pathlib import Path

from evaluation.benchmark_features import Feature, get_features, run_hidden_tests
from evaluation.metrics import RunResult, print_table, save_results, summarize
from team.config import ROOT, Config
from team.llm.llm_client import LLMClient
from team.observability.conversation_logger import ConversationLogger
from team.observability.cost_tracker import BudgetExceeded, CostTracker
from team.orchestrator.orchestrator import Orchestrator
from team.sandbox.docker_manager import DockerManager
from team.tools import git_tools
from team.tools.registry import ToolContext, ToolRegistry

MODES = ["team_full", "team_no_reviewer", "single_agent"]

SINGLE_PROMPT = (
    "You are a senior software engineer working alone. Implement the feature request in the workspace, "
    "write pytest tests under tests/, run them with run_tests until they pass, then call "
    "submit_implementation. Follow the interfaces in the request exactly."
)


def run_single_agent(request: str, config: Config, workspace: Path, run_dir: Path) -> dict:
    """Baseline: one agent with all tools and a test loop, no team."""
    logger = ConversationLogger(run_dir)
    cost = CostTracker(config.cost_budget_usd, config.token_budget)
    llm = LLMClient(config, cost, logger)
    sandbox = DockerManager(config.docker_image, config.sandbox_timeout, config.use_docker)
    sandbox.ensure_image()
    base = git_tools.init_repo(workspace)
    registry = ToolRegistry(ToolContext(workspace, sandbox, base))
    try:
        llm.run_loop(
            agent="single", model=config.models["coder"], system=SINGLE_PROMPT, user_message=request,
            tools=registry.schemas("single"),
            execute=lambda name, args: registry.execute("single", name, args),
            terminal_tools={"submit_implementation"}, max_turns=60,
        )
    except BudgetExceeded:
        pass
    cost.save(run_dir / "cost.json")
    return {"cost_usd": cost.total_usd, "tokens": cost.total_tokens}


def run_one(feature: Feature, mode: str, repeat: int, out_dir: Path, base_config: Config) -> RunResult:
    config = copy.deepcopy(base_config)
    run_id = f"{mode}-{feature.name}-{repeat}-{time.strftime('%H%M%S')}"
    workspace = out_dir / "workspaces" / run_id
    config.runs_dir = out_dir / "runs"
    start = time.time()

    if mode == "single_agent":
        stats = run_single_agent(feature.request, config, workspace, config.runs_dir / run_id)
        row = dict(internal_success=False, rounds=1, tasks_total=1, tasks_done=0,
                   review_rejections=0, test_failures_after_review=0, **stats)
    else:
        config.enable_reviewer = mode != "team_no_reviewer"
        summary = Orchestrator(config, workspace=workspace, run_id=run_id).run(feature.request)
        row = dict(
            internal_success=summary.success, rounds=summary.rounds_total, tasks_total=summary.tasks_total,
            tasks_done=summary.tasks_done, review_rejections=summary.review_rejections,
            test_failures_after_review=summary.test_failures_after_review,
            cost_usd=summary.cost_usd, tokens=summary.tokens,
        )

    success = run_hidden_tests(feature, workspace, config.sandbox_timeout)
    return RunResult(
        feature=feature.name, mode=mode, repeat=repeat, success=success,
        duration_s=time.time() - start, **row,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--modes", nargs="+", default=MODES, choices=MODES)
    parser.add_argument("--features", nargs="*", help="Feature names (default: all)")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--out", default=str(ROOT / "data" / "benchmarks" / "results"))
    parser.add_argument("--budget", type=float, default=2.0, help="USD budget per run")
    args = parser.parse_args()

    base_config = Config()
    base_config.cost_budget_usd = args.budget
    out_dir = Path(args.out) / time.strftime("%Y%m%d-%H%M%S")

    results: list[RunResult] = []
    for feature in get_features(args.features):
        for mode in args.modes:
            for repeat in range(1, args.repeats + 1):
                print(f"\n>>> {feature.name} | {mode} | repeat {repeat}")
                result = run_one(feature, mode, repeat, out_dir, base_config)
                print(f"    hidden tests: {'PASS' if result.success else 'FAIL'}  cost ${result.cost_usd:.3f}")
                results.append(result)
                save_results(results, out_dir / "results.jsonl")

    print()
    print_table(summarize(results))
    print(f"\nSaved to {out_dir}")


if __name__ == "__main__":
    main()