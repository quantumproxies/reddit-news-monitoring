"""One monitoring pass: fetch, diff against state, report what is new.

    python3 watch.py watchlist.json --state seen.json --min-score 25
    python3 watch.py watchlist.json --webhook https://hooks.example/qd
"""
from __future__ import annotations

import argparse
import json
import pathlib
from collections import Counter

import requests

from monitor import (fresh, known_subreddits, load_state, news, reddit,
                     remember_subreddits, save_state)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("watchlist", type=pathlib.Path)
    ap.add_argument("--state", type=pathlib.Path, default=pathlib.Path("seen.json"))
    ap.add_argument("--min-score", type=int, default=25, help="Reddit score that counts as loud")
    ap.add_argument("--min-comments", type=int, default=15)
    ap.add_argument("--news-burst", type=int, default=3, help="articles in one run that count as a burst")
    ap.add_argument("--webhook", default=None)
    args = ap.parse_args()

    config = json.loads(args.watchlist.read_text(encoding="utf-8"))
    state = load_state(args.state)
    country, lang = config.get("country", "us"), config.get("lang", "en")

    alerts: list[dict] = []

    for term in config["terms"]:
        label, query = term["label"], term["query"]
        print(f"\n=== {label} — {query!r} ===")

        if term.get("reddit"):
            rows = reddit(query, country, term.get("subreddit"))
            new = fresh(state, label, "reddit", rows, "id", "created_at")
            print(f"reddit: {len(new)} new of {len(rows)}")

            seen_subs = known_subreddits(state, label)
            current = {r.get("subreddit") for r in rows if r.get("subreddit")}
            novel = current - seen_subs if seen_subs else set()
            remember_subreddits(state, label, current)

            for post in sorted(new, key=lambda p: -(p.get("score") or 0))[:10]:
                loud = ((post.get("score") or 0) >= args.min_score
                        or (post.get("comments") or 0) >= args.min_comments)
                mark = "!" if loud else " "
                print(f" {mark} {(post.get('score') or 0):>5}▲ {(post.get('comments') or 0):>4}c "
                      f"r/{str(post.get('subreddit')):<20}{(post.get('title') or '')[:60]}")
                if loud:
                    alerts.append({"type": "loud_thread", "term": label,
                                   "title": post.get("title"),
                                   "url": post.get("permalink"),
                                   "score": post.get("score"),
                                   "comments": post.get("comments")})
            if novel:
                print(f"   new subreddits for this term: {', '.join(sorted(novel))}")
                alerts.append({"type": "new_venue", "term": label, "subreddits": sorted(novel)})

        if term.get("news"):
            rows = news(query, country, lang)
            new = fresh(state, label, "news", rows, "link", "date")
            print(f"news: {len(new)} new of {len(rows)}")
            for article in new[:10]:
                print(f"   {str(article.get('source'))[:22]:<24}{(article.get('title') or '')[:60]}")
            if len(new) >= args.news_burst:
                sources = Counter(a.get("source") for a in new)
                print(f"   BURST: {len(new)} articles from {len(sources)} sources")
                alerts.append({"type": "news_burst", "term": label, "count": len(new),
                               "sources": sources.most_common(5),
                               "headlines": [a.get("title") for a in new[:5]]})

    save_state(args.state, state)
    print(f"\nstate → {args.state};  {len(alerts)} alert(s)")

    if alerts and args.webhook:
        try:
            requests.post(args.webhook, json={"alerts": alerts}, timeout=15)
            print("webhook delivered")
        except requests.RequestException as exc:
            print(f"webhook failed: {exc}")


if __name__ == "__main__":
    main()
