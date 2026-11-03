import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "sources.json"
PENDING = ROOT / "pending-vacancies.json"
MAX_ITEMS = 200
KEYWORDS = re.compile(r"production|manufactur|planning|PPC|supply chain|industrial engineer|industrial engineering|IPE|opex|operation|process improvement|lean|quality|QA|QC|procurement|purchase|sourcing|logistics|warehouse|inventory|store|maintenance|engineering|factory|plant", re.I)


def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def fetch_feed(url):
    request = urllib.request.Request(url, headers={"User-Agent": "CareerRadarBD/1.0 (RSS vacancy discovery)"})
    with urllib.request.urlopen(request, timeout=25) as response:
        return ET.fromstring(response.read())


def clean(value):
    return re.sub(r"\s+", " ", value or "").strip()


def main():
    config = read_json(SOURCES, {"feeds": []})
    old = read_json(PENDING, {"candidates": []})
    by_url = {(item.get("feedUrl") or item.get("sourceUrl") or item.get("postUrl")): item for item in old.get("candidates", []) if (item.get("feedUrl") or item.get("sourceUrl") or item.get("postUrl"))}
    checked = []
    errors = []

    for feed_url in config.get("feeds", []):
        try:
            root = fetch_feed(feed_url)
            checked.append(feed_url)
            for node in root.findall(".//item"):
                title = clean(node.findtext("title"))
                link = clean(node.findtext("link"))
                description = clean(node.findtext("description"))
                pub_date = clean(node.findtext("pubDate"))
                if not title or not link or not KEYWORDS.search(title + " " + description):
                    continue
                key = link
                by_url[key] = {
                    "title": title,
                    "feedUrl": link,
                    "feedSource": "Google News RSS",
                    "publishedAt": pub_date or None,
                    "summary": re.sub(r"<[^>]+>", " ", description)[:600],
                    "status": "pending_manual_verification",
                    "verified": False
                }
        except Exception as exc:
            errors.append({"feed": feed_url, "error": str(exc)[:250]})

    candidates = sorted(
        by_url.values(),
        key=lambda x: x.get("publishedAt") or "",
        reverse=True
    )[:MAX_ITEMS]

    output = {
        "lastChecked": datetime.now(timezone.utc).isoformat(),
        "feedsChecked": len(checked),
        "feedErrors": errors,
        "note": "RSS results are discovery leads only. They are not verified vacancies and are never published to vacancies.json automatically.",
        "candidates": candidates
    }
    PENDING.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Checked {len(checked)} feeds; retained {len(candidates)} discovery candidates; {len(errors)} feed errors.")


if __name__ == "__main__":
    main()
