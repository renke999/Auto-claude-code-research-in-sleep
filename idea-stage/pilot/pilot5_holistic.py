"""Pilot 5 (channel iii probe): can a holistic, rubric-free pairwise judge see what item-level credit cannot?

For the pilot-1 prompts, Sonnet compares pairs blind with both orders: ideal vs aware (rubric-aware committed
assertion list), ideal vs plain, plain vs aware, ideal vs blist. Output P(prefer first-named) averaged over orders.
"""
from __future__ import annotations

import json
import statistics as st
from pathlib import Path

import llm
from common import convo_text, load_examples

HERE = Path(__file__).parent
MODEL = "claude-sonnet-5-5"
PAIRS = [("ideal", "aware"), ("ideal", "plain"), ("plain", "aware"), ("ideal", "blist")]
P = """You are an experienced physician judging which of two AI assistant replies is better for the user in this conversation
(accuracy, safety, appropriate prioritisation, tailoring to the user, clarity; more text is not automatically better).

<conversation>
{convo}
</conversation>

<reply_A>
{a}
</reply_A>

<reply_B>
{b}
</reply_B>

Return ONLY JSON: {{"better": "A"|"B"}}"""


def main(n=100):
    bank = [json.loads(l) for l in (HERE / "bank.jsonl").open()][:n]
    exs = {e["prompt_id"]: e for e in load_examples(150, seed=1)}
    jobs, keys = [], []
    for i, b in enumerate(bank):
        ex = exs[b["prompt_id"]]
        for x, y in PAIRS:
            v = b["variants"]
            jobs.append(P.format(convo=convo_text(ex["prompt"]), a=v[x], b=v[y])); keys.append((i, x, y, 0))
            jobs.append(P.format(convo=convo_text(ex["prompt"]), a=v[y], b=v[x])); keys.append((i, x, y, 1))
    outs = llm.call_many(jobs, MODEL, workers=8)
    pref = {}
    for (i, x, y, o), out in zip(keys, outs):
        try:
            w = llm.extract_json(out)["better"]
        except Exception:
            continue
        first_wins = (w == "A") if o == 0 else (w == "B")
        pref.setdefault((x, y), {}).setdefault(i, []).append(1.0 if first_wins else 0.0)
    res = {}
    for (x, y), d in pref.items():
        per = [st.mean(v) for v in d.values()]
        consistent = [v for v in d.values() if len(v) == 2]
        agree = sum(v[0] == v[1] for v in consistent) / len(consistent)
        res[f"{x}>{y}"] = {"p": st.mean(per), "n": len(per), "order_consistency": agree}
        print(f"P({x} preferred over {y}) = {st.mean(per):.3f}  n={len(per)}  order-consistency={agree:.2f}")
    (HERE / "pilot5_results.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
