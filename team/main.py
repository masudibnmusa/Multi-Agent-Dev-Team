from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from team.config import Config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="team", description="Multi-agent dev team")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="Build a feature from a plain-language request")
    build.add_argument("request", help="Feature request, in quotes")
    build.add_argument("--repo", help="Existing repo path (default: fresh workspace)")
    build.add_argument("--run-id", help="Custom run id")
    build.add_argument("--max-rounds", type=int, help="Max revision rounds per task")
    build.add_argument("--budget", type=float, help="Cost budget in USD")
    build.add_argument("--no-reviewer", action="store_true", help="Disable the Reviewer")
    build.add_argument("--docker", action="store_true", help="Run tests in Docker")

    args = parser.parse_args(argv)

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set (put it in .env).", file=sys.stderr)
        return 2

    config = Config()
    if args.max_rounds:
        config.max_revision_rounds = args.max_rounds
    if args.budget:
        config.cost_budget_usd = args.budget
    if args.no_reviewer:
        config.enable_reviewer = False
    if args.docker:
        config.use_docker = True

    # Imported late so --help works without the API key / SDK.
    from team.orchestrator.orchestrator import Orchestrator

    orchestrator = Orchestrator(
        config,
        workspace=Path(args.repo) if args.repo else None,
        run_id=args.run_id,
    )
    summary = orchestrator.run(args.request)

    print("\n" + "=" * 60)
    print(f"Result      : {'SUCCESS' if summary.success else 'INCOMPLETE'}")
    print(f"Tasks       : {summary.tasks_done}/{summary.tasks_total} done")
    print(f"Integration : {'passed' if summary.integration_passed else 'failed'}")
    print(f"Rounds      : {summary.rounds_total}")
    print(f"Cost        : ${summary.cost_usd:.4f} ({summary.tokens:,} tokens)")
    print(f"Run dir     : {summary.run_dir}")
    if summary.stopped_reason:
        print(f"Stopped     : {summary.stopped_reason}")
    return 0 if summary.success else 1


if __name__ == "__main__":
    raise SystemExit(main())