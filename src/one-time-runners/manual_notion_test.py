import sys
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv

# Make src/ importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

import arxiv as arxiv_client
import notion_utils
from models import FilteredPaper


def main():
    print("Fetching 3 papers from arXiv cs.AI...")
    papers_raw = arxiv_client.fetch_papers("cs.AI", 3)

    papers = [
        FilteredPaper(
            arxiv_id=p.arxiv_id,
            title=p.title,
            abstract=p.abstract,
            url=p.url,
            reason="Manual test",
            is_wildcard=False,
        )
        for p in papers_raw
    ]

    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"\nPushing {len(papers)} papers to Notion (run_id={run_id})...")
    pushed = notion_utils.push_papers(papers, run_id=run_id)

    print(f"\nPushed {len(pushed)} paper(s):")
    for p in papers:
        if p.arxiv_id in pushed:
            print(f"  • {p.title}")
            print(f"    {p.url}")

    input("\n→ Open Notion, score some papers (fill in Score 1-5), then press Enter...")

    scored = notion_utils.fetch_scored_papers()
    if not scored:
        print("\nNo scored papers found.")
    else:
        print(f"\nFetched {len(scored)} scored paper(s):")
        for p in scored:
            print(f"  • [{p['score']}] {p['title']}")
            if p.get('skip_reason'):
                print(f"    skip_reason: {p['skip_reason']}")


if __name__ == "__main__":
    main()
