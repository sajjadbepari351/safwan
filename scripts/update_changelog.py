import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    ("vacancies.json", "vacancies", "Private Vacancies"),
    ("government-vacancies.json", "vacancies", "Government Jobs"),
    ("pending-vacancies.json", "candidates", "New Leads"),
    ("linkedin-leads.json", "candidates", "LinkedIn Posts"),
]
STATE = ROOT / "new-updates-state.json"
OUTPUT = ROOT / "new-updates.json"

def read(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default

def url_of(item):
    return item.get("apply") or item.get("sourceUrl") or item.get("feedUrl") or item.get("postUrl") or ""

def department(item):
    if item.get("category"):
        return item["category"]
    text = " ".join(str(item.get(k, "")) for k in ("title", "summary", "description")).lower()
    rules = [
        ("Supply Chain", ("supply chain", "procurement", "purchase", "sourcing", "inventory", "warehouse", "logistics", "store")),
        ("Industrial Engineering", ("industrial engineer", "industrial engineering", "work study", "line balancing")),
        ("Production", ("production", "manufacturing", "plant", "process engineer")),
        ("Planning", ("planning", "ppc", "demand forecast")),
        ("Operations", ("operation", "opex")),
    ]
    for name, words in rules:
        if any(word in text for word in words):
            return name
    return "Other"

def main():
    state = read(STATE, {"seen": []})
    seen = set(state.get("seen", []))
    data = read(OUTPUT, {"items": []})
    items = data.get("items", [])
    known_updates = {url_of(x) for x in items}
    added = []
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    for filename, key, section in FILES:
        payload = read(ROOT / filename, {})
        for raw in payload.get(key, []):
            url = url_of(raw)
            if not url or url in seen:
                continue
            seen.add(url)
            record = {
                "title": raw.get("title", "Vacancy lead"),
                "company": raw.get("company", "Not stated"),
                "category": department(raw),
                "location": raw.get("location", "Not stated"),
                "salary": raw.get("salary", "Not stated"),
                "experience": raw.get("experience", "Not stated"),
                "deadline": raw.get("deadline", "Not stated"),
                "apply": raw.get("apply") or raw.get("sourceUrl") or raw.get("feedUrl") or raw.get("postUrl") or url,
                "sourceUrl": url,
                "verified": raw.get("verified") is True,
                "status": "Verified" if raw.get("verified") is True else "Pending verification",
                "section": section,
                "addedAt": now,
            }
            if url not in known_updates:
                added.append(record)
                known_updates.add(url)
    if added:
        items = added + items
    # Keep the newest 100 additions for the website's New Updates panel.
    items = items[:100]
    OUTPUT.write_text(json.dumps({"lastUpdated": now, "items": items}, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
    STATE.write_text(json.dumps({"seen": sorted(seen), "updatedAt": now}, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
    print(f"New vacancy updates recorded: {len(added)}; total retained: {len(items)}")

if __name__ == "__main__":
    main()
