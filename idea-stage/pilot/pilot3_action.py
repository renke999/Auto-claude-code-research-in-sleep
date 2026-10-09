"""Pilot 3 (idea I12): induced-action agreement.

1. Sonnet writes a 3-5 item multiple-choice DECISION questionnaire from the conversation alone (never sees the
   ideal or any response); each question has an option "The response doesn't make this clear".
2. A simulated user (Haiku) answers the questionnaire after reading ONE response. Target decisions = answers
   after reading the physician ideal. Reward = agreement with the ideal's decisions on questions where the ideal
   gives a decision.
Stage A: bank variants (same 100 prompts as pilot 1, incl. disjunction/decisive rewrites).
Stage B: physician BoN-4 on the same 200 meta-eval pools as pilot 1 stage B.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import llm
from common import convo_text, is_rewrite_refusal, load_examples
from metaeval import load_pools

HERE = Path(__file__).parent
QGEN = "claude-sonnet-5-5"
READER = "claude-haiku-5-5"
UNCLEAR = "The response doesn't make this clear"

QPROMPT = """Below is a conversation between a user and a medical AI assistant (the assistant's final reply is not shown).
Write 3-5 multiple-choice questions about the concrete DECISIONS the user would make after reading a good reply:
e.g. whether/where/how urgently to seek care, what to take or do, how much/how often, what warning signs to act on,
what information to gather. Each question must have 3-5 mutually exclusive, specific options that a reasonable reply
could lead to, plus the final option "{u}". Do not reveal which option is correct.

<conversation>
{convo}
</conversation>

Return ONLY JSON: {{"questions": [{{"q": "...", "options": ["...", "...", "{u}"]}}]}}"""

RPROMPT = """You are the user in the conversation below. You have just read the assistant's reply.
Based ONLY on what the reply tells you (not on your own knowledge), answer each question by choosing the option
the reply would lead you to. If the reply does not clearly point to one option (for example it lists several
options without saying which to choose, or does not address the question), choose "{u}".

<conversation>
{convo}
</conversation>

<assistant_reply>
{resp}
</assistant_reply>

Questions:
{qs}

Return ONLY JSON: {{"answers": [<option index (0-based) for each question, in order>]}}"""


def questionnaire(ex):
    out = llm.call(QPROMPT.format(u=UNCLEAR, convo=convo_text(ex["prompt"])), QGEN)
    try:
        qs = llm.extract_json(out)["questions"]
        return [q for q in qs if UNCLEAR in q["options"]]
    except Exception:
        return None


def fmt(qs):
    return "\n".join(f"Q{j}: {q['q']}\n" + "\n".join(f"  {k}. {o}" for k, o in enumerate(q["options"])) for j, q in enumerate(qs))


def read_prompt(ex, qs, resp):
    return RPROMPT.format(u=UNCLEAR, convo=convo_text(ex["prompt"]), resp=resp, qs=fmt(qs))


def parse_answers(text, qs):
    try:
        a = llm.extract_json(text)["answers"]
        return [int(x) for x in a][: len(qs)] if len(a) >= len(qs) else None
    except Exception:
        return None


def agreement(qs, target, ans):
    keep = [j for j, q in enumerate(qs) if target[j] != q["options"].index(UNCLEAR)]
    if not keep or ans is None:
        return None
    return sum(ans[j] == target[j] for j in keep) / len(keep)


def run_pairs(items):
    """items: list of (key, ex, {name: response_text}) with 'ideal' among names."""
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(6) as ex_:
        qss = list(ex_.map(lambda it: questionnaire(it[1]), items))
    jobs, keys = [], []
    for (key, ex, resps), qs in zip(items, qss):
        if not qs:
            continue
        for name, txt in resps.items():
            if txt is None:
                continue
            jobs.append(read_prompt(ex, qs, txt)); keys.append((key, name))
    outs = llm.call_many(jobs, READER, workers=10)
    ans = {}
    for (key, name), o in zip(keys, outs):
        ans[(key, name)] = o
    res = []
    for (key, ex, resps), qs in zip(items, qss):
        if not qs or (key, "ideal") not in ans:
            continue
        tgt = parse_answers(ans[(key, "ideal")], qs)
        if tgt is None:
            continue
        unclear_idx = [q["options"].index(UNCLEAR) for q in qs]
        row = {"key": key, "n_q": len(qs), "ideal_decided": sum(t != u for t, u in zip(tgt, unclear_idx)), "agree": {}, "unclear_rate": {}}
        for name in resps:
            if (key, name) not in ans:
                continue
            a = parse_answers(ans[(key, name)], qs)
            row["agree"][name] = agreement(qs, tgt, a)
            row["unclear_rate"][name] = None if a is None else sum(x == u for x, u in zip(a, unclear_idx)) / len(qs)
        res.append(row)
    return res


def stage_a(n=100):
    import pilot1_stance as P
    rows = P.build_variants(n)
    items = []
    for i, (ex, v) in enumerate(rows):
        resps = {k: (None if (k in P.__dict__.get("REWRITES", set()) and is_rewrite_refusal(t)) else t) for k, t in v.items()}
        for k in ("hedged", "disj1", "disj3", "disj9", "decisive", "padded"):
            if is_rewrite_refusal(resps.get(k)):
                resps[k] = None
        items.append((i, ex, resps))
    res = run_pairs(items)
    # self-consistency: the ideal read twice (different tag) -> reader noise
    (HERE / "pilot3a_results.jsonl").write_text("\n".join(json.dumps(r) for r in res) + "\n")


def stage_b(n=200):
    pools = load_pools(n, seed=3, min_spread=0.01)
    items = []
    for pi, p in enumerate(pools):
        resps = dict(p["completions"])
        resps["ideal"] = p["ex"]["ideal_completions_data"]["ideal_completion"]
        items.append((pi, p["ex"], resps))
    res = run_pairs(items)
    for r in res:
        r["gold"] = pools[r["key"]]["gold"]
    (HERE / "pilot3b_results.jsonl").write_text("\n".join(json.dumps(r) for r in res) + "\n")


if __name__ == "__main__":
    w = sys.argv[1] if len(sys.argv) > 1 else "ab"
    if "a" in w:
        stage_a()
    if "b" in w:
        stage_b()
