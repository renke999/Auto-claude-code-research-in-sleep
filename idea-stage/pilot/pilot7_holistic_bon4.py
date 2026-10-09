"""Pilot 7: physician BoN-4 for a holistic pairwise judge (rubric-free) vs per-item rubric credit.

Same meta-eval pools as pilot 1 stage B (seed=3). Sonnet compares all 6 pairs of the 4 completions in both orders;
each completion's holistic score = its win rate. Compare gold of the pick and pairwise concordance with physicians.
"""
from __future__ import annotations

import itertools
import json
import statistics as st
from pathlib import Path

import llm
from common import convo_text
from metaeval import load_pools
from pilot5_holistic import P as PAIR

HERE = Path(__file__).parent


def main(n=100):
    pools = load_pools(200, seed=3, min_spread=0.01)[:n]
    jobs, keys = [], []
    for pi, p in enumerate(pools):
        cids = list(p["completions"])
        c = convo_text(p["ex"]["prompt"])
        for a, b in itertools.combinations(cids, 2):
            jobs.append(PAIR.format(convo=c, a=p["completions"][a], b=p["completions"][b])); keys.append((pi, a, b))
            jobs.append(PAIR.format(convo=c, a=p["completions"][b], b=p["completions"][a])); keys.append((pi, b, a))
    outs = llm.call_many(jobs, "claude-sonnet-5-5", workers=8)
    wins = {}
    for (pi, a, b), o in zip(keys, outs):
        try:
            w = llm.extract_json(o)["better"]
        except Exception:
            continue
        win = a if w == "A" else b
        wins.setdefault(pi, {}).setdefault(win, 0)
        wins[pi][win] += 1
    g, hit, conc, rnd = [], [], [], []
    for pi, p in enumerate(pools):
        gold = p["gold"]; cids = list(gold)
        sc = {c: wins.get(pi, {}).get(c, 0) for c in cids}
        top = max(sc.values()); picks = [c for c in cids if sc[c] == top]; best = max(gold.values())
        g.append(st.mean(gold[c] for c in picks)); hit.append(st.mean(gold[c] == best for c in picks)); rnd.append(st.mean(gold.values()))
        cc = [(1 if (sc[a] - sc[b]) * (gold[a] - gold[b]) > 0 else (0.5 if sc[a] == sc[b] else 0))
              for a, b in itertools.combinations(cids, 2) if gold[a] != gold[b]]
        if cc:
            conc.append(st.mean(cc))
    print(f"holistic pairwise (Sonnet) physician BoN-4: pools={len(g)} gold(pick)={st.mean(g):.3f} random={st.mean(rnd):.3f} "
          f"P(best)={st.mean(hit):.3f} concordance={st.mean(conc):.3f}")
    (HERE / "pilot7_results.json").write_text(json.dumps({"gold": g, "hit": hit, "conc": conc, "random": rnd}))


if __name__ == "__main__":
    main()
