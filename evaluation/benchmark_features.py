from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Feature:
    name: str
    request: str
    hidden_tests: str  # pytest source; never shown to the agents


FEATURES: list[Feature] = [
    Feature(
        name="slugify",
        request=(
            "Create a Python module `textslug.py` at the workspace root with a function "
            "`slugify(text: str, max_length: int | None = None) -> str`. It lowercases the text, treats every run "
            "of characters that are not ASCII letters or digits as one separator, joins the words with a single "
            "hyphen, and has no leading or trailing hyphens. An input with no letters or digits returns ''. "
            "If max_length is given, truncate the result to at most max_length characters and then strip any "
            "trailing hyphen. max_length=None means no limit."
        ),
        hidden_tests='''
from textslug import slugify

def test_basic():
    assert slugify("Hello, World!") == "hello-world"

def test_collapse_and_strip():
    assert slugify("  a   b  ") == "a-b"

def test_empty():
    assert slugify("") == ""

def test_only_separators():
    assert slugify("---!!!") == ""

def test_digits():
    assert slugify("Python 3.11 rocks") == "python-3-11-rocks"

def test_max_length():
    assert slugify("hello-world", max_length=5) == "hello"

def test_max_length_strips_trailing_hyphen():
    assert slugify("hello world", max_length=6) == "hello"

def test_no_limit_by_default():
    assert slugify("a" * 100) == "a" * 100
''',
    ),
    Feature(
        name="lru_cache",
        request=(
            "Create a module `lru_cache.py` at the workspace root with a class `LRUCache(capacity: int)`. "
            "`get(key)` returns the value or None if the key is missing, and marks the key as most recently used. "
            "`put(key, value)` inserts or updates a key (also marking it most recently used) and evicts the "
            "least recently used key when the size would exceed capacity. `len(cache)` returns the number of "
            "items. A capacity below 1 raises ValueError."
        ),
        hidden_tests='''
import pytest
from lru_cache import LRUCache

def test_put_get():
    c = LRUCache(2); c.put("a", 1)
    assert c.get("a") == 1

def test_missing_returns_none():
    assert LRUCache(1).get("x") is None

def test_evicts_least_recently_used():
    c = LRUCache(2); c.put("a", 1); c.put("b", 2); c.put("c", 3)
    assert c.get("a") is None
    assert c.get("b") == 2
    assert c.get("c") == 3

def test_get_refreshes_recency():
    c = LRUCache(2); c.put("a", 1); c.put("b", 2)
    c.get("a"); c.put("c", 3)
    assert c.get("b") is None
    assert c.get("a") == 1

def test_update_overwrites_and_refreshes():
    c = LRUCache(2); c.put("a", 1); c.put("b", 2)
    c.put("a", 10); c.put("c", 3)
    assert c.get("b") is None
    assert c.get("a") == 10

def test_len():
    c = LRUCache(2); c.put("a", 1); c.put("b", 2); c.put("c", 3)
    assert len(c) == 2

def test_invalid_capacity():
    with pytest.raises(ValueError):
        LRUCache(0)
''',
    ),
    Feature(
        name="token_bucket",
        request=(
            "Create a module `token_bucket.py` at the workspace root with a class "
            "`TokenBucket(capacity: float, refill_per_sec: float, clock=time.monotonic)`. The bucket starts full. "
            "`allow(cost: float = 1) -> bool` first refills tokens based on the time elapsed according to "
            "`clock()` (never exceeding capacity), then returns True and deducts `cost` if enough tokens are "
            "available, otherwise returns False and deducts nothing. capacity <= 0 or refill_per_sec < 0 "
            "raises ValueError."
        ),
        hidden_tests='''
import pytest
from token_bucket import TokenBucket

class FakeClock:
    def __init__(self): self.t = 0.0
    def __call__(self): return self.t

def test_starts_full():
    b = TokenBucket(3, 1, clock=FakeClock())
    assert [b.allow() for _ in range(4)] == [True, True, True, False]

def test_refills_over_time():
    clock = FakeClock(); b = TokenBucket(2, 1, clock=clock)
    b.allow(); b.allow()
    assert not b.allow()
    clock.t = 1.0
    assert b.allow()
    assert not b.allow()

def test_capped_at_capacity():
    clock = FakeClock(); b = TokenBucket(2, 1, clock=clock)
    clock.t = 100.0
    assert b.allow(2)
    assert not b.allow(1)

def test_failed_request_consumes_nothing():
    b = TokenBucket(2, 1, clock=FakeClock())
    assert not b.allow(3)
    assert b.allow(2)

def test_invalid_args():
    with pytest.raises(ValueError):
        TokenBucket(0, 1)
    with pytest.raises(ValueError):
        TokenBucket(1, -1)
''',
    ),
]


def get_features(names: list[str] | None = None) -> list[Feature]:
    if not names:
        return FEATURES
    return [f for f in FEATURES if f.name in names]


def run_hidden_tests(feature: Feature, workspace: Path, timeout: int = 120) -> bool:
    """Copy the hidden tests into the workspace, run them, then remove them."""
    workspace = workspace.resolve()
    hidden_dir = workspace / "_hidden_tests"
    hidden_dir.mkdir(exist_ok=True)
    (hidden_dir / "test_hidden.py").write_text(feature.hidden_tests)
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join([str(workspace), str(workspace / "src")]),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "_hidden_tests"],
            cwd=workspace, env=env, capture_output=True, text=True, timeout=timeout,
        )
        return proc.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    finally:
        shutil.rmtree(hidden_dir, ignore_errors=True)