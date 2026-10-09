"""Pre-registered analysis for pilot 8 (see IDEA_REPORT.md, "修正与预登记：Pilot 8")."""
from __future__ import annotations

import collections
import json
import random
import statistics as st
import sys
from pathlib import Path

import judges as J
from common import is_rewrite_refusal

HERE = Path(__file__).parent
rub = lambda pts: [{"points": p} for p in pts]


def boot(xs, B=4000, seed=0):
    rng = random.Random(seed)
    v = sorted(st.mean(rng.choice(xs) for _ in xs) for _ in range(B))
    return v[int(0.025 * B)], v[int(0.975 * B)]


def pres(r):
    return J.presence_score(rub(r["points"]), [bool(x) for x in r["presence"]])


def two(r, h=0.0, c=-3.0):
    return J.two_stage_score(rub(r["points"]), [bool(x) for x in r["presence"]], r["commit"], h, c)


def stage_a():
    rows = [json.loads(l) for l in (HERE / "pilot8a_results.jsonl").open()]
    by = {(r["i"], r["variant"], r["rep"]): r for r in rows}
    import pilot1_stance as P
    vt = P.build_variants(100)
    refused = {(i, k) for i, (_, v) in enumerate(vt) for k in ("hedged", "disj1", "disj3", "disj9", "decisive") if is_rewrite_refusal(v.get(k))}
    n = 100

    def paired(v, f):
        ks = [i for i in range(n) if (i, v, 0) in by and (i, "plain", 0) in by and (i, v) not in refused]
        return [f(by[(i, v, 0)]) - f(by[(i, "plain", 0)]) for i in ks]

    print("== P8-A' paired deltas vs plain: presence | two-stage(h0,c-3) | two-stage minus presence [95% CI]")
    for v in ("hedged", "disj3", "disj9", "numpert", "numsub", "aware", "padded", "generic", "blist", "ideal", "decisive"):
        dp, dt = paired(v, pres), paired(v, two)
        if len(dp) < 5:
            continue
        diff = [b - a for a, b in zip(dp, dt)]
        print(f"  {v:8s} n={len(dp):3d}  {st.mean(dp):+.3f} | {st.mean(dt):+.3f} | {st.mean(diff):+.3f} {tuple(round(x, 3) for x in boot(diff))}")
    # A1
    dp, dt = paired("hedged", pres), paired("hedged", two)
    diff = [b - a for a, b in zip(dp, dt)]
    lo, hi = boot(diff)
    print(f"A1 (hedged: two-stage more negative than presence by <= -0.05, CI excludes 0): diff={st.mean(diff):+.3f} CI=({lo:.3f},{hi:.3f}) -> {'PASS' if st.mean(diff) <= -0.05 and hi < 0 else 'FAIL'}")
    # A2: re-judge floor
    reps = [i for i in range(n) if (i, "plain", 1) in by]
    for name, f in (("presence", pres), ("two-stage", two)):
        floor = [f(by[(i, v, 1)]) - f(by[(i, v, 0)]) for i in reps for v in ("plain", "ideal", "hedged", "aware", "padded") if (i, v, 1) in by]
        fr = sum(x < 0 for x in floor) / len(floor)
        for v in ("numpert", "numsub"):
            d = paired(v, f)
            pen = sum(x < 0 for x in d) / len(d)
            print(f"A2 {name:9s} {v}: penalised {pen:.2f} (n={len(d)}) vs same-text floor {fr:.2f} -> {'PASS' if pen > fr else 'FAIL'}; mean Δ {st.mean(d):+.3f}")
    # A3
    def ev_share(v):
        lab = [l for i in range(n) if (i, v, 0) in by and (i, v) not in refused
               for l, p, m in zip(by[(i, v, 0)]["commit"], by[(i, v, 0)]["points"], by[(i, v, 0)]["presence"]) if p > 0 and m and l]
        return sum(l == "evasive" for l in lab) / len(lab), len(lab)
    shares = {v: ev_share(v) for v in ("ideal", "plain", "hedged", "disj3", "disj9", "aware", "generic")}
    print("evasive share among presence-met positive items:", {k: f"{a:.3f}(n={b})" for k, (a, b) in shares.items()})
    print(f"A3 (ideal evasive share <= plain): {shares['ideal'][0]:.3f} vs {shares['plain'][0]:.3f} -> {'PASS' if shares['ideal'][0] <= shares['plain'][0] else 'FAIL'}")
    con = {v: sum(l == "contradicted" for i in range(n) if (i, v, 0) in by for l in by[(i, v, 0)]["commit"]) for v in ("plain", "numpert", "numsub", "ideal")}
    print("contradicted label counts:", con)


def stage_b():
    rows = [json.loads(l) for l in (HERE / "pilot8b_results.jsonl").open()]
    pools = collections.defaultdict(list)
    for r in rows:
        pools[r["pool"]].append(r)
    pools = {k: v for k, v in pools.items() if len(v) == 4 and all(x["presence"] and x["commit"] for x in v)}
    hed = {k for k, v in pools.items() if any(("hedging" in c) or ("context_seeking" in c) for c in (v[0].get("clusters") or []))}
    rules = {"presence": pres, "two h0 c-3": lambda r: two(r, 0, -3), "two h0.5 c-3": lambda r: two(r, 0.5, -3),
             "two h1 c-3": lambda r: two(r, 1, -3), "two h0 c-1": lambda r: two(r, 0, -1), "two h0.5 c-1": lambda r: two(r, 0.5, -1),
             "ConRub-like h1 c-1": lambda r: two(r, 1, -1)}

    def evalr(f, keys):
        g, hit, conc = {}, [], []
        for k in keys:
            xs = pools[k]
            sc = [f(x) for x in xs]; gold = [x["gold"] for x in xs]; best = max(gold); top = max(sc)
            picks = [i for i in range(4) if sc[i] == top]
            g[k] = st.mean(gold[i] for i in picks); hit.append(st.mean(gold[i] == best for i in picks))
            c = [(1 if (sc[a] - sc[b]) * (gold[a] - gold[b]) > 0 else (0.5 if sc[a] == sc[b] else 0)) for a in range(4) for b in range(a + 1, 4) if gold[a] != gold[b]]
            if c:
                conc.append(st.mean(c))
        return g, st.mean(hit), st.mean(conc)

    allk = sorted(pools); hk = sorted(hed & set(pools)); ok = sorted(set(pools) - hed)
    print(f"\n== P8-B' physician BoN-4: pools={len(allk)} (hedging/context {len(hk)}, other {len(ok)}); random gold={st.mean(st.mean(x['gold'] for x in pools[k]) for k in allk):.3f}")
    base = {name: evalr(pres, ks)[0] for name, ks in (("all", allk), ("hed", hk), ("oth", ok))}
    for name, f in rules.items():
        line = [f"{name:20s}"]
        for lab, ks in (("all", allk), ("hed", hk), ("oth", ok)):
            g, hit, conc = evalr(f, ks)
            d = [g[k] - base[lab][k] for k in ks]
            lo, hi = boot(d)
            line.append(f"{lab}: gold {st.mean(g.values()):.3f} Δ{st.mean(d):+.3f}[{lo:+.3f},{hi:+.3f}] P(best) {hit:.3f} conc {conc:.3f}")
        print("  " + " | ".join(line))
    g, _, _ = evalr(rules["two h0 c-3"], allk); d = [g[k] - base["all"][k] for k in allk]; lo, _ = boot(d)
    print(f"B1 (non-inferiority, CI lower bound > -0.01): Δ={st.mean(d):+.4f} lower={lo:+.4f} -> {'PASS' if lo > -0.01 else 'FAIL'}")
    g, _, _ = evalr(rules["two h0 c-3"], hk); d = [g[k] - base["hed"][k] for k in hk]
    print(f"B2 (hedging/context pools point estimate > -0.02): Δ={st.mean(d):+.4f} -> {'PASS' if st.mean(d) > -0.02 else 'FAIL -> move h toward 0.5 before RL'}")


if __name__ == "__main__":
    w = sys.argv[1] if len(sys.argv) > 1 else "ab"
    if "a" in w:
        stage_a()
    if "b" in w:
        stage_b()
