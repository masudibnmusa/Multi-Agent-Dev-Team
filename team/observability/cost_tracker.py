import json
from collections import defaultdict
from pathlib import Path


class BudgetExceeded(RuntimeError):
    pass


# USD per million tokens: (input, output, cache write, cache read).
# Cache write is 1.25x input (5-minute TTL). Add a row for every model you configure; "default" is a fallback guess.
PRICES_PER_MTOK: dict[str, tuple[float, float, float, float]] = {
    "claude-sonnet-5-5": (2.00, 10.00, 2.50, 0.10),
    "default": (3.00, 15.00, 3.75, 0.30),
}


class CostTracker:
    def __init__(self, budget_usd: float | None = None, token_budget: int | None = None,
                 prices: dict[str, tuple[float, float, float, float]] | None = None) -> None:
        self.budget_usd = budget_usd
        self.token_budget = token_budget
        self.prices = prices or PRICES_PER_MTOK
        self.rows: dict[str, dict] = defaultdict(
            lambda: {"calls": 0, "input": 0, "output": 0, "cache_write": 0, "cache_read": 0, "usd": 0.0}
        )

    def record(self, agent: str, model: str, input_tokens: int, output_tokens: int,
               cache_write: int = 0, cache_read: int = 0) -> None:
        """input_tokens is the uncached part only; the API reports cache writes and reads separately."""
        p_in, p_out, p_write, p_read = self.prices.get(model, self.prices["default"])
        row = self.rows[agent]
        row["calls"] += 1
        row["input"] += input_tokens
        row["output"] += output_tokens
        row["cache_write"] += cache_write
        row["cache_read"] += cache_read
        row["usd"] += (input_tokens * p_in + output_tokens * p_out
                       + cache_write * p_write + cache_read * p_read) / 1e6

    @property
    def total_usd(self) -> float:
        return sum(r["usd"] for r in self.rows.values())

    @property
    def total_tokens(self) -> int:
        return sum(r["input"] + r["output"] + r["cache_write"] + r["cache_read"] for r in self.rows.values())

    def check_budget(self) -> None:
        if self.budget_usd is not None and self.total_usd >= self.budget_usd:
            raise BudgetExceeded(f"${self.total_usd:.2f} spent of ${self.budget_usd:.2f} budget")
        if self.token_budget is not None and self.total_tokens >= self.token_budget:
            raise BudgetExceeded(f"{self.total_tokens:,} tokens used of {self.token_budget:,} budget")

    def by_agent(self) -> dict[str, dict]:
        return {k: dict(v) for k, v in self.rows.items()}

    def summary(self) -> str:
        lines = [f"{'agent':<16} {'calls':>5} {'input':>10} {'cache rd':>10} {'output':>9} {'usd':>8}"]
        for agent, r in self.rows.items():
            lines.append(f"{agent:<16} {r['calls']:>5} {r['input'] + r['cache_write']:>10,} "
                         f"{r['cache_read']:>10,} {r['output']:>9,} {r['usd']:>8.4f}")
        lines.append(f"{'TOTAL tokens':<16} {self.total_tokens:>38,} {self.total_usd:>8.4f}")
        return "\n".join(lines)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(
            {"total_usd": self.total_usd, "total_tokens": self.total_tokens, "by_agent": self.by_agent()},
            indent=2,
        ))