"""Pilot 1 (top idea I1 + diagnostics I3/I2/I7): presence credit vs stance (commitment-proper) credit.

Stage A (variants, 100 bank prompts): ideal, plain, generic, blist, aware, hedged, padded, numpert,
  plus k-disjunction rewrites of plain (k = 1, 3, 9 extra alternatives at every decision point)
  and 'decisive' (ideal reduced to its 1-3 core committed recommendations; probes the silence risk).
  Each variant is judged by (i) the status-quo presence judge and (ii) the stance judge, chunked <=4 items/call.
  A replicate of both judges on 30 prompts gives the noise floor and stance-label agreement.
Stage B (physician BoN-4, 200 meta-eval pools): pick the best of the 4 physician-labelled completions with
  presence vs stance credit; compare picked-completion physician gold and pairwise concordance.
"""
from __future__ import annotations

import json
import random
import statistics as st
import sys
from pathlib import Path

import judges as J
import llm
from common import load_examples
from metaeval import load_pools

HERE = Path(__file__).parent
GEN = "claude-haiku-5-5"

DISJ = (
    "Rewrite the following assistant answer. At EVERY point where it makes a recommendation, conclusion, or "
    "next step, keep that recommendation but present it together with exactly {k} other plausible alternative(s), "
    "e.g. 'X, or alternatively Y' / 'options include X, Y, Z ...', without saying which option is best. Change "
    "nothing else. Output only the rewritten answer.\n\n<answer>\n{a}\n</answer>"
)
DECISIVE = (
    "Reduce the following physician-written answer to only its 1-3 most important definitive recommendations, in at "
    "most 3 short sentences. Delete all explanation, caveats, background, and secondary advice. Do not add anything. "
    "Output only the reduced answer.\n\n<answer>\n{a}\n</answer>"
)


def build_variants(n):
    bank = [json.loads(l) for l in (HERE / "bank.jsonl").open()][:n]
    exs = {e["prompt_id"]: e for e in load_examples(150, seed=1)}
    plains = [b["variants"]["plain"] for b in bank]
    extra = {}
    for k in (1, 3, 9):
        outs = llm.call_many([DISJ.format(k=k, a=p) for p in plains], GEN, workers=16)
        extra[f"disj{k}"] = outs
    extra["decisive"] = llm.call_many([DECISIVE.format(a=b["variants"]["ideal"]) for b in bank], GEN, workers=16)
    rows = []
    for i, b in enumerate(bank):
        v = dict(b["variants"])
        for k, outs in extra.items():
            v[k] = outs[i]
        rows.append((exs[b["prompt_id"]], v))
    return rows


def stage_a(n=100, n_rep=20):
    rows = build_variants(n)
    jobs, keys = [], []
    for i, (ex, v) in enumerate(rows):
        for name, resp in v.items():
            jobs.append((ex, resp, ""))
            keys.append((i, name, 0))
            if i < n_rep:
                jobs.append((ex, resp, "independent grading run #2"))
                keys.append((i, name, 1))
    pres = J.judge_many(jobs, "presence", workers=20)
    stan = J.judge_many(jobs, "stance", workers=20)
    out = []
    for (i, name, rep), (ex, resp, _), p, s in zip(keys, jobs, pres, stan):
        out.append({"i": i, "prompt_id": ex["prompt_id"], "variant": name, "rep": rep, "words": len(resp.split()),
                    "presence": p, "stance": s, "points": [r["points"] for r in ex["rubrics"]]})
    (HERE / "pilot1a_results.jsonl").write_text("\n".join(json.dumps(r) for r in out) + "\n")


def stage_b(n=200):
    pools = load_pools(n, seed=3, min_spread=0.01)
    jobs, keys = [], []
    for pi, p in enumerate(pools):
        for cid, txt in p["completions"].items():
            jobs.append((p["ex"], txt, ""))
            keys.append((pi, cid))
    pres = J.judge_many(jobs, "presence", workers=20)
    stan = J.judge_many(jobs, "stance", workers=20)
    out = []
    for (pi, cid), (ex, _, _), pv, sv in zip(keys, jobs, pres, stan):
        out.append({"pool": pi, "prompt_id": ex["prompt_id"], "cid": cid, "gold": pools[pi]["gold"][cid],
                    "presence": pv, "stance": sv, "points": [r["points"] for r in ex["rubrics"]]})
    (HERE / "pilot1b_results.jsonl").write_text("\n".join(json.dumps(r) for r in out) + "\n")


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "ab"
    if "a" in which:
        stage_a()
    if "b" in which:
        stage_b()
