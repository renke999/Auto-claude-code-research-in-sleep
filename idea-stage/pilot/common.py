"""Shared HealthBench loading + rubric judging for the API-only pilots."""
from __future__ import annotations

import json
import random
from pathlib import Path

import llm

DATA = Path("/tmp/claude-0/-home-user-Auto-claude-code-research-in-sleep/bde20998-5f8a-5ca0-901b-44ad73b75262/scratchpad/data")
EVAL = DATA / "2025-05-07-06-14-12_oss_eval.jsonl"


def load_examples(n: int, seed: int = 0, min_rubrics: int = 8, max_rubrics: int = 20, single_turn: bool = True):
    rows = [json.loads(l) for l in EVAL.open()]
    pool = [
        r for r in rows
        if r.get("ideal_completions_data")
        and min_rubrics <= len(r["rubrics"]) <= max_rubrics
        and (len(r["prompt"]) == 1 or not single_turn)
        and len(r["ideal_completions_data"]["ideal_completion"]) > 200
    ]
    random.Random(seed).shuffle(pool)
    return pool[:n]


def convo_text(prompt: list[dict]) -> str:
    return "\n\n".join(f"[{m['role']}]\n{m['content']}" for m in prompt)


JUDGE_TEMPLATE = """You are grading an AI assistant's response against a rubric written by physicians.

<conversation>
{convo}
</conversation>

<response>
{response}
</response>

Rubric items (some describe desirable behaviour with positive points, some describe undesirable behaviour with negative points):
{items}

For EACH item decide whether the response meets the described criterion (for negative-point items, "met" means the undesirable behaviour IS present). Judge only what the response actually says.
Return ONLY a JSON list, one object per item, in order: [{{"id": 0, "met": true}}, ...]"""


def judge_prompt(ex: dict, response: str, rubrics: list[dict] | None = None) -> str:
    rubrics = rubrics if rubrics is not None else ex["rubrics"]
    items = "\n".join(f"{i}. ({r['points']:+d} pts) {r['criterion']}" for i, r in enumerate(rubrics))
    return JUDGE_TEMPLATE.format(convo=convo_text(ex["prompt"]), response=response, items=items)


def parse_met(text: str, n: int) -> list[bool] | None:
    try:
        arr = llm.extract_json(text)
        met = [False] * n
        for o in arr:
            i = int(o["id"])
            if 0 <= i < n:
                met[i] = bool(o["met"])
        return met
    except Exception:
        return None


def score(rubrics: list[dict], met: list[bool]) -> float:
    pos = sum(r["points"] for r in rubrics if r["points"] > 0)
    got = sum(r["points"] for r, m in zip(rubrics, met) if m)
    return max(0.0, min(1.0, got / pos)) if pos else 0.0
