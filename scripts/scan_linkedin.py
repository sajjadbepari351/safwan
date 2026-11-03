#!/usr/bin/env python3
"""Discover public Bangladesh vacancy links from search-index RSS feeds.

This is discovery, not verification: it never logs into LinkedIn, scrapes gated
pages, or promotes a lead to a verified vacancy. Human/source review is required.
"""
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
LINKEDIN_OUT = ROOT / "linkedin-leads.json"
PENDING_OUT = ROOT / "pending-vacancies.json"
QUERIES = [
    "site:linkedin.com/posts Bangladesh hiring production manufacturing jobs",
    "site:linkedin.com/posts Bangladesh hiring supply chain procurement",
    "site:linkedin.com/posts Bangladesh hiring planning PPC operations",
    "site:linkedin.com/posts Bangladesh hiring industrial engineering IE",
    "site:linkedin.com/posts Dhaka Gazipur Savar Narayanganj vacancy engineer",
    "site:thecvguy.net/jobs-and-careertips Bangladesh MNC production manufacturing planning supply chain",
    "site:bdrecruit.net Bangladesh production manufacturing planning supply chain vacancy",
    "site:facebook.com/groups Bangladesh jobs production manufacturing supply chain planning vacancy",
    "site:facebook.com Bangladesh MNC job circular production engineering supply chain",
    "Bangladesh vacancy production planning supply chain site:chakri.app OR site:jobs.com.bd OR site:myjobs.com.bd OR site:skill.jobs",
    "Bangladesh vacancy manufacturing engineering production site:jagojobs.com OR site:nrbjobs.com OR site:bdjobstoday.com",
    "Bangladesh production engineer OR executive vacancy Dhaka Gazipur Savar",
    "Bangladesh supply chain OR procurement OR planning officer executive vacancy",
    "Bangladesh industrial engineering OR IE executive vacancy manufacturing",
    "site:bdjobs.com/h/details Bangladesh production OR planning OR supply chain",
    "site:dohaj.com/job-details Bangladesh production OR supply chain OR industrial engineering",
]
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CareerRadarBD/1.1; +https://sajjadbepari351.github.io/safwan/)"}
ALLOWED_JOB_HOSTS = ("bdjobs.com", "dohaj.com", "jobmedia.com.bd", "careerjet.com.bd", "thecvguy.net", "bdrecruit.net", "jobs.com.bd", "job.com.bd", "myjobs.com.bd", "chakri.app", "skill.jobs", "nrbjobs.com", "bdjobstoday.com", "jagojobs.com", "bikroy.com", "youthop.com", "uncareer.net", "onlinejobbd.com", "chakrirkhobor.net", "bdgovtjobs.com", "teletalk.com.bd")
NOW = dt.datetime.now(dt.timezone.utc).astimezone()

def clean(value):
    value = html.unescape(re.sub(r"<[^>]+>", " ", value or ""))
    return re.sub(r"\s+", " ", value).strip()

def canonical(url):
    try:
        p = urllib.parse.urlsplit(url)
        if p.scheme not in ("http", "https") or not p.hostname:
            return ""
        host = p.hostname.lower()
        if host.endswith("bing.com") or host.endswith("google.com") or host.endswith("news.google.com"):
            return ""
        return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path.rstrip("/"), "", ""))
    except Exception:
        return ""

def is_linkedin_post(url):
    try:
        p = urllib.parse.urlsplit(url)
        host, path = (p.hostname or "").lower(), p.path.lower()
        return (host == "linkedin.com" or host.endswith(".linkedin.com")) and ("/posts/" in path or "/feed/update/" in path)
    except Exception:
        return False

def is_public_facebook_post(url):
    """Accept only publicly indexed post/permalink URLs, never private group content."""
    try:
        p = urllib.parse.urlsplit(url)
        host, path = (p.hostname or "").lower(), p.path.lower()
        if not (host == "facebook.com" or host.endswith(".facebook.com")):
            return False
        return ("/posts/" in path or "/permalink/" in path or
                path.startswith("/permalink.php") or path.startswith("/story.php"))
    except Exception:
        return False

def is_job_result(url):
    try:
        host = (urllib.parse.urlsplit(url).hostname or "").lower()
        return any(host == d or host.endswith("." + d) for d in ALLOWED_JOB_HOSTS)
    except Exception:
        return False

def fetch(query):
    url = "https://www.bing.com/search?" + urllib.parse.urlencode({"q": query, "format": "rss", "count": "30"})
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=25) as response:
        raw = response.read()
    root = ET.fromstring(raw)
    if root.tag.lower().endswith("html"):
        raise ValueError("Search endpoint returned HTML, not RSS")
    return root.findall(".//item")

def parsed_date(value):
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.isoformat()
    except Exception:
        return ""

def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def main():
    linkedin, pending = {}, {}
    old_li = read_json(LINKEDIN_OUT, {"candidates": []})
    old_pending = read_json(PENDING_OUT, {"candidates": []})
    for item in old_li.get("candidates", []):
        url = canonical(item.get("postUrl") or item.get("url") or "")
        if url and is_linkedin_post(url):
            linkedin[url] = item
    for item in old_pending.get("candidates", []):
        url = canonical(item.get("sourceUrl") or item.get("feedUrl") or item.get("postUrl") or "")
        if url:
            pending[url] = item

    successful, errors = 0, []
    for query in QUERIES:
        try:
            items = fetch(query)
            successful += 1
            for item in items:
                title = clean(item.findtext("title"))
                raw_url = clean(item.findtext("link"))
                url = canonical(raw_url)
                summary = clean(item.findtext("description"))
                if not title or not url:
                    continue
                published = parsed_date(item.findtext("pubDate"))
                if is_linkedin_post(url):
                    linkedin.setdefault(url, {
                        "title": title[:220], "company": "", "location": "",
                        "summary": summary[:700] or "Publicly indexed LinkedIn hiring post. Check the original post for full details.",
                        "postUrl": url, "publishedAt": published or "Date not supplied by search index",
                        "status": "pending_manual_verification",
                        "reason": "Found through public search indexing only. Confirm employer, requirements, location, deadline and application route."
                    })
                elif is_public_facebook_post(url):
                    pending.setdefault(url, {
                        "title": title[:220], "company": "", "location": "",
                        "summary": summary[:700] or "Publicly indexed Facebook vacancy post. Open the original post to confirm details.",
                        "source": "Facebook public post",
                        "sourceUrl": url, "feedUrl": url,
                        "publishedAt": published or "Date not supplied by search index",
                        "status": "pending_manual_verification",
                        "reason": "Discovered from public search indexing only. Private groups and login-restricted content are not accessed; verify the original post and employer before applying."
                    })
                elif is_job_result(url):
                    pending.setdefault(url, {
                        "title": title[:220], "company": "", "location": "",
                        "summary": summary[:700] or "Publicly indexed vacancy result. Check the source page for full details.",
                        "source": urllib.parse.urlsplit(url).hostname,
                        "sourceUrl": url, "feedUrl": url,
                        "publishedAt": published or "Date not supplied by search index",
                        "status": "pending_manual_verification",
                        "reason": "Discovered through public search indexing. Confirm that the vacancy is still open and check employer, IPE eligibility, experience, salary and deadline."
                    })
        except Exception as exc:
            errors.append((query[:75] + ": " + str(exc))[:220])

    # Do not replace good existing data if every search feed fails.
    if successful == 0:
        raise SystemExit("All public search feeds failed; existing lead files were left unchanged. " + " | ".join(errors[:2]))

    # Keep a bounded, deduplicated lead list. Do not auto-verify or auto-publish.
    li_items = sorted(linkedin.values(), key=lambda x: x.get("publishedAt", ""), reverse=True)[:50]
    pending_items = sorted(pending.values(), key=lambda x: x.get("publishedAt", ""), reverse=True)[:50]
    checked = NOW.isoformat(timespec="seconds")
    common = {"lastChecked": checked, "feedsChecked": successful, "feedsAttempted": len(QUERIES),
              "feedSource": "Bing public RSS search index; no LinkedIn login or gated-page scraping",
              "scanErrors": errors[:5]}
    LINKEDIN_OUT.write_text(json.dumps({"candidates": li_items, **common}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    PENDING_OUT.write_text(json.dumps({"candidates": pending_items, **common}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Successful feeds: %s/%s; LinkedIn leads: %s; other job-board leads: %s" %
          (successful, len(QUERIES), len(li_items), len(pending_items)))

if __name__ == "__main__":
    main()
