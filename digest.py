"""A readable Markdown brief instead of a log line.

Same fetches as watch.py, but formatted for a human reading it once a day: the
loudest threads first, the news grouped by source, and the total spend at the end.

    python3 digest.py watchlist.json --state seen.json --out digest.md
"""
from __future__ import annotations

import argparse
import json
import pathlib
from collections import Counter
from datetime import date

from monitor import fresh, load_state, news, reddit, save_state


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("watchlist", type=pathlib.Path)
    ap.add_argument("--state", type=pathlib.Path, default=pathlib.Path("seen.json"))
    ap.add_argument("--out", default="digest.md")
    args = ap.parse_args()

    config = json.loads(args.watchlist.read_text(encoding="utf-8"))
    state = load_state(args.state)
    country, lang = config.get("country", "us"), config.get("lang", "en")

    lines = [f"# Monitoring digest — {date.today().isoformat()}", ""]
    rows_fetched = 0

    for term in config["terms"]:
        label, query = term["label"], term["query"]
        lines += [f"## {label}", f"*query:* `{query}`", ""]
        quiet = True

        if term.get("reddit"):
            rows = reddit(query, country, term.get("subreddit"))
            rows_fetched += len(rows)
            new = sorted(fresh(state, label, "reddit", rows, "id", "created_at"),
                         key=lambda p: -((p.get("score") or 0) + 2 * (p.get("comments") or 0)))
            if new:
                quiet = False
                lines += ["### Reddit", ""]
                for post in new[:12]:
                    lines.append(
                        f"- **{post.get('score') or 0}▲ / {post.get('comments') or 0} comments** — "
                        f"[{(post.get('title') or '').strip()}]({post.get('permalink')}) "
                        f"· r/{post.get('subreddit')} · {str(post.get('created_at') or '')[:10]}")
                lines.append("")

        if term.get("news"):
            rows = news(query, country, lang)
            rows_fetched += len(rows)
            new = fresh(state, label, "news", rows, "link", "date")
            if new:
                quiet = False
                lines += ["### News", ""]
                by_source: dict[str, list] = {}
                for article in new:
                    by_source.setdefault(article.get("source") or "unknown", []).append(article)
                for source, articles in sorted(by_source.items(), key=lambda kv: -len(kv[1])):
                    lines.append(f"**{source}**")
                    for a in articles[:4]:
                        lines.append(f"- [{a.get('title')}]({a.get('link')}) · {a.get('date')}")
                    lines.append("")

        if quiet:
            lines += ["_nothing new since the last run._", ""]

    lines += ["---", "",
              f"*{rows_fetched} rows fetched, about ${rows_fetched * 0.0005:.3f}. "
              "Only items unseen in previous runs are listed.*"]

    save_state(args.state, state)
    pathlib.Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {args.out} ({rows_fetched} rows fetched)")


if __name__ == "__main__":
    main()
