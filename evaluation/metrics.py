from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class RunResult:
    feature: str
    mode: str
    repeat: int
    success: bool                  # hidden acceptance tests pass
    internal_success: bool         # the run's own integration tests pass
    cost_usd: float
    tokens: int
    rounds: int
    tasks_total: int
    tasks_done: int
    review_rejections: int
    test_failures_after_review: int
    duration_s: float


def summarize(results: list[RunResult]) -> dict[str, dict]:
    by_mode: dict[str, list[RunResult]] = defaultdict(list)
    for r in results:
        by_mode[r.mode].append(r)

    out: dict[str, dict] = {}
    for mode, rs in by_mode.items():
        n = len(rs)
        successes = sum(r.success for r in rs)
        total_cost = sum(r.cost_usd for r in rs)
        out[mode] = {
            "runs": n,
            "success_rate": successes / n,
            "avg_cost_usd": total_cost / n,
            "cost_per_success_usd": (total_cost / successes) if successes else None,
            "avg_rounds": sum(r.rounds for r in rs) / n,
            "avg_duration_s": sum(r.duration_s for r in rs) / n,
            "review_rejections": sum(r.review_rejections for r in rs),
            # Reviewer-miss proxy: tests failed even though the reviewer had approved.
            "test_failures_after_review": sum(r.test_failures_after_review for r in rs),
        }
    return out


def print_table(summary: dict[str, dict]) -> None:
    header = f"{'mode':<18} {'runs':>4} {'success':>8} {'avg $':>8} {'$/success':>10} {'rounds':>7} {'rejects':>8} {'misses':>7}"
    print(header)
    print("-" * len(header))
    for mode, s in summary.items():
        cps = f"{s['cost_per_success_usd']:.3f}" if s["cost_per_success_usd"] is not None else "n/a"
        print(
            f"{mode:<18} {s['runs']:>4} {s['success_rate']:>8.0%} {s['avg_cost_usd']:>8.3f} {cps:>10} "
            f"{s['avg_rounds']:>7.1f} {s['review_rejections']:>8} {s['test_failures_after_review']:>7}"
        )


def save_results(results: list[RunResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for r in results:
            f.write(json.dumps(asdict(r)) + "\n")