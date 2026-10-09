"""Re-registered B1/B2 (physician BoN-4) for the v3 judge."""
from __future__ import annotations

import collections
import json
import statistics as st
from pathlib import Path

import judges as J
from pilot8_analyze import boot

HERE = Path(__file__).parent
rub = lambda pts: [{"points": p} for p in pts]


def main():
    rows = [json.loads(l) for l in (HERE / "pilot9c_results.jsonl").open()]
    pools = collections.defaultdict(list)
    for r in rows:
        pools[r["pool"]].append(r)
    pools = {k: v for k, v in pools.items() if len(v) == 4 and all(x["presence"] for x in v)}
    hed = {k for k, v in pools.items() if any(("hedging" in c) or ("context_seeking" in c) for c in v[0]["clusters"])}
    P = lambda r: J.presence_score(rub(r["points"]), [bool(x) for x in r["presence"]])
    V = lambda r, h, c: J.v3_score(rub(r["points"]), [bool(x) for x in r["presence"]], r["commit3"], h, c)
    rules = {"presence": P, "v3 h0 c-3": lambda r: V(r, 0, -3), "v3 h0.5 c-3": lambda r: V(r, 0.5, -3), "v3 h1 c-3": lambda r: V(r, 1, -3),
             "v3 h0 c-1": lambda r: V(r, 0, -1), "v3 h1 c-1 (ConRub-like)": lambda r: V(r, 1, -1), "v3 h0 c-4.1 (c*)": lambda r: V(r, 0, -4.1)}

    def ev(f, ks):
        g, hit, conc = {}, [], []
        for k in ks:
            xs = pools[k]; sc = [f(x) for x in xs]; gold = [x["gold"] for x in xs]; best = max(gold); top = max(sc)
            pk = [i for i in range(4) if sc[i] == top]
            g[k] = st.mean(gold[i] for i in pk); hit.append(st.mean(gold[i] == best for i in pk))
            c = [(1 if (sc[a] - sc[b]) * (gold[a] - gold[b]) > 0 else (0.5 if sc[a] == sc[b] else 0)) for a in range(4) for b in range(a + 1, 4) if gold[a] != gold[b]]
            if c:
                conc.append(st.mean(c))
        return g, st.mean(hit), st.mean(conc)

    allk = sorted(pools); hk = sorted(hed); ok = sorted(set(pools) - hed)
    print(f"Pilot 9c physician BoN-4 (v3): pools={len(allk)} (hedging/context {len(hk)}, other {len(ok)}); "
          f"random gold {st.mean(st.mean(x['gold'] for x in pools[k]) for k in allk):.3f}; oracle {st.mean(max(x['gold'] for x in pools[k]) for k in allk):.3f}")
    base = {lab: ev(P, ks)[0] for lab, ks in (("all", allk), ("hed", hk), ("oth", ok))}
    for name, f in rules.items():
        parts = []
        for lab, ks in (("all", allk), ("hed", hk), ("oth", ok)):
            g, hit, conc = ev(f, ks); d = [g[k] - base[lab][k] for k in ks]; lo, hi = boot(d)
            parts.append(f"{lab}: gold {st.mean(g.values()):.3f} Δ{st.mean(d):+.3f}[{lo:+.3f},{hi:+.3f}] P(best) {hit:.3f} conc {conc:.3f}")
        print(f"  {name:24s} " + " | ".join(parts))
    g, _, _ = ev(rules["v3 h0 c-3"], allk); d = [g[k] - base["all"][k] for k in allk]; lo, _ = boot(d)
    print(f"B1 (v3 non-inferiority, CI lower bound > -0.01): Δ={st.mean(d):+.4f} lower={lo:+.4f} -> {'PASS' if lo > -0.01 else 'FAIL'}")
    g, _, _ = ev(rules["v3 h0 c-3"], hk); d = [g[k] - base["hed"][k] for k in hk]
    print(f"B2 (hedging/context pools point estimate > -0.02): Δ={st.mean(d):+.4f} -> {'PASS' if st.mean(d) > -0.02 else 'FAIL'}")


if __name__ == "__main__":
    main()
