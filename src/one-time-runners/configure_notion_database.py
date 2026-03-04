"""Configure the Notion database schema.

Run once (or re-run) to apply the canonical schema. Before patching:
1. Archives all existing pages (clears all rows).
2. Removes all non-title properties (clean slate).
Then applies the target schema.
"""

import httpx
import json
import os
from dotenv import load_dotenv

load_dotenv()

notion_api_key = os.getenv("NOTION_API_KEY")
notion_database_id = os.getenv("NOTION_DATABASE_ID")
if not notion_api_key or not notion_database_id:
    raise RuntimeError("Missing NOTION_API_KEY or NOTION_DATABASE_ID. Set it in .env (or export it) before running.")

headers = {
    "Authorization": f"Bearer {notion_api_key}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

# ── Step 1: Archive all pages ────────────────────────────────────────────────
print("Archiving all pages...")
cursor = None
archived = 0
while True:
    body = {}
    if cursor:
        body["start_cursor"] = cursor
    resp = httpx.post(
        f"https://api.notion.com/v1/databases/{notion_database_id}/query",
        headers=headers,
        json=body,
    )
    resp.raise_for_status()
    data = resp.json()
    for page in data["results"]:
        page_id = page["id"]
        httpx.patch(
            f"https://api.notion.com/v1/pages/{page_id}",
            headers=headers,
            json={"archived": True},
        ).raise_for_status()
        archived += 1
    if not data.get("has_more"):
        break
    cursor = data["next_cursor"]
print(f"  Archived {archived} page(s).")

# ── Step 2: Remove all existing non-title properties ─────────────────────────
print("Fetching current schema...")
db = httpx.get(
    f"https://api.notion.com/v1/databases/{notion_database_id}",
    headers=headers,
).json()

removals = {
    name: None
    for name, prop in db["properties"].items()
    if prop["type"] != "title"
}
if removals:
    print(f"  Removing {len(removals)} existing property/ies: {list(removals)}")
    httpx.patch(
        f"https://api.notion.com/v1/databases/{notion_database_id}",
        headers=headers,
        json={"properties": removals},
    ).raise_for_status()
else:
    print("  No properties to remove.")

# ── Step 3: Apply target schema ───────────────────────────────────────────────
print("Applying target schema...")
r = httpx.patch(
    f"https://api.notion.com/v1/databases/{notion_database_id}",
    headers=headers,
    json={
        "properties": {
            "Short Summary": {"rich_text": {}},
            "URL": {"url": {}},
            "Abstract": {"rich_text": {}},
            "Why Selected": {"rich_text": {}},
            "Score": {"number": {"format": "number"}},
            "Skip Reason": {
                "select": {
                    "options": [
                        {"name": "off-topic", "color": "red"},
                        {"name": "low-quality", "color": "orange"},
                        {"name": "already-knew-this", "color": "gray"},
                        {"name": "never got to it", "color": "yellow"},
                    ]
                }
            },
            "Type": {
                "select": {
                    "options": [
                        {"name": "Regular", "color": "blue"},
                        {"name": "🔍 Explore", "color": "purple"},
                    ]
                }
            },
            "Run ID": {"rich_text": {}},
            "Processed": {"checkbox": {}},
        }
    },
)

print(f"Status: {r.status_code}")
print(json.dumps(r.json(), indent=2))
