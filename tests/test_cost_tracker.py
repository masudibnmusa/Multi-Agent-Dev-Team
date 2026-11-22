import pytest

from team.observability.cost_tracker import BudgetExceeded, CostTracker


def test_cache_tokens_priced_and_counted():
    c = CostTracker(prices={"default": (2.0, 10.0, 2.5, 0.1)})
    c.record("coder", "m", input_tokens=1_000_000, output_tokens=100_000,
             cache_write=1_000_000, cache_read=10_000_000)
    assert c.total_usd == pytest.approx(2.0 + 1.0 + 2.5 + 1.0)
    assert c.total_tokens == 12_100_000
    assert "cache rd" in c.summary()


def test_budget_includes_cache_cost():
    c = CostTracker(budget_usd=1.0, prices={"default": (0, 0, 0, 0.1)})
    c.record("coder", "m", 0, 0, cache_read=10_000_000)
    with pytest.raises(BudgetExceeded):
        c.check_budget()
