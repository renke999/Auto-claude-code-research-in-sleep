"""HealthBench meta-eval pools as human (physician) gold.

Each meta-eval prompt has (mostly) 4 model completions, each labelled by ~2 physicians on 1-3 cluster-level
consensus criteria. Physician gold for a completion = mean over its criteria of the mean physician label.
The same prompt_id has per-example physician rubrics (and often an ideal) in oss_eval, so we can run
"physician BoN-4": select among the 4 completions with any reward and score the choice with physician gold.
"""
from __future__ import annotations

import collections
import json
import random

from common import DATA, EVAL

META = DATA / "2025-05-07-06-14-12_oss_meta_eval.jsonl"


def load_pools(n=None, seed=0, need_ideal=True, single_turn=False, min_spread=0.0):
    ev = {}
    for l in EVAL.open():
        r = json.loads(l)
        ev[r["prompt_id"]] = r
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    text = {}
    for l in META.open():
        r = json.loads(l)
        by[r["prompt_id"]][r["completion_id"]].append(r)
        text[r["completion_id"]] = r["completion"]
    pools = []
    for pid, comps in by.items():
        if len(comps) != 4 or pid not in ev:
            continue
        ex = ev[pid]
        if need_ideal and not ex.get("ideal_completions_data"):
            continue
        if single_turn and len(ex["prompt"]) != 1:
            continue
        gold = {}
        for cid, rows in comps.items():
            gold[cid] = sum(sum(r["binary_labels"]) / len(r["binary_labels"]) for r in rows) / len(rows)
        if max(gold.values()) - min(gold.values()) < min_spread:
            continue
        pools.append({"ex": ex, "completions": {c: text[c] for c in comps}, "gold": gold})
    random.Random(seed).shuffle(pools)
    return pools[:n] if n else pools


if __name__ == "__main__":
    p = load_pools()
    print(len(p), "pools with ideal;", sum(max(x["gold"].values()) > min(x["gold"].values()) for x in p), "with spread")
