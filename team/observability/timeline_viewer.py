"""Usage: python -m team.observability.timeline_viewer [run_dir] [--messages-only]"""
import argparse
import json
from pathlib import Path

from team.config import ROOT


def _load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def render(run_dir: Path, messages_only: bool = False) -> str:
    messages = _load(run_dir / "messages.jsonl")
    events = [] if messages_only else _load(run_dir / "events.jsonl")

    items: list[tuple[float, str]] = []
    for m in messages:
        task = f" [{m['task_id']}]" if m.get("task_id") else ""
        items.append((m["timestamp"], f"MSG    {m['sender']:>12} -> {m['recipient']:<12} {m['type']}{task}"))
    for e in events:
        data = e.get("data", {})
        brief = data.get("tool") or " ".join(f"{k}={v}" for k, v in list(data.items())[:3])
        items.append((e["t"], f"event  {e['agent']:>12}    {e['kind']} {str(brief)[:70]}"))

    if not items:
        return "(no records found)"
    items.sort(key=lambda x: x[0])
    t0 = items[0][0]
    return "\n".join(f"{t - t0:8.1f}s  {line}" for t, line in items)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", nargs="?")
    parser.add_argument("--messages-only", action="store_true")
    args = parser.parse_args()

    if args.run_dir:
        run_dir = Path(args.run_dir)
    else:
        runs = sorted(p for p in (ROOT / "data" / "runs").iterdir() if p.is_dir())
        if not runs:
            raise SystemExit("No runs found.")
        run_dir = runs[-1]
    print(f"Timeline for {run_dir}\n")
    print(render(run_dir, args.messages_only))


if __name__ == "__main__":
    main()