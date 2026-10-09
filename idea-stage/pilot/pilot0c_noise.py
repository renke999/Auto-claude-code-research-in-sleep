"""Pilot 0c: judge test-retest noise control for pilot 0b.

Re-grades the ORIGINAL (unperturbed) responses from pilot 0b with a
different run tag, so Δ(rerun − orig) gives the noise floor against which
Δ(perturbed − orig) should be compared.
"""
from __future__ import annotations

import json
import random
import statistics as st

import llm
from common import judge_prompt, load_examples, parse_met, score
from pilot0_susceptibility import gen_prompt
from pilot0b_numeric import perturb

JUDGE = "claude-haiku-5-5"


def main(n=120):
    exs = load_examples(n)
    rng = random.Random(0)
    base = llm.call_many([gen_prompt(e, "plain") for e in exs], "claude-haiku-5-5", workers=12)
    pairs = []
    for e, b in zip(exs, base):
        for src, txt in (("plain", b), ("ideal", e["ideal_completions_data"]["ideal_completion"])):
            p, k = perturb(txt, rng)
            if p:
                pairs.append((e, src, txt))
    orig = llm.call_many([judge_prompt(e, t) for e, _, t in pairs], JUDGE, workers=12)
    rerun = llm.call_many([judge_prompt(e, t) + "\n\n(independent grading run #2)" for e, _, t in pairs], JUDGE, workers=12)
    res = {}
    for (e, src, _), a, b in zip(pairs, orig, rerun):
        ma, mb = parse_met(a, len(e["rubrics"])), parse_met(b, len(e["rubrics"]))
        if ma is None or mb is None:
            continue
        res.setdefault(src, []).append(score(e["rubrics"], mb) - score(e["rubrics"], ma))
    pert = [json.loads(l) for l in open("pilot0b_results.jsonl")]
    for src, d in res.items():
        pd = [x["pert"] - x["orig"] for x in pert if x["src"] == src]
        print(f"{src}: noise Δ mean={st.mean(d):+.3f} sd={st.stdev(d):.3f} |Δ|={st.mean(abs(x) for x in d):.3f} frac0={sum(x == 0 for x in d)/len(d):.2f}  "
              f"| perturbation Δ mean={st.mean(pd):+.3f} sd={st.stdev(pd):.3f}")


if __name__ == "__main__":
    main()
