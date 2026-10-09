"""Pilot 8 (pre-registered after review round 1): corrected two-stage stance credit.

Stage A' (variants, same 100 prompts as pilot 1): presence verdicts reused from pilot 1 (lean cache) + new COMMIT
  stage on positive items; adds 'numsub' (subtler x1.5 or /1.5 numeric errors) and a same-text re-judge floor
  (20 prompts, both stages, tagged run #2).
Stage B' (physician BoN-4, 1000 meta-eval pools, seed 5): presence + COMMIT, written incrementally per batch of 100.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import judges as J
from metaeval import load_pools
from pilot0b_numeric import NUM

HERE = Path(__file__).parent


def perturb_sub(text, rng, k=3):
    spans = list(NUM.finditer(text or ""))
    if not spans:
        return None
    for m in sorted(rng.sample(spans, min(k, len(spans))), key=lambda m: m.start(), reverse=True):
        v = float(m.group(1)); nv = v * 1.5 if rng.random() < 0.5 else v / 1.5
        s = f"{nv:.0f}" if nv >= 10 or float(nv).is_integer() else f"{nv:.1f}"
        text = text[:m.start()] + s + text[m.end():]
    return text


def stage_a(n=100, n_rep=20):
    import pilot1_stance as P
    rows = P.build_variants(n)
    rng = random.Random(7)
    jobs, keys = [], []
    for i, (ex, v) in enumerate(rows):
        v = dict(v)
        v["numsub"] = perturb_sub(v["plain"], rng)
        for name, resp in v.items():
            if not resp:
                continue
            jobs.append((ex, resp, "")); keys.append((i, name, 0))
            if i < n_rep:
                jobs.append((ex, resp, "independent grading run #2")); keys.append((i, name, 1))
    pres = J.judge_many(jobs, "presence", workers=10)
    com = J.commit_many(jobs, workers=10)
    out = [{"i": i, "prompt_id": ex["prompt_id"], "variant": name, "rep": rep, "words": len(resp.split()),
            "presence": p, "commit": c, "points": [r["points"] for r in ex["rubrics"]]}
           for (i, name, rep), (ex, resp, _), p, c in zip(keys, jobs, pres, com)]
    (HERE / "pilot8a_results.jsonl").write_text("\n".join(json.dumps(r) for r in out) + "\n")


def stage_b(n=1000, batch=100):
    pools = load_pools(n, seed=5, min_spread=0.0)
    path = HERE / "pilot8b_results.jsonl"
    done = set()
    if path.exists():
        done = {json.loads(l)["pool"] for l in path.open()}
    for s in range(0, len(pools), batch):
        idx = [pi for pi in range(s, min(s + batch, len(pools))) if pi not in done]
        if not idx:
            continue
        jobs, keys = [], []
        for pi in idx:
            for cid, txt in pools[pi]["completions"].items():
                jobs.append((pools[pi]["ex"], txt, "")); keys.append((pi, cid))
        pres = J.judge_many(jobs, "presence", workers=10)
        com = J.commit_many(jobs, workers=10)
        with path.open("a") as f:
            for (pi, cid), (ex, _, _), p, c in zip(keys, jobs, pres, com):
                cats = sorted({k for k in pools[pi]["gold"]})
                f.write(json.dumps({"pool": pi, "prompt_id": ex["prompt_id"], "cid": cid, "gold": pools[pi]["gold"][cid],
                                    "clusters": pools[pi].get("clusters"), "presence": p, "commit": c,
                                    "points": [r["points"] for r in ex["rubrics"]]}) + "\n")
        print(f"batch {s//batch} done", flush=True)


if __name__ == "__main__":
    w = sys.argv[1] if len(sys.argv) > 1 else "ab"
    if "a" in w:
        stage_a()
    if "b" in w:
        stage_b()
