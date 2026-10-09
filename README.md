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
9. **Integration**: once all tasks are approved and passing, the full test suite runs and the final patch or PR is produced.
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
integration test run → final patch/PR + summary
```

### Agents

| Agent | Responsibility | Tool access |
|-------|----------------|-------------|
| **Planner** | Decomposes the request into tasks, interfaces, and acceptance criteria; arbitrates deadlocks | Read-only |
| **Coder** | Implements one task at a time and revises based on feedback | Read / search / **write** |
| **Reviewer** | Checks diffs against the plan; returns approve or located change requests | Read-only + static analysis |
| **Tester** | Writes tests from acceptance criteria and runs them in a sandbox | Read-only + test runner |

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
├── workspace/                         # Generated project output
├── data/
│   ├── runs/                          # Saved run transcripts and shared-memory snapshots
│   └── benchmarks/
│
├── tests/
│   ├── test_message_bus.py
│   ├── test_workflow.py
│   ├── test_shared_store.py
│   └── test_arbitration.py
│
├── .env.example
├── requirements.txt
└── run.sh
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Docker (for sandboxed test execution)
- An Anthropic API key

### Installation

```bash
git clone https://github.com/masudibnmusa/Multi-Agent-Dev-Team.git
cd multi-agent-dev-team
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

---

## Configuration

Set in `team/config.py` (and `.env` for secrets):

| Setting | Description |
|---------|-------------|
| `MODELS` | Model used per role (e.g., a stronger model for Planner/Reviewer, a faster one for Coder) |
| `MAX_REVISION_ROUNDS` | Cap on review/test feedback loops per task before arbitration |
| `MAX_TASKS` | Upper bound on tasks the Planner may create |
| `TOKEN_BUDGET` / `COST_BUDGET` | Hard limits per run |
| `SANDBOX_TIMEOUT` | Max seconds for any test or code execution |

---

## Observability

Every run is saved to `data/runs/<run_id>/`:

- **Transcript**: every typed message, in order
- **Shared-memory snapshots**: plan, decisions, and task status over time
- **Cost report**: tokens and dollars per agent
- **Timeline**: who did what and when (`timeline_viewer.py`)

---

## Evaluation

The `evaluation/` module measures whether the team structure actually helps.

- **Benchmark features**: a set of feature requests, each with hidden acceptance tests
- **Ablations**: full team vs. single agent, with vs. without the Reviewer, with vs. without the feedback loop
- **Metrics**:
  - Success rate (hidden tests pass)
  - Rounds to completion
  - Cost per successful feature
  - Reviewer usefulness (how often review comments led to a real fix vs. noise)

```bash
python -m evaluation.ablation_runner --benchmark data/benchmarks/ --runs 5
```

---

## Design Principles

- **Typed over free-form**: structured messages keep runs predictable and debuggable.
- **Least privilege**: only the Coder can write files; every other role is read-only.
- **Bounded loops**: revision rounds, tasks, and spend are all capped; deadlocks escalate to arbitration, then to a human.
- **Blind testing**: the Tester works from acceptance criteria, not the implementation.
- **Isolation**: all generated code and tests run in a Docker sandbox.
- **Reproducibility**: runs are logged in full so they can be inspected and replayed.

---

## Limitations

- Output quality depends heavily on how precise the Planner's interfaces and acceptance criteria are.
- Multi-agent runs cost more than a single agent; the ablations exist to show whether the extra cost pays off.
- Large repos require careful context management (compact repo maps, per-task views) to keep token usage in check.

---

## Contributing

Issues and pull requests are welcome. Please run `pytest` before submitting.

## License

MIT