"""Tests for bin/lit-search — cache key determinism, output schema, partial failures.

Importing the bin script as a module (no .py suffix) requires importlib.
HTTP fetchers are stubbed so tests are network-free.
"""

from __future__ import annotations

import importlib.util
import json
from importlib.machinery import SourceFileLoader
from pathlib import Path
from typing import Any

import pytest

BIN = Path(__file__).resolve().parent.parent / "bin" / "lit-search"


def _load_module():
    # bin/lit-search has no .py suffix; use SourceFileLoader explicitly.
    loader = SourceFileLoader("lit_search", str(BIN))
    spec = importlib.util.spec_from_loader("lit_search", loader)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


@pytest.fixture
def mod():
    return _load_module()


def test_cache_key_stable_across_query_whitespace(mod):
    a = mod.cache_key("alzheimer disease MRI", ["pubmed"], 5)
    b = mod.cache_key("  Alzheimer Disease MRI  ", ["pubmed"], 5)
    assert a == b, "cache key should be case- and whitespace-insensitive"


def test_cache_key_stable_across_source_order(mod):
    a = mod.cache_key("foo", ["pubmed", "arxiv"], 5)
    b = mod.cache_key("foo", ["arxiv", "pubmed"], 5)
    assert a == b


def test_cache_key_changes_with_max_results(mod):
    a = mod.cache_key("foo", ["pubmed"], 5)
    b = mod.cache_key("foo", ["pubmed"], 10)
    assert a != b


def test_cache_key_changes_with_query(mod):
    assert mod.cache_key("foo", ["pubmed"], 5) != mod.cache_key("bar", ["pubmed"], 5)


def test_main_uses_cache_when_present(mod, tmp_path, monkeypatch, capsys):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cached = [{"title": "cached paper", "authors": [], "year": 2024, "abstract": "", "url": "", "source": "pubmed"}]
    key = mod.cache_key("test query", ["pubmed"], 3)
    (cache_dir / f"{key}.json").write_text(json.dumps(cached))

    # Make sure we error if the script tries to hit the network — we should not.
    def _boom(*_a, **_k):
        raise RuntimeError("must not hit network when cache is warm")
    monkeypatch.setattr(mod, "search_pubmed", _boom)

    rc = mod.main(["--query", "test query", "--max-results", "3", "--source", "pubmed", "--cache-dir", str(cache_dir)])
    assert rc == 0
    out = capsys.readouterr().out
    assert json.loads(out) == cached


def test_main_writes_cache_after_fresh_fetch(mod, tmp_path, monkeypatch, capsys):
    cache_dir = tmp_path / "cache"
    fake_paper: dict[str, Any] = {
        "title": "Fake paper", "authors": ["Doe J"], "year": 2026,
        "abstract": "abstract", "url": "https://x.example/1", "source": "pubmed",
    }
    monkeypatch.setitem(mod.SOURCES, "pubmed", lambda q, n: [fake_paper])
    rc = mod.main(["--query", "q", "--max-results", "1", "--source", "pubmed", "--cache-dir", str(cache_dir)])
    assert rc == 0
    files = list(cache_dir.glob("*.json"))
    assert len(files) == 1
    written = json.loads(files[0].read_text())
    assert written == [fake_paper]


def _raise(exc):
    def _f(*_a, **_k):
        raise exc
    return _f


def test_main_swallows_per_source_failures(mod, tmp_path, monkeypatch, capsys):
    cache_dir = tmp_path / "cache"
    fake = [{"title": "ok", "authors": [], "year": 2025, "abstract": "", "url": "", "source": "pubmed"}]
    monkeypatch.setitem(mod.SOURCES, "pubmed", lambda q, n: fake)
    monkeypatch.setitem(mod.SOURCES, "arxiv", _raise(RuntimeError("boom")))
    monkeypatch.setitem(mod.SOURCES, "semanticscholar", lambda q, n: [])

    rc = mod.main([
        "--query", "q", "--max-results", "1",
        "--source", "pubmed,arxiv,semanticscholar",
        "--cache-dir", str(cache_dir),
        "--no-cache",
    ])
    # arXiv raised; pubmed succeeded; rc must be 0 because at least one source returned hits.
    assert rc == 0
    out = capsys.readouterr().out
    assert json.loads(out) == fake


def test_main_returns_1_when_all_sources_fail(mod, tmp_path, monkeypatch, capsys):
    cache_dir = tmp_path / "cache"
    monkeypatch.setitem(mod.SOURCES, "pubmed", _raise(RuntimeError("a")))
    monkeypatch.setitem(mod.SOURCES, "arxiv", _raise(RuntimeError("b")))
    rc = mod.main([
        "--query", "q", "--max-results", "1",
        "--source", "pubmed,arxiv",
        "--cache-dir", str(cache_dir),
        "--no-cache",
    ])
    assert rc == 1


def test_main_rejects_unknown_source(mod, tmp_path, capsys):
    rc = mod.main([
        "--query", "q", "--source", "googlescholar", "--cache-dir", str(tmp_path),
    ])
    assert rc == 2
