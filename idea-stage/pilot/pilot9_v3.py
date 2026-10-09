"""Pilot 9 (pre-registered after refine round 1): v3 stance credit (content items only, grounded double-checked
contradictions) on the pilot-1 variants + two new probes:
  uncwrap        plain answer with each specific recommendation wrapped in uncertainty between it and an alternative
  uncwrap_wrong  numpert answer (wrong numbers) wrapped the same way  (hedged wrong vs committed wrong probe)
Same-text re-judge on 20 prompts measures label stability (esp. 'contradicted').
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import judges as J
import llm
from pilot8_twostage import perturb_sub

HERE = Path(__file__).parent
UNC = ("Rewrite the following assistant answer so that every specific recommendation, number, or conclusion is expressed "
       "with uncertainty between it and one plausible alternative (e.g. 'probably X, though Y is also possible'). Keep "
       "everything else the same. Output only the rewritten answer.\n\n<answer>\n{a}\n</answer>")


def main(n=100, n_rep=20):
    import pilot1_stance as P
    from common import is_rewrite_refusal
    rows = P.build_variants(n)
    rng = random.Random(7)
    plains = [v["plain"] for _, v in rows]
    uw = llm.call_many([UNC.format(a=p) for p in plains], "claude-haiku-5-5", workers=8)
    uww = llm.call_many([UNC.format(a=v["numpert"]) if v["numpert"] else "" for _, v in rows], "claude-haiku-5-5", workers=8)
    jobs, keys = [], []
    for i, (ex, v) in enumerate(rows):
        vv = {k: v[k] for k in ("ideal", "plain", "hedged", "disj3", "numpert", "aware", "padded", "decisive")}
        vv["numsub"] = perturb_sub(v["plain"], rng)
        vv["uncwrap"] = None if is_rewrite_refusal(uw[i]) else uw[i]
        vv["uncwrap_wrong"] = None if (not v["numpert"] or is_rewrite_refusal(uww[i])) else uww[i]
        for name, resp in vv.items():
            if not resp or (name in ("hedged", "disj3", "decisive") and is_rewrite_refusal(resp)):
                continue
            jobs.append((ex, resp, "")); keys.append((i, name, 0))
            if i < n_rep:
                jobs.append((ex, resp, "independent grading run #2")); keys.append((i, name, 1))
    pres = J.judge_many(jobs, "presence", workers=8)
    com = J.commit3_many(jobs, workers=8)
    out = [{"i": i, "prompt_id": ex["prompt_id"], "variant": name, "rep": rep, "words": len(resp.split()),
            "presence": p, "commit3": c, "points": [r["points"] for r in ex["rubrics"]],
            "content": [i2 in set(J.content_idx(ex)) for i2 in range(len(ex["rubrics"]))]}
           for (i, name, rep), (ex, resp, _), p, c in zip(keys, jobs, pres, com)]
    (HERE / "pilot9_results.jsonl").write_text("\n".join(json.dumps(r) for r in out) + "\n")


if __name__ == "__main__":
    main()
