# Reddit & news monitoring — brand mentions with state, not another firehose

Two collectors, one monitoring loop:

- [`reddit_posts`](https://quanticdata.io/collectors/reddit-scraper-api/) — search or a subreddit
  feed with `sort` and `time` windows. Rows carry id, title, subreddit, author, score, comment
  count, `created_at`, permalink, outbound URL, domain, NSFW flag and flair. **$0.0005 per post.**
- [`google_news`](https://quanticdata.io/collectors/google-news-api/) — the Google News vertical
  per country and language: title, link, source, date, description, image. **$0.0005 per article.**

The scripts here keep a JSON state file, so each run reports *what is new* rather than printing
the same fifty items every hour.

```bash
pip install requests
export QUANTICDATA_API_KEY=qd_live_your_key_here

python3 watch.py watchlist.json --state seen.json        # run from cron
python3 digest.py watchlist.json --out digest.md         # a readable daily brief
```

## Files

| File | What it does |
|---|---|
| [`monitor.py`](monitor.py) | collector calls + the state file (per-term high-water marks) |
| [`watch.py`](watch.py) | one pass: fetch, diff against state, print and optionally webhook |
| [`digest.py`](digest.py) | a Markdown brief grouped by term, with the loudest threads first |
| [`watchlist.json`](watchlist.json) | the input format |

## Watchlist

```json
{
  "terms": [
    { "label": "our brand", "query": "quanticdata", "reddit": true, "news": true },
    { "label": "category",  "query": "web scraping api", "reddit": true, "news": true,
      "subreddit": "webscraping" },
    { "label": "competitor", "query": "\"acme scraper\"", "news": true }
  ],
  "country": "us",
  "lang": "en"
}
```

## The state file is the whole design

Monitoring without state is a firehose you stop reading on day three. `monitor.py` stores, per
term and per source, the ids already seen plus the newest timestamp. Each run:

1. fetches a small page (`sort: "new"` for Reddit, the default recency order for News),
2. keeps only items whose id is unknown **and** whose timestamp beats the high-water mark,
3. writes the merged state back.

That means a run costs a few cents whether it is the first one or the four hundredth, and the
output is always "here is what changed".

## Alerting thresholds worth having

A new mention is not news. These three usually are, and `watch.py` flags them:

- a Reddit post above a **score or comment threshold** — argument, not chatter
- a mention in a **subreddit not seen before** for that term — the conversation moved
- **three or more news articles in 24 hours** for one term — something happened

## Related

- [Reddit scraper API](https://quanticdata.io/collectors/reddit-scraper-api/) · [Google News API](https://quanticdata.io/collectors/google-news-api/) · [All collectors](https://quanticdata.io/collectors/)
- [SERP API](https://quanticdata.io/serp-api/) · [Market research data](https://quanticdata.io/market-research-data/)
- [What is web data?](https://quanticdata.io/blog/what-is-web-data/)

MIT licensed.
