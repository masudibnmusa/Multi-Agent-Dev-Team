from types import SimpleNamespace

from team.config import Config
from team.llm.llm_client import LLMClient
from team.observability.cost_tracker import CostTracker


def test_loop_enables_caching_and_records_cache_tokens():
    sent = {}

    def create(**kw):
        sent.update(kw)
        usage = SimpleNamespace(input_tokens=10, output_tokens=5,
                                cache_creation_input_tokens=100, cache_read_input_tokens=None)
        block = SimpleNamespace(type="tool_use", name="submit_x", input={"ok": 1}, id="t1")
        return SimpleNamespace(usage=usage, content=[block])

    llm = LLMClient.__new__(LLMClient)  # skip __init__: no real API client
    llm.config, llm.cost, llm.logger = Config(), CostTracker(), None
    llm.client = SimpleNamespace(messages=SimpleNamespace(create=create))

    result = llm.run_loop(agent="a", model="m", system="s", user_message="u", tools=[],
                          execute=lambda n, a: "", terminal_tools={"submit_x"})
    assert result.terminal_input == {"ok": 1}
    assert sent["cache_control"] == {"type": "ephemeral"}
    assert llm.cost.rows["a"]["cache_write"] == 100 and llm.cost.rows["a"]["cache_read"] == 0
