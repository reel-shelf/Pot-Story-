"""Fetch the latest Cash Pot results and save them to results.json.

Runs on GitHub Actions. Reads the public Cash Pot results pages, pulls out
each day's draws, and merges them with what is already saved.
"""
import html
import json
import re
import urllib.request
from datetime import datetime, timedelta, timezone

SOURCES = [
    "https://lotteryguru.com/jamaica-lottery-results/jm-cash-pot",
    "https://lotteryguru.com/jamaica-lottery-results/jm-cash-pot/jm-cash-pot-results-history",
]
DRAWS = ["Earlybird", "Morning", "Midday", "Midafternoon", "Drivetime", "Evening"]
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
DRAW_RE = r"(Early\s*bird|Morning|Mid\s*day|Mid\s*afternoon|Drive\s*time|Evening)"
DATE_RE = r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?,?\s+(\d{4})"
KEEP_DAYS = 60


def fetch(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; PotStory/1.0; results for a fan site)",
        "Accept-Language": "en",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def to_text(page):
    page = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", page)
    page = re.sub(r"(?s)<[^>]+>", " ", page)
    return re.sub(r"\s+", " ", html.unescape(page))


def parse(text):
    """Walk through the text: a date sets the day, then 'Draw name' + number pairs follow."""
    out = []
    token = re.compile(DATE_RE + "|" + DRAW_RE + r"\s+(\d{1,2})\b", re.I)
    day = None
    for m in token.finditer(text):
        if m.group(1):
            try:
                day = datetime(int(m.group(3)), MONTHS[m.group(2)[:3].lower()], int(m.group(1))).date()
            except ValueError:
                day = None
        elif day and m.group(4):
            name = re.sub(r"\s", "", m.group(4)).lower()
            draw = next(d for d in DRAWS if d.lower() == name)
            n = int(m.group(5))
            if 1 <= n <= 36:
                out.append({"date": day.isoformat(), "draw": draw, "number": n})
    return out


def main():
    try:
        with open("results.json") as f:
            saved = json.load(f)
    except (FileNotFoundError, ValueError):
        saved = {"draws": []}

    found = []
    for url in SOURCES:
        try:
            found += parse(to_text(fetch(url)))
        except Exception as e:  # keep going if one page fails
            print(f"Could not read {url}: {e}")

    jm_now = datetime.now(timezone(timedelta(hours=-5)))
    today = jm_now.date().isoformat()
    merged = {(d["date"], d["draw"]): d for d in saved.get("draws", [])}
    new = 0
    for d in found:
        if d["date"] > today:
            continue
        key = (d["date"], d["draw"])
        if key not in merged:
            new += 1
        merged[key] = d

    cutoff = (jm_now.date() - timedelta(days=KEEP_DAYS)).isoformat()
    draws = sorted((d for d in merged.values() if d["date"] >= cutoff),
                   key=lambda d: (d["date"], DRAWS.index(d["draw"])))
    with open("results.json", "w") as f:
        json.dump({"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "source": "lotteryguru.com", "draws": draws}, f, indent=1)
    print(f"Done: {len(found)} draws read, {new} new, {len(draws)} saved.")


if __name__ == "__main__":
    main()
