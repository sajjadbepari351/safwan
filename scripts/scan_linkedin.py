#!/usr/bin/env python3
"""Public search-index discovery only; no LinkedIn login, scraping, or access bypass."""
import datetime as dt
import email.utils
import html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "linkedin-leads.json"
QUERIES = [
    "site:linkedin.com/posts Bangladesh hiring production jobs",
    "site:linkedin.com/posts Bangladesh hiring supply chain procurement",
    "site:linkedin.com/posts Bangladesh hiring planning PPC operations",
    "site:linkedin.com/posts Bangladesh hiring industrial engineering manufacturing",
    "site:linkedin.com/posts Dhaka Gazipur Savar Narayanganj production supply chain vacancy",
]
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CareerRadarBD/1.0)"}

def clean(value):
    value = html.unescape(re.sub(r"<[^>]+>", " ", value or ""))
    return re.sub(r"\s+", " ", value).strip()

def direct_post(url):
    try:
        p = urllib.parse.urlparse(url)
        host = (p.hostname or "").lower()
        path = p.path.lower()
        return (host == "linkedin.com" or host.endswith(".linkedin.com")) and ("/posts/" in path or "/feed/update/" in path)
    except Exception:
        return False

def fetch(query):
    url = "https://www.bing.com/search?" + urllib.parse.urlencode({"q": query, "format": "rss"})
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=25) as response:
        root = ET.fromstring(response.read())
    return root.findall(".//item")

def parsed_date(value):
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.isoformat()
    except Exception:
        return "Date not supplied by search index"

def main():
    found, successful, errors = {}, 0, []
    for query in QUERIES:
        try:
            items = fetch(query)
            successful += 1
            for item in items:
                title = clean(item.findtext("title"))
                url = clean(item.findtext("link"))
                summary = clean(item.findtext("description"))
                if not title or not direct_post(url):
                    continue
                key = url.split("?")[0].rstrip("/")
                found[key] = {
                    "title": title[:220], "company": "", "location": "",
                    "summary": summary[:650] or "Publicly indexed LinkedIn hiring post. Check the original post for full details.",
                    "postUrl": key, "publishedAt": parsed_date(item.findtext("pubDate")),
                    "status": "pending_manual_verification",
                    "reason": "Found through public search indexing only. Confirm employer, requirements, location, deadline and application route."
                }
        except Exception as exc:
            errors.append(str(exc)[:180])

    # Retain existing direct post leads if search temporarily returns no results.
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
            for item in old.get("candidates", []):
                url = item.get("postUrl") or item.get("url") or ""
                if direct_post(url):
                    found.setdefault(url.split("?")[0].rstrip("/"), item)
        except Exception:
            pass

    candidates = list(found.values())
    candidates.sort(key=lambda x: x.get("publishedAt", ""), reverse=True)
    payload = {
        "candidates": candidates[:40],
        "lastChecked": dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
        "feedsChecked": successful,
        "feedSource": "Bing public RSS search; direct LinkedIn post URLs only",
        "scanErrors": errors[:3]
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Checked %s/%s feeds; retained %s public LinkedIn post leads." % (successful, len(QUERIES), len(payload["candidates"])))
    if successful == 0:
        raise SystemExit("All public search feeds failed.")

if __name__ == "__main__":
    main()
