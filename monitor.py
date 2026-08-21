"""Collector calls plus the state file that turns them into monitoring."""
from __future__ import annotations

import json
import os
import pathlib
import time
from typing import Any

import requests

BASE = "https://api.quanticdata.io/v1"
_s = requests.Session()
KEEP_IDS = 3000          # per term+source; enough for months of a busy query


def _h() -> dict[str, str]:
    key = os.environ.get("QUANTICDATA_API_KEY")
    if not key:
        raise SystemExit("set QUANTICDATA_API_KEY — https://app.quanticdata.io/register")
    return {"Authorization": f"Bearer {key}"}


def collect(slug: str, **input_: Any) -> list[dict]:
    body = {k: v for k, v in input_.items() if v not in (None, "", [], False)}
    r = _s.post(f"{BASE}/scraper/collectors/{slug}/run", json=body, headers=_h(), timeout=300)
    data = r.json()
    if data.get("type") == "error" or not r.ok:
        raise RuntimeError(f"{slug} ({r.status_code}): {data.get('message')}")

    run = data.get("payload", {})
    while run.get("status") in ("queued", "running"):
        time.sleep(3)
        run = _s.get(f"{BASE}/scraper/collectors/runs/{run['run_id']}",
                     headers=_h(), timeout=60).json().get("payload", {})
    return run.get("results") or []


def load_state(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_state(path: pathlib.Path, state: dict) -> None:
    path.write_text(json.dumps(state, indent=1, sort_keys=True), encoding="utf-8")


def _slot(state: dict, label: str, source: str) -> dict:
    return state.setdefault(f"{label}::{source}", {"ids": [], "latest": "", "subreddits": []})


def fresh(state: dict, label: str, source: str, rows: list[dict],
          id_key: str, time_key: str) -> list[dict]:
    """Rows whose id is new AND whose timestamp beats the high-water mark."""
    slot = _slot(state, label, source)
    known = set(slot["ids"])
    high = slot["latest"]

    new = [r for r in rows
           if str(r.get(id_key) or r.get("link") or "") not in known
           and str(r.get(time_key) or "") > high]

    slot["ids"] = (slot["ids"] + [str(r.get(id_key) or r.get("link") or "") for r in rows])[-KEEP_IDS:]
    slot["latest"] = max([high] + [str(r.get(time_key) or "") for r in rows])
    return new


def known_subreddits(state: dict, label: str) -> set[str]:
    return set(_slot(state, label, "reddit")["subreddits"])


def remember_subreddits(state: dict, label: str, subs: set[str]) -> None:
    slot = _slot(state, label, "reddit")
    slot["subreddits"] = sorted(set(slot["subreddits"]) | subs)


def reddit(query: str, country: str, subreddit: str | None = None,
           limit: int = 40, sort: str = "new") -> list[dict]:
    return collect("reddit_posts", query=query, subreddit=subreddit, sort=sort,
                   time="week", country=country, max_results=limit)


def news(query: str, country: str, lang: str, limit: int = 30) -> list[dict]:
    return collect("google_news", query=query, country=country, lang=lang, max_results=limit)
