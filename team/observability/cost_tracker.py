import json
from collections import defaultdict
from pathlib import Path


class BudgetExceeded(RuntimeError):
    pass


# USD per million tokens: (input, output). PLACEHOLDER values; set the real prices for your models.
PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "default": (3.00, 15.00),
}


class CostTracker:
    def __init__(self, budget_usd: float | None = None, token_budget: int | None = None,
                 prices: dict[str, tuple[float, float]] | None = None) -> None:
        self.budget_usd = budget_usd
        self.token_budget = token_budget
        self.prices = prices or PRICES_PER_MTOK
        self.rows: dict[str, dict] = defaultdict(lambda: {"calls": 0, "input": 0, "output": 0, "usd": 0.0})

    def record(self, agent: str, model: str, input_tokens: int, output_tokens: int) -> None:
        price_in, price_out = self.prices.get(model, self.prices["default"])
        row = self.rows[agent]
        row["calls"] += 1
        row["input"] += input_tokens
        row["output"] += output_tokens
        row["usd"] += input_tokens / 1e6 * price_in + output_tokens / 1e6 * price_out

    @property
    def total_usd(self) -> float:
        return sum(r["usd"] for r in self.rows.values())

    @property
    def total_tokens(self) -> int:
        return sum(r["input"] + r["output"] for r in self.rows.values())

    def check_budget(self) -> None:
        if self.budget_usd is not None and self.total_usd >= self.budget_usd:
            raise BudgetExceeded(f"${self.total_usd:.2f} spent of ${self.budget_usd:.2f} budget")
        if self.token_budget is not None and self.total_tokens >= self.token_budget:
            raise BudgetExceeded(f"{self.total_tokens:,} tokens used of {self.token_budget:,} budget")

    def by_agent(self) -> dict[str, dict]:
        return {k: dict(v) for k, v in self.rows.items()}

    def summary(self) -> str:
        lines = [f"{'agent':<12} {'calls':>5} {'input':>10} {'output':>9} {'usd':>8}"]
        for agent, r in self.rows.items():
            lines.append(f"{agent:<12} {r['calls']:>5} {r['input']:>10,} {r['output']:>9,} {r['usd']:>8.4f}")
        lines.append(f"{'TOTAL':<12} {'':>5} {'':>10} {self.total_tokens:>9,} {self.total_usd:>8.4f}")
        return "\n".join(lines)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(
            {"total_usd": self.total_usd, "total_tokens": self.total_tokens, "by_agent": self.by_agent()},
            indent=2,
        ))