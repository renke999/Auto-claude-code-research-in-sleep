"""Three-action optimal policy (commit / hedge-menu / omit) per credit rule, from the pilot-10 item-aligned probes.
For confidence p, E[commit] = p*R + (1-p)*W, E[hedge] = H, E[omit] = 0. Reports the optimal action regions and the c
that puts the commit threshold at 0.75 for h=0."""
from __future__ import annotations

import json
import statistics as st
from pathlib import Path

HERE = Path(__file__).parent
out = [json.loads(l) for l in (HERE / "pilot10_probes.jsonl").open()]
by = {}
for o in out:
    by.setdefault(o["k"], {})[o["probe"]] = o
ks = [k for k, d in by.items() if all(x in d for x in ("right", "wrong", "hedge"))]
g = lambda l, m, h, c: {"committed": 1.0, "evasive": h, "not_addressed": 0.0, "contradicted": c}.get(l, 1.0 if m else 0.0)


def E(rule):
    if rule is None:
        return {nm: st.mean(bool(by[k][nm]["met"]) for k in ks) for nm in ("right", "wrong", "hedge")}
    h, c = rule
    return {nm: st.mean(g(by[k][nm]["label"], by[k][nm]["met"], h, c) for k in ks) for nm in ("right", "wrong", "hedge")}


def regions(e):
    R, W, H = e["right"], e["wrong"], e["hedge"]
    acts = []
    prev = None
    for i in range(101):
        p = i / 100
        vals = {"commit": p * R + (1 - p) * W, "hedge": H, "omit": 0.0}
        a = max(vals, key=vals.get)
        if a != prev:
            acts.append((p, a)); prev = a
    return " -> ".join(f"{a}@p>={p:.2f}" for p, a in acts)


rules = {"presence": None, "truth-only h1 c-1 (ConRub-like)": (1, -1), "truth-only h1 c-3": (1, -3), "stance h0 c-1": (0, -1),
         "stance h0 c-3": (0, -3), "stance h0 c-4": (0, -4), "h0.5 c-3": (0.5, -3)}
print(f"items={len(ks)}")
for name, r in rules.items():
    e = E(r)
    print(f"{name:32s} R={e['right']:+.3f} W={e['wrong']:+.3f} H={e['hedge']:+.3f} | optimal action by confidence p: {regions(e)}")
best = None
for c10 in range(-5, -151, -1):
    c = c10 / 10
    e = E((0, c))
    pstar = -e["wrong"] / (e["right"] - e["wrong"])
    if best is None or abs(pstar - 0.75) < abs(best[1] - 0.75):
        best = (c, pstar)
print(f"h=0: c* putting the commit-vs-omit threshold at 0.75 -> c*={best[0]:.1f} (threshold {best[1]:.3f})")
