"""Pilot 0b: is a per-item rubric judge sensitive to wrong specifics?

The LLM generator refuses to write deliberately wrong medical content, so we
perturb numbers programmatically: in each response, up to 3 numeric tokens
(doses, thresholds, durations, percentages) are scaled by x3 or /3. We then
compare rubric scores of original vs perturbed responses.
"""
from __future__ import annotations

import json
import random
import re
import statistics as st
from pathlib import Path

import llm
from common import judge_prompt, load_examples, parse_met, score
from pilot0_susceptibility import gen_prompt

JUDGE = "claude-haiku-5-5"
NUM = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(?=\s?(?:mg|mcg|g|ml|mL|%|hours?|days?|weeks?|minutes?|years?|times|mmHg|mmol|kg|cm|IU|units|°)\b)")


def perturb(text: str, rng: random.Random, k: int = 3):
    spans = list(NUM.finditer(text))
    if len(spans) < 1:
        return None, 0
    chosen = sorted(rng.sample(spans, min(k, len(spans))), key=lambda m: m.start(), reverse=True)
    for m in chosen:
        v = float(m.group(1))
        nv = v * 3 if rng.random() < 0.5 else v / 3
        s = f"{nv:.0f}" if nv >= 10 or float(nv).is_integer() else f"{nv:.1f}"
        text = text[: m.start()] + s + text[m.end():]
    return text, len(chosen)


def main(n=120):
    exs = load_examples(n)
    rng = random.Random(0)
    base = llm.call_many([gen_prompt(e, "plain") for e in exs], "claude-haiku-5-5", workers=12)
    pairs = []
    for e, b in zip(exs, base):
        for src, txt in (("plain", b), ("ideal", e["ideal_completions_data"]["ideal_completion"])):
            p, k = perturb(txt, rng)
            if p:
                pairs.append((e, src, txt, p, k))
    prompts = [judge_prompt(e, t) for e, _, t, _, _ in pairs] + [judge_prompt(e, p) for e, _, _, p, _ in pairs]
    outs = llm.call_many(prompts, JUDGE, workers=12)
    m = len(pairs)
    res = []
    for i, (e, src, t, p, k) in enumerate(pairs):
        a = parse_met(outs[i], len(e["rubrics"]))
        b = parse_met(outs[m + i], len(e["rubrics"]))
        if a is None or b is None:
            continue
        res.append({"prompt_id": e["prompt_id"], "src": src, "k": k, "orig": score(e["rubrics"], a), "pert": score(e["rubrics"], b)})
    Path(__file__).with_name("pilot0b_results.jsonl").write_text("\n".join(json.dumps(r) for r in res) + "\n")
    for src in ("plain", "ideal"):
        r = [x for x in res if x["src"] == src]
        d = [x["pert"] - x["orig"] for x in r]
        print(f"{src}: n={len(r)} orig={st.mean(x['orig'] for x in r):.3f} pert={st.mean(x['pert'] for x in r):.3f} "
              f"mean_delta={st.mean(d):+.3f} frac_unpenalised(delta>=0)={sum(x>=0 for x in d)/len(d):.2f}")


if __name__ == "__main__":
    main()
