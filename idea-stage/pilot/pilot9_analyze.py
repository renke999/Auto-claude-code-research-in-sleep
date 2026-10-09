"""Pre-registered gate analysis for pilot 9 (v3 judge)."""
from __future__ import annotations

import json
import random
import statistics as st
from pathlib import Path

import judges as J

HERE = Path(__file__).parent
rub = lambda pts: [{"points": p} for p in pts]


def boot(xs, B=4000, seed=0):
    rng = random.Random(seed)
    v = sorted(st.mean(rng.choice(xs) for _ in xs) for _ in range(B))
    return v[int(0.025 * B)], v[int(0.975 * B)]


def main():
    rows = [json.loads(l) for l in (HERE / "pilot9_results.jsonl").open()]
    by = {(r["i"], r["variant"], r["rep"]): r for r in rows}
    P = lambda r: J.presence_score(rub(r["points"]), [bool(x) for x in r["presence"]])
    V = lambda r, h=0.0, c=-3.0: J.v3_score(rub(r["points"]), [bool(x) for x in r["presence"]], r["commit3"], h, c)
    rules = {"presence": P, "v3 h0 c-3": V, "v3 h0 c-1": lambda r: V(r, 0, -1), "v3 h0.5 c-3": lambda r: V(r, 0.5, -3),
             "v3 h1 c-1 (ConRub-like)": lambda r: V(r, 1, -1), "v3 h1 c-3": lambda r: V(r, 1, -3)}
    n = max(r["i"] for r in rows) + 1
    variants = ["ideal", "hedged", "disj3", "uncwrap", "numpert", "numsub", "uncwrap_wrong", "aware", "padded", "decisive"]

    def paired(v, f, base="plain"):
        ks = [i for i in range(n) if (i, v, 0) in by and (i, base, 0) in by]
        return [f(by[(i, v, 0)]) - f(by[(i, base, 0)]) for i in ks]

    print("== mean Δ vs plain by rule ==")
    print("  " + " ".join(f"{v:>13s}" for v in variants))
    for name, f in rules.items():
        print(f"  {name:24s}" + " ".join(f"{st.mean(paired(v, f)):+13.3f}" if paired(v, f) else f"{'-':>13s}" for v in variants))

    # G1 stability of contradicted
    same = tot = 0
    for (i, v, rep), r in by.items():
        if rep != 0 or (i, v, 1) not in by:
            continue
        r2 = by[(i, v, 1)]
        for a, b in zip(r["commit3"], r2["commit3"]):
            if a == "contradicted":
                tot += 1; same += b == "contradicted"
    g1 = same / tot if tot else float("nan")
    print(f"G1 contradicted repeat rate (rep0->rep1): {g1:.2f} (n={tot}) -> {'PASS' if g1 >= 0.60 else 'FAIL'}")
    # label stability overall
    for lab in ("committed", "evasive", "not_addressed"):
        s = t = 0
        for (i, v, rep), r in by.items():
            if rep == 0 and (i, v, 1) in by:
                for a, b in zip(r["commit3"], by[(i, v, 1)]["commit3"]):
                    if a == lab:
                        t += 1; s += b == lab
        print(f"   {lab} repeat rate {s/t:.2f} (n={t})")
    # G2 specificity
    fire = {v: st.mean(any(l == "contradicted" for l in by[(i, v, 0)]["commit3"]) for i in range(n) if (i, v, 0) in by)
            for v in ("ideal", "plain", "numpert", "numsub", "uncwrap_wrong")}
    print(f"G2 contradicted fire rate: {', '.join(f'{k} {x:.2f}' for k, x in fire.items())} -> {'PASS' if fire['ideal'] <= fire['plain'] else 'FAIL'}")
    # G3 loophole
    dp, dv = paired("uncwrap", P), paired("uncwrap", V)
    d = [b - a for a, b in zip(dp, dv)]; lo, hi = boot(d)
    print(f"G3 uncwrap: Δpresence {st.mean(dp):+.3f}, Δv3 {st.mean(dv):+.3f}, v3−presence {st.mean(d):+.3f} CI({lo:+.3f},{hi:+.3f}) -> {'PASS' if st.mean(d) <= -0.05 and hi < 0 else 'FAIL'}")
    # G4 truth
    reps = [i for i in range(n) if (i, "plain", 1) in by]
    for name, f in (("presence", P), ("v3", V)):
        fl = [f(by[(i, v, 1)]) - f(by[(i, v, 0)]) for i in reps for v in ("plain", "ideal", "aware", "padded") if (i, v, 1) in by]
        floor = sum(x < 0 for x in fl) / len(fl)
        for v in ("numsub", "numpert"):
            dd = paired(v, f)
            pen = sum(x < 0 for x in dd) / len(dd)
            print(f"G4 {name:8s} {v}: penalised {pen:.2f} (n={len(dd)}) vs floor {floor:.2f}; mean Δ {st.mean(dd):+.3f} -> {'PASS' if pen > floor else 'FAIL'}")
    # empirical tau and hedged-wrong vs committed-wrong
    print("== empirical tau (right=plain, wrong=numpert, hedge=uncwrap) and hedged-wrong − committed-wrong ==")
    ks = [i for i in range(n) if all((i, v, 0) in by for v in ("plain", "numpert", "uncwrap", "uncwrap_wrong"))]
    for name, f in rules.items():
        R = {v: st.mean(f(by[(i, v, 0)]) for i in ks) for v in ("plain", "numpert", "uncwrap", "uncwrap_wrong")}
        tau = (R["uncwrap"] - R["numpert"]) / (R["plain"] - R["numpert"]) if R["plain"] != R["numpert"] else float("nan")
        hw = [f(by[(i, "uncwrap_wrong", 0)]) - f(by[(i, "numpert", 0)]) for i in ks]
        print(f"  {name:24s} n={len(ks)} right {R['plain']:.3f} wrong {R['numpert']:.3f} hedge {R['uncwrap']:.3f} tau={tau:+.2f} | hedged-wrong − committed-wrong {st.mean(hw):+.3f}")
    ev = {v: (lambda labs: sum(l == "evasive" for l in labs) / max(1, len(labs)))([l for i in range(n) if (i, v, 0) in by for l in by[(i, v, 0)]["commit3"] if l])
          for v in ("ideal", "plain", "hedged", "disj3", "uncwrap", "aware")}
    print("evasive share among content labels:", {k: round(x, 3) for k, x in ev.items()})


if __name__ == "__main__":
    main()
