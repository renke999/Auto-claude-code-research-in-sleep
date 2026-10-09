"""Pilot 6: controls for pilots 4 and 5.

(a) Error-finding false-positive floor: re-run the rubric-free error finder on the ORIGINAL plain answers with a
    run tag; detection rate of the noise (count increases between two runs of the same text).
(b) Holistic-judge calibration against physician edits: Sonnet pairwise (both orders) between a HealthBench physician
    ideal and the exact model reference the physician rewrote it from (pilot 2 pairs). If the judge agrees with
    physicians it should prefer the ideal; if it prefers the source reference, the judge (self-preference / style)
    or the ideals (staleness) are not a valid anchor.
"""
from __future__ import annotations

import json
import statistics as st
from pathlib import Path

import llm
from common import convo_text, load_examples
from pilot2_deletions import load as load_pairs
from pilot4_judge_scale import ERR, JUDGES
from pilot5_holistic import P as PAIR

HERE = Path(__file__).parent


def err_floor(n=60):
    bank = [json.loads(l) for l in (HERE / "bank.jsonl").open()]
    exs = {e["prompt_id"]: e for e in load_examples(150, seed=1)}
    items = [(exs[b["prompt_id"]], b["variants"]["plain"]) for b in bank if b["variants"]["numpert"]][:n]
    for m in JUDGES:
        a = llm.call_many([ERR.format(convo=convo_text(ex["prompt"]), resp=t) for ex, t in items], m, workers=8)
        b = llm.call_many([ERR.format(convo=convo_text(ex["prompt"]), resp=t) + "\n\n[independent review #2]" for ex, t in items], m, workers=8)
        d = []
        for x, y in zip(a, b):
            try:
                d.append(len(llm.extract_json(y)["errors"]) - len(llm.extract_json(x)["errors"]))
            except Exception:
                pass
        print(f"{m:20s} noise: frac count increased {sum(v > 0 for v in d)/len(d):.2f}  mean change {st.mean(d):+.2f}  n={len(d)}")


def edit_calibration(n=100):
    pairs = load_pairs(n)
    jobs, keys = [], []
    for i, (r, ref, ideal) in enumerate(pairs):
        c = convo_text(r["prompt"])
        jobs.append(PAIR.format(convo=c, a=ideal, b=ref)); keys.append((i, 0))
        jobs.append(PAIR.format(convo=c, a=ref, b=ideal)); keys.append((i, 1))
    outs = llm.call_many(jobs, "claude-sonnet-5-5", workers=8)
    per = {}
    for (i, o), out in zip(keys, outs):
        try:
            w = llm.extract_json(out)["better"]
        except Exception:
            continue
        per.setdefault(i, []).append(1.0 if ((w == "A") if o == 0 else (w == "B")) else 0.0)
    v = [st.mean(x) for x in per.values()]
    groups = {}
    for i, x in per.items():
        groups.setdefault(pairs[i][0]["ideal_completions_data"]["ideal_completions_group"], []).append(st.mean(x))
    print(f"P(physician ideal preferred over the model answer it was rewritten from) = {st.mean(v):.3f} n={len(v)}  "
          + "  ".join(f"{g}: {st.mean(x):.3f} (n={len(x)})" for g, x in sorted(groups.items())))


if __name__ == "__main__":
    err_floor()
    edit_calibration()
