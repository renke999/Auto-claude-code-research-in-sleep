"""Pilot 2b: second coder (Opus) for 50 of the pilot-2 physician-edit diffs; compares edit-type distributions
(per-answer presence of each type) between coders."""
from __future__ import annotations

import collections
import json
from pathlib import Path

import llm
from common import convo_text
from pilot2_deletions import PROMPT, TYPES, load

HERE = Path(__file__).parent


def main(n=50):
    items = load(300)[:n]
    first = {json.loads(l)["prompt_id"]: json.loads(l) for l in (HERE / "pilot2_results.jsonl").open()}
    outs = llm.call_many([PROMPT.format(convo=convo_text(r["prompt"]), orig=b, ideal=i) for r, b, i in items], "claude-opus-5-5", workers=6)
    agree = collections.defaultdict(list)
    c1, c2 = collections.Counter(), collections.Counter()
    for (r, _, _), o in zip(items, outs):
        if r["prompt_id"] not in first:
            continue
        try:
            e2 = llm.extract_json(o)["edits"]
        except Exception:
            continue
        s1 = {e.get("type") for e in first[r["prompt_id"]]["edits"]}
        s2 = {e.get("type") for e in e2}
        for t in TYPES:
            agree[t].append((t in s1) == (t in s2))
        c1.update(e.get("type") for e in first[r["prompt_id"]]["edits"]); c2.update(e.get("type") for e in e2)
    t1, t2 = sum(c1.values()), sum(c2.values())
    print(f"n={len(agree[TYPES[0]])}  (per-answer presence agreement; share of edits coder1 Sonnet / coder2 Opus)")
    for t in TYPES:
        print(f"  {t:36s} agree={sum(agree[t])/len(agree[t]):.2f}  share {c1[t]/t1:.3f} / {c2[t]/t2:.3f}")


if __name__ == "__main__":
    main()
