"""Shared response bank for the idea pilots (API-only).

For each sampled HealthBench prompt with a physician ideal we build:
  ideal      physician ideal completion
  plain      ordinary Haiku answer
  generic    rubric-blind vague, cover-all-bases answer
  blist      rubric-blind wall of standalone assertions
  aware      rubric-aware terse assertion list (upper bound on gaming)
  hedged     plain answer rewritten so every recommendation is one of several options (no commitment)
  padded     plain answer + true-but-unrequested general advice
  numpert    plain answer with ~2 clinical numbers scaled x3 or /3 (programmatic)
plus a BoN pool of 16 Haiku samples under mixed style instructions.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import llm
from common import convo_text, load_examples
from pilot0_susceptibility import aware_prompt, gen_prompt
from pilot0b_numeric import perturb

OUT = Path(__file__).with_name("bank.jsonl")
GEN = "claude-haiku-5-5"

HEDGE = (
    "Rewrite the following assistant answer so that every concrete recommendation, conclusion, or next step is "
    "presented as just one of several possibilities (e.g. 'it could be X, or Y, or Z'; 'options include A, B or C'; "
    "'you might consider ... or ...'), never committing to a single one. Keep all the original content and similar "
    "length. Output only the rewritten answer.\n\n<answer>\n{a}\n</answer>"
)
PAD = (
    "Here is an assistant answer. Append 6 additional sentences of true, generally sensible health advice that is "
    "loosely related to the topic but that the user did not ask for (e.g. general lifestyle, prevention, when to see a "
    "doctor). Output the full answer with the additions at the end.\n\n<answer>\n{a}\n</answer>"
)
POOL_STYLES = [
    "Answer the user helpfully as a careful medical assistant.",
    "Answer concisely and directly, committing to clear recommendations.",
    "Answer thoroughly and comprehensively, covering everything that could be relevant.",
    "Answer as a structured bulleted list covering all relevant aspects.",
]


def pool_prompt(ex, i):
    return f"{POOL_STYLES[i % len(POOL_STYLES)]}\n\nConversation:\n{convo_text(ex['prompt'])}\n\nWrite only the assistant's next reply.\n\n[sample {i}]"


def main(n=150, pool=16):
    exs = load_examples(n, seed=1)
    rng = random.Random(1)
    styles = ["plain", "generic", "listing"]
    g = llm.call_many([gen_prompt(e, s) for e in exs for s in styles], GEN, workers=16)
    aw = llm.call_many([aware_prompt(e) for e in exs], GEN, workers=16)
    plains = [g[i * 3] for i in range(len(exs))]
    hd = llm.call_many([HEDGE.format(a=p) for p in plains], GEN, workers=16)
    pd = llm.call_many([PAD.format(a=p) for p in plains], GEN, workers=16)
    pl = llm.call_many([pool_prompt(e, i) for e in exs for i in range(pool)], GEN, workers=16)
    with OUT.open("w") as f:
        for k, e in enumerate(exs):
            np_, nk = perturb(plains[k], rng)
            row = {
                "prompt_id": e["prompt_id"],
                "variants": {
                    "ideal": e["ideal_completions_data"]["ideal_completion"],
                    "plain": plains[k], "generic": g[k * 3 + 1], "blist": g[k * 3 + 2], "aware": aw[k],
                    "hedged": hd[k], "padded": pd[k], "numpert": np_,
                },
                "numpert_k": nk,
                "pool": pl[k * pool:(k + 1) * pool],
            }
            f.write(json.dumps(row) + "\n")
    print("wrote", OUT, len(exs))


if __name__ == "__main__":
    main(*(int(a) for a in sys.argv[1:]))
