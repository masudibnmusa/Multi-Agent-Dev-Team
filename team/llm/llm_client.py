from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import anthropic

from team.config import Config
from team.observability.cost_tracker import CostTracker


@dataclass
class LoopResult:
    terminal_tool: str | None
    terminal_input: dict[str, Any] | None
    text: str
    turns: int


class LLMClient:
    """Claude API with native tool use. Runs a tool loop until a terminal (submit_*) tool is called."""

    def __init__(self, config: Config, cost: CostTracker, logger=None) -> None:
        self.config = config
        self.cost = cost
        self.logger = logger
        self.client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY

    def run_loop(
        self,
        *,
        agent: str,
        model: str,
        system: str,
        user_message: str,
        tools: list[dict],
        execute: Callable[[str, dict], str],
        terminal_tools: set[str],
        max_turns: int | None = None,
    ) -> LoopResult:
        max_turns = max_turns or self.config.max_agent_turns
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]
        last_text = ""

        for turn in range(1, max_turns + 1):
            self.cost.check_budget()
            response = self.client.messages.create(
                model=model,
                max_tokens=self.config.max_tokens_per_call,
                system=system,
                tools=tools,
                messages=messages,
            )
            self.cost.record(agent, model, response.usage.input_tokens, response.usage.output_tokens)
            if self.logger:
                self.logger.event(agent, "llm_call", {
                    "turn": turn, "in": response.usage.input_tokens, "out": response.usage.output_tokens,
                })

            messages.append({"role": "assistant", "content": response.content})
            last_text = "".join(b.text for b in response.content if b.type == "text") or last_text
            tool_uses = [b for b in response.content if b.type == "tool_use"]

            if not tool_uses:
                messages.append({
                    "role": "user",
                    "content": "Continue working, and finish by calling the required submit_* tool.",
                })
                continue

            terminal: tuple[str, dict] | None = None
            results: list[dict[str, Any]] = []
            for tu in tool_uses:
                if tu.name in terminal_tools:
                    terminal = terminal or (tu.name, dict(tu.input))
                    continue
                try:
                    output = execute(tu.name, dict(tu.input))
                    is_error = output.startswith("ERROR")
                except Exception as e:  # tool errors go back to the model, not up the stack
                    output, is_error = f"ERROR: {type(e).__name__}: {e}", True
                if self.logger:
                    self.logger.event(agent, "tool_call", {"tool": tu.name, "args": dict(tu.input), "error": is_error})
                results.append({
                    "type": "tool_result", "tool_use_id": tu.id, "content": output, "is_error": is_error,
                })

            if terminal:
                return LoopResult(terminal[0], terminal[1], last_text, turn)
            messages.append({"role": "user", "content": results})

        return LoopResult(None, None, last_text, max_turns)