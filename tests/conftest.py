import json
import sys
from pathlib import Path

import pytest
import yaml

# Add src/ to sys.path so imports work without package install
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from models import FilteredPaper, Paper


@pytest.fixture
def sample_paper():
    return Paper(
        arxiv_id="2401.12345",
        title="Efficient Inference for Large Language Models",
        abstract="We present a method for reducing inference costs in LLMs by 40% through dynamic pruning.",
        url="http://arxiv.org/abs/2401.12345",
    )


@pytest.fixture
def sample_papers():
    def _make(n=3):
        papers = []
        for i in range(n):
            papers.append(
                Paper(
                    arxiv_id=f"2401.{12345 + i:05d}",
                    title=f"Paper Title {i}",
                    abstract=f"This is the abstract for paper {i} about AI research.",
                    url=f"http://arxiv.org/abs/2401.{12345 + i:05d}",
                )
            )
        return papers

    return _make


@pytest.fixture
def sample_filtered_paper():
    def _make(is_wildcard=False):
        return FilteredPaper(
            arxiv_id="2401.12345",
            title="Efficient Inference for Large Language Models",
            abstract="We present a method for reducing inference costs in LLMs by 40%.",
            url="http://arxiv.org/abs/2401.12345",
            reason="Directly relevant to efficient inference interests",
            is_wildcard=is_wildcard,
        )

    return _make


@pytest.fixture
def sample_filtered_papers():
    return [
        FilteredPaper(
            arxiv_id="2401.12345",
            title="Efficient Inference for LLMs",
            abstract="Abstract about efficient inference.",
            url="http://arxiv.org/abs/2401.12345",
            reason="Matches efficient inference interest",
            is_wildcard=False,
        ),
        FilteredPaper(
            arxiv_id="2401.12346",
            title="Novel RAG Architecture",
            abstract="Abstract about RAG systems.",
            url="http://arxiv.org/abs/2401.12346",
            reason="Matches RAG interest",
            is_wildcard=False,
        ),
        FilteredPaper(
            arxiv_id="2401.12347",
            title="Human-AI Interaction Patterns",
            abstract="Abstract about HCI with AI.",
            url="http://arxiv.org/abs/2401.12347",
            reason="Interesting exploration from cs.HC",
            is_wildcard=True,
        ),
    ]


@pytest.fixture
def sample_preferences():
    return {
        "field": "cs.AI",
        "max_results_per_run": 50,
        "max_papers_to_push": 5,
        "immutable_interests": [
            "LLM agents with tool use",
            "Efficient inference and quantization",
        ],
        "interests": [
            "RAG and retrieval systems for production use",
            "LLM fine-tuning on limited hardware",
        ],
        "avoid": [
            "Pure benchmark papers with no practical application",
            "Vision-only models unrelated to language",
        ],
        "exploration": {
            "enabled": True,
            "wildcard_count": 1,
            "adjacent_categories": ["cs.IR", "cs.HC", "stat.ML"],
        },
        "scoring_history_summary": "",
        "example_papers": [
            {
                "title": "Example Paper on Tool Use",
                "reason": "I liked this because it showed practical tool use patterns",
            }
        ],
    }


@pytest.fixture
def sample_scored_papers():
    return [
        {
            "arxiv_id": "2401.12345",
            "title": "Efficient Inference for LLMs",
            "score": 5,
            "skip_reason": None,
            "paper_type": "Regular",
        },
        {
            "arxiv_id": "2401.12346",
            "title": "Novel RAG Architecture",
            "score": 3,
            "skip_reason": None,
            "paper_type": "Regular",
        },
        {
            "arxiv_id": "2401.12347",
            "title": "Human-AI Interaction Patterns",
            "score": 4,
            "skip_reason": None,
            "paper_type": "\ud83d\udd0d Explore",
        },
    ]


@pytest.fixture
def preferences_file(tmp_path, sample_preferences):
    path = tmp_path / "preferences.yaml"
    path.write_text(yaml.dump(sample_preferences, default_flow_style=False))
    return path


@pytest.fixture
def seen_papers_file(tmp_path):
    path = tmp_path / "seen_papers.json"
    seen = ["2401.11111", "2401.22222", "2401.33333"]
    path.write_text(json.dumps(seen))
    return path
