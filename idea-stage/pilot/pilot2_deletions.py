"""Pilot 2 (idea I10): what do physicians delete / change when rewriting model answers into HealthBench ideals?

For Group 2/3 examples, take the reference completion most similar to the physician ideal (difflib ratio),
then ask Sonnet to align atomic claims and type every edit. Output: an edit taxonomy with counts, plus the
deleted claims (raw material for deletion-derived negative criteria).
"""
from __future__ import annotations

import collections
import json
import random
import statistics as st
from pathlib import Path

import llm
from common import EVAL, convo_text

HERE = Path(__file__).parent
MODEL = "claude-sonnet-5-5"

TYPES = ["hedge_or_alternatives_removed", "padding_or_unrequested_removed", "wrong_or_unsafe_specific_corrected",
         "redundancy_removed", "overconfidence_softened", "action_or_specific_added", "context_question_added",
         "tailoring_added", "style_or_format_only", "other"]

PROMPT = """A physician rewrote an AI model's answer into an improved "ideal" answer for the conversation below.
Compare ORIGINAL (model) and REWRITE (physician) at the level of atomic claims/recommendations and list EVERY substantive edit.

<conversation>
{convo}
</conversation>

<original>
{orig}
</original>

<rewrite>
{ideal}
</rewrite>

Edit types:
- hedge_or_alternatives_removed: the original offered several options / hedged; the rewrite commits to one or drops the alternatives
- padding_or_unrequested_removed: content the user did not need (generic advice, boilerplate, tangents) was deleted
- wrong_or_unsafe_specific_corrected: a factually wrong, outdated, or unsafe specific (dose, threshold, timing, claim) was corrected or removed
- redundancy_removed: repeated content was deleted
- overconfidence_softened: an overconfident claim was qualified
- action_or_specific_added: a concrete action, number, or specific recommendation was added
- context_question_added: the rewrite asks the user for missing context
- tailoring_added: content adapted to this user's situation was added
- style_or_format_only: wording/format/tone only, no change in content
- other

Return ONLY JSON: {{"edits": [{{"type": "<one type>", "original_text": "<short quote or empty>", "rewrite_text": "<short quote or empty>"}}], "length_change": "shorter|similar|longer"}}"""


def load(n, seed=0):
    rows = [json.loads(l) for l in EVAL.open()]
    random.Random(seed).shuffle(rows)
    pool = []
    for r in rows:
        if len(pool) >= n:
            break
        d = r.get("ideal_completions_data")
        if not d or d.get("ideal_completions_group") not in ("Group 2", "Group 3"):
            continue
        refs = d.get("ideal_completions_ref_completions") or []
        if not refs:
            continue
        ideal = d["ideal_completion"]
        iw = set(ideal.lower().split())
        best = max(refs, key=lambda x: len(iw & set(x.lower().split())) / (len(iw | set(x.lower().split())) or 1))
        pool.append((r, best, ideal))
    return pool


def main(n=300):
    items = load(n)
    outs = llm.call_many([PROMPT.format(convo=convo_text(r["prompt"]), orig=b, ideal=i) for r, b, i in items], MODEL, workers=8)
    res = []
    for (r, b, i), o in zip(items, outs):
        try:
            j = llm.extract_json(o)
        except Exception:
            continue
        res.append({"prompt_id": r["prompt_id"], "group": r["ideal_completions_data"]["ideal_completions_group"],
                    "orig_words": len(b.split()), "ideal_words": len(i.split()), "edits": j.get("edits", []),
                    "length_change": j.get("length_change")})
    (HERE / "pilot2_results.jsonl").write_text("\n".join(json.dumps(x) for x in res) + "\n")
    c = collections.Counter(e.get("type") for x in res for e in x["edits"])
    tot = sum(c.values())
    print(f"n={len(res)} edits={tot} per_answer={tot/len(res):.1f}")
    for t in TYPES:
        print(f"  {t:36s} {c.get(t,0):5d}  {c.get(t,0)/tot:.3f}  prompts_with={sum(any(e.get('type')==t for e in x['edits']) for x in res)/len(res):.2f}")
    print("length_change", collections.Counter(x["length_change"] for x in res))
    print("words orig/ideal median", st.median(x["orig_words"] for x in res), st.median(x["ideal_words"] for x in res))


if __name__ == "__main__":
    main()
