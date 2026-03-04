"""Option A (httpx): Rename the existing 'Name' title column to 'Title'."""

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

r = httpx.patch(
    f"https://api.notion.com/v1/databases/{notion_database_id}",
    headers=headers,
    json={
        "properties": {
            "Name": {"name": "Title", "title": {}},
            "URL": {"url": {}},
            "Abstract": {"rich_text": {}},
            "Reason": {"rich_text": {}},
            "Score": {"number": {"format": "number"}},
            "Skip Reason": {
                "select": {
                    "options": [
                        {"name": "off-topic", "color": "red"},
                        {"name": "low-quality", "color": "orange"},
                        {"name": "already-knew-this", "color": "gray"},
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
            "Scored": {"checkbox": {}},
        }
    },
)

print(f"Status: {r.status_code}")
print(json.dumps(r.json(), indent=2))