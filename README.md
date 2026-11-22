# Multi-Agent Dev Team

A team of specialized LLM agents that turns a plain-language feature request into working, reviewed, and tested code.

A **Planner** breaks the request into tasks, a **Coder** implements them, a **Reviewer** critiques the code, and a **Tester** writes and runs tests. The agents coordinate through typed messages and a shared memory, and review comments and test failures flow back to the Coder in a capped feedback loop.

---

## Core Idea

**Role specialization + structured handoffs.**

- Each agent has its own system prompt, tools, and permissions.
- Agents communicate through **typed messages** (not free-form chat), so the workflow stays predictable and debuggable.
- A **feedback loop** (review comments and test failures routed back to the Coder) is what makes this a team rather than a pipeline.
- The Tester writes tests from the acceptance criteria, ideally **without seeing the implementation first**, to avoid tests that merely mirror the code.

---

## How It Works

1. **Feature request intake**: describe a feature in plain language, plus a target repo or an empty workspace.
2. **Planning**: the Planner produces a structured plan: tasks, file targets, interfaces, acceptance criteria, and task dependencies.
3. **Shared memory setup**: the plan, repo map, coding conventions, and decisions are written to a shared store all agents can read.
4. **Implementation**: the Coder takes one task at a time, edits files, and posts a "ready for review" message with a diff summary.
5. **Review**: the Reviewer inspects the diff against the plan and acceptance criteria, then returns *approve* or *request-changes* with specific, located comments.
6. **Testing**: the Tester writes tests from the acceptance criteria and runs them in a sandbox.
7. **Feedback loop**: review comments and test failures route back to the Coder, with a capped number of revision rounds.
8. **Conflict resolution**: if agents disagree repeatedly, the Planner or orchestrator arbitrates, or escalates to the human.
9. **Integration**: each finished task is merged into the base branch; at the end the full test suite runs and a `final.patch` is written.
10. **Reporting**: a summary of what was built, decisions made, and open issues.

---

## Architecture

```
Feature request
      ↓
planner_agent.py → structured plan → shared_store.py
      ↓
task_scheduler.py picks next task
      ↓
┌───────────────── per-task loop (orchestrator) ─────────────────┐
│  TaskAssignment ──► coder_agent.py (edits files)               │
│        ↓                                                       │
│  ReviewRequest ──► reviewer_agent.py                           │
│        ↓                                                       │
│  changes requested? ──► back to Coder (round counter + 1)      │
│        ↓ approved                                              │
│  tester_agent.py writes + runs tests                           │
│        ↓                                                       │
│  failures? ──► TestReport back to Coder                        │
│        ↓ passing                                               │
│  mark task done in shared_store.py                             │
└────────────────────────────────────────────────────────────────┘
      ↓
integration test run → final.patch + report.md
```

### Agents

| Agent | Responsibility | Tool access |
|-------|----------------|-------------|
| **Planner** | Decomposes the request into tasks, interfaces, and acceptance criteria; arbitrates deadlocks | Read-only |
| **Coder** | Implements one task at a time and revises based on feedback | Read / search / **write** (anything except `tests/`) |
| **Reviewer** | Checks diffs against the plan; returns approve or located change requests | Read-only + static analysis + diff |
| **Tester** | Writes tests from acceptance criteria and runs them in a sandbox | Writes only `tests/test_*.py`; blind (no read access) while writing, read + test runner while running |

The Tester's pass/fail is not taken from the model: after every testing round the orchestrator runs the whole `tests/` directory itself and uses that result.

### Message Types

`TaskAssignment`, `ReviewRequest`, `ReviewResult`, `TestReport`, `EscalationNotice`. All payloads are validated with Pydantic.

---

## Project Structure

```
multi-agent-dev-team/
│
├── team/
│   ├── main.py                        # CLI entry: `team build "<feature request>"`
│   ├── config.py                      # Models per role, round limits, budgets
│   │
│   ├── orchestrator/
│   │   ├── orchestrator.py            # Controls workflow, routes messages, enforces limits
│   │   ├── workflow.py                # State machine: plan -> code -> review -> test -> done
│   │   ├── task_scheduler.py          # Order tasks by dependency, track status
│   │   └── arbitration.py             # Resolve deadlocks between agents
│   │
│   ├── agents/
│   │   ├── base_agent.py              # Shared loop: read inbox, think, use tools, send messages
│   │   ├── planner_agent.py
│   │   ├── coder_agent.py
│   │   ├── reviewer_agent.py
│   │   └── tester_agent.py
│   │
│   ├── protocol/
│   │   ├── messages.py                # Typed messages
│   │   ├── message_bus.py             # Routing, delivery, per-agent inboxes
│   │   └── schemas.py                 # Payload validation (Pydantic)
│   │
│   ├── memory/
│   │   ├── shared_store.py            # Blackboard: plan, decisions, task status, artifacts
│   │   ├── repo_context.py            # Repo map and conventions, kept current as code changes
│   │   ├── decision_log.py            # Why choices were made (prevents re-litigating)
│   │   └── agent_scratchpads.py       # Private working notes per agent
│   │
│   ├── tools/
│   │   ├── registry.py                # Per-role tool permissions
│   │   ├── file_tools.py              # Read/search/edit (Coder write; others read-only)
│   │   ├── test_runner.py             # Run tests in sandbox (Tester)
│   │   ├── static_analysis.py         # Linters/type checkers (Reviewer)
│   │   └── git_tools.py               # Branch, commit, diff
│   │
│   ├── sandbox/
│   │   └── docker_manager.py          # Isolated execution for tests and code
│   │
│   ├── llm/
│   │   ├── llm_client.py              # Claude API with native tool use
│   │   └── prompts/                   # planner.md, coder.md, reviewer.md, tester.md
│   │
│   └── observability/
│       ├── conversation_logger.py     # Full message transcript
│       ├── cost_tracker.py            # Tokens/dollars per agent per run
│       └── timeline_viewer.py         # Visualize who did what and when
│
├── evaluation/
│   ├── benchmark_features.py          # Feature requests with acceptance tests
│   ├── ablation_runner.py             # Team vs. single agent, with/without reviewer
│   └── metrics.py                     # Success rate, rounds to completion, cost
│
├── workspace/                         # Generated project output (git-ignored)
├── data/                              # (git-ignored)
│   ├── runs/                          # Saved run transcripts and shared-memory snapshots
│   └── benchmarks/
│
├── tests/                             # Unit tests (no API calls, no Docker needed)
│
├── .env.example
├── requirements.txt
└── run.sh
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- An Anthropic API key
- Docker (optional, recommended): needed for isolated test execution (`--docker` / `USE_DOCKER=true`)

### Installation

```bash
git clone https://github.com/masudibnmusa/Multi-Agent-Dev-Team.git
cd Multi-Agent-Dev-Team
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then add your ANTHROPIC_API_KEY
```

### Usage

```bash
# Build a feature in a fresh workspace
python -m team.main build "Add a REST endpoint that returns paginated user records"

# Build a feature in an existing repo
python -m team.main build "Add rate limiting to the login route" --repo ./path/to/repo

# Or use the helper script
./run.sh "Add a CSV export button to the reports page"
```

Options for `build`:

| Flag | Effect |
|------|--------|
| `--repo PATH` | Work in an existing git repo instead of a fresh `workspace/<run_id>/` |
| `--docker` | Run tests in Docker (same as `USE_DOCKER=true`) |
| `--max-rounds N` | Revision rounds per task before arbitration (N ≥ 1, default 3) |
| `--budget USD` | Cost budget for the run (> 0, default 5.0) |
| `--no-reviewer` | Skip the Reviewer (ablation) |
| `--run-id ID` | Custom run id (default: timestamp) |

The exit code is 0 when every task is done and the integration tests pass, 1 when the run is incomplete, and 2 for bad input.

### Working in an existing repo (`--repo`)

The team commits and merges in your repo, so it is strict about where it starts:

- The working tree must be **clean** (no uncommitted or untracked changes), and you must be **on a branch** (not a detached HEAD). Otherwise the run refuses to start.
- Each task runs on its own branch, `task/<run_id>/<task id>`, and is merged into the branch you started on once it passes. Unfinished work stays on its task branch as a `WIP` commit and is not merged.
- Use `--docker` here: the repo's own code and any text in it reach the models, and generated tests run against it.

---

## Configuration

Defaults live in the `Config` dataclass in `team/config.py`. Secrets and a few overrides come from `.env`:

| Setting | Where | Default | Description |
|---------|-------|---------|-------------|
| `ANTHROPIC_API_KEY` | `.env` | - | Required |
| `TEAM_MODEL_PLANNER` / `_CODER` / `_REVIEWER` / `_TESTER` | `.env` | `claude-sonnet-5-5` | Model per role |
| `USE_DOCKER` | `.env` | `false` | Run tests in Docker (no network, 1 CPU, 1 GB) |
| `max_revision_rounds` | `config.py` / `--max-rounds` | 3 | Coder rounds per task before arbitration |
| `max_tasks` | `config.py` | 8 | Upper bound on tasks the Planner may create |
| `max_agent_turns` | `config.py` | 30 | LLM turns per agent call |
| `cost_budget_usd` / `token_budget` | `config.py` / `--budget` | 5.0 / 2,000,000 | Hard limits per run |
| `sandbox_timeout` | `config.py` | 120 | Seconds per test run (Docker containers time themselves out) |
| `blind_tests` | `config.py` | `true` | Tester writes tests without seeing the code |

**Cost tracking:** prices per model are in `PRICES_PER_MTOK` in `team/observability/cost_tracker.py`. Only `claude-sonnet-5-5` has real prices; if you switch a role to another model, add its row, or the budget is computed from the `default` guess. Every agent call uses prompt caching, and cache writes and reads are priced separately.

---

## Observability

Every run is saved to `data/runs/<run_id>/`:

| File | Contents |
|------|----------|
| `report.md` | Result, plan, task status, decisions, open issues, cost table |
| `final.patch` | Everything the run changed, as one diff |
| `messages.jsonl` | Every typed message, in order |
| `events.jsonl` | LLM calls (incl. cache tokens), tool calls, arbitration, escalations, crashes |
| `snapshots/` | Shared memory after planning and after each task |
| `cost.json` | Tokens and dollars per agent |

These are written even when a run stops early (budget, agent error, or crash); the reason is in `report.md`.

```bash
python -m team.observability.timeline_viewer                  # latest run
python -m team.observability.timeline_viewer data/runs/<run_id> --messages-only
```

---

## Evaluation

The `evaluation/` module measures whether the team structure actually helps.

- **Benchmark features** (`benchmark_features.py`): `slugify`, `lru_cache` and `token_bucket`, each with hidden acceptance tests the agents never see
- **Modes**: `team_full`, `team_no_reviewer`, `single_agent` (one agent with every tool and a test loop)
- **Metrics**:
  - Success rate (hidden tests pass)
  - Average cost, and cost per successful feature
  - Average rounds
  - Review rejections
  - Reviewer misses (tests failed after the Reviewer approved)

```bash
python -m evaluation.ablation_runner --modes team_full single_agent --features slugify lru_cache --repeats 3 --budget 2.0
```

Results go to `data/benchmarks/results/<timestamp>/results.jsonl`, and a summary table is printed. Hidden tests run on the host, with the API key removed from their environment.

---

## Design Principles

- **Typed over free-form**: structured messages keep runs predictable and debuggable.
- **Least privilege**: only the Coder writes source files and it cannot touch `tests/`; the Tester writes only `tests/test_*.py`; Planner and Reviewer are read-only. All paths are confined to the workspace.
- **Bounded loops**: revision rounds, tasks, and spend are all capped; deadlocks escalate to arbitration, then to a human.
- **Blind testing**: the Tester works from acceptance criteria, not the implementation.
- **Isolation**: with `USE_DOCKER=true` (or `--docker`), generated code and tests run in a Docker sandbox with no network. The default (`false`) runs them on your machine with the API key removed from their environment, but they are not isolated: use Docker for untrusted repos.
- **Reproducibility**: runs are logged in full so they can be inspected; the report is written even when a run crashes.

---

## Limitations

- Output quality depends heavily on how precise the Planner's interfaces and acceptance criteria are.
- Multi-agent runs cost more than a single agent; the ablations exist to show whether the extra cost pays off.
- Large repos require careful context management (compact repo maps, per-task views) to keep token usage in check.

---

## Contributing

Issues and pull requests are welcome. Please run `pytest` before submitting (the unit tests need no API key or Docker).

## License

MIT