"""Analysis for pilot 1 (presence vs stance credit). Prints the pre-registered decision quantities."""
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
REWRITES = {"hedged", "disj1", "disj3", "disj9", "decisive", "padded"}


def rub(points):
    return [{"points": p} for p in points]


def scores(r):
    R = rub(r["points"])
    pres = J.presence_score(R, [bool(x) for x in r["presence"]]) if r["presence"] else None
    if r["stance"] and sum(s is not None for s in r["stance"]) >= 0.8 * len(r["stance"]):
        prop = J.proper_score(R, r["stance"])
        sap = J.stance_as_presence(R, r["stance"])
    else:
        prop = sap = None
    return pres, prop, sap


def boot_ci(xs, f=st.mean, B=2000, seed=0):
    rng = random.Random(seed)
    v = sorted(f([rng.choice(xs) for _ in xs]) for _ in range(B))
    return v[int(0.025 * B)], v[int(0.975 * B)]


def kappa(a, b):
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if not pairs:
        return float("nan")
    po = sum(x == y for x, y in pairs) / len(pairs)
    ca, cb = collections.Counter(x for x, _ in pairs), collections.Counter(y for _, y in pairs)
    pe = sum(ca[k] * cb[k] for k in ca) / len(pairs) ** 2
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")


def stage_a():
    rows = [json.loads(l) for l in (HERE / "pilot1a_results.jsonl").open()]
    bank = {json.loads(l)["prompt_id"]: json.loads(l) for l in (HERE / "bank.jsonl").open()}
    S = {}
    texts = {}
    for r in rows:
        S[(r["i"], r["variant"], r["rep"])] = scores(r) + (r["words"],)
    # refusals for rewrite variants are detected from the regenerated texts saved in results? use word count + bank
    n = max(r["i"] for r in rows) + 1
    variants = sorted({r["variant"] for r in rows})
    refused = set()
    import pilot1_stance as P  # noqa: regenerate cached variant texts for refusal check
    vrows = P.build_variants(n)
    for i, (_, v) in enumerate(vrows):
        for name in REWRITES:
            if name in v and is_rewrite_refusal(v[name]):
                refused.add((i, name))
    print(f"Stage A: prompts={n}, variants={variants}")
    print(f"rewrite refusals excluded: {collections.Counter(nm for _, nm in refused)}")
    print("\n== Mean scores (rep 0) ==   presence | stance-proper | stance-as-presence | words | P(>=ideal) pres | P(>=ideal) proper")
    for v in ["ideal", "plain", "decisive", "generic", "blist", "aware", "hedged", "disj1", "disj3", "disj9", "padded", "numpert"]:
        ks = [i for i in range(n) if (i, v, 0) in S and (i, v) not in refused and S[(i, v, 0)][0] is not None and S[(i, v, 1 - 1)][1] is not None]
        if not ks:
            continue
        pres = [S[(i, v, 0)][0] for i in ks]
        prop = [S[(i, v, 0)][1] for i in ks]
        sap = [S[(i, v, 0)][2] for i in ks]
        w = [S[(i, v, 0)][3] for i in ks]
        ge_p = [S[(i, v, 0)][0] >= S[(i, "ideal", 0)][0] for i in ks if S[(i, "ideal", 0)][0] is not None]
        ge_s = [S[(i, v, 0)][1] >= S[(i, "ideal", 0)][1] for i in ks if S[(i, "ideal", 0)][1] is not None]
        print(f"{v:9s} n={len(ks):3d}  {st.mean(pres):.3f} | {st.mean(prop):+.3f} | {st.mean(sap):.3f} | {st.mean(w):5.0f} | {sum(ge_p)/len(ge_p):.2f} | {sum(ge_s)/len(ge_s):.2f}")

    print("\n== Paired deltas vs plain (rep 0), mean [95% CI] ==")
    for v in ["hedged", "disj1", "disj3", "disj9", "padded", "numpert", "aware", "decisive", "generic", "blist"]:
        ks = [i for i in range(n) if (i, v, 0) in S and (i, v) not in refused and None not in S[(i, v, 0)][:2] and None not in S[(i, "plain", 0)][:2]]
        if len(ks) < 5:
            continue
        dp = [S[(i, v, 0)][0] - S[(i, "plain", 0)][0] for i in ks]
        ds = [S[(i, v, 0)][1] - S[(i, "plain", 0)][1] for i in ks]
        print(f"{v:9s} n={len(ks):3d}  Δpresence {st.mean(dp):+.3f} {tuple(round(x,3) for x in boot_ci(dp))}   Δproper {st.mean(ds):+.3f} {tuple(round(x,3) for x in boot_ci(ds))}")

    print("\n== Noise floor (rep0 vs rep1 on replicated prompts) ==")
    reps = [i for i in range(n) if (i, "plain", 1) in S]
    for name, idx in (("presence", 0), ("proper", 1)):
        d = [abs(S[(i, v, 1)][idx] - S[(i, v, 0)][idx]) for i in reps for v in variants
             if (i, v, 1) in S and S[(i, v, 1)][idx] is not None and S[(i, v, 0)][idx] is not None]
        print(f"{name}: mean |Δ| = {st.mean(d):.3f}  (n={len(d)})  sd≈{st.pstdev(d):.3f}")
    by = {(r["i"], r["variant"], r["rep"]): r for r in rows}
    a, b = [], []
    for i in reps:
        for v in variants:
            if (i, v, 1) in by:
                a += by[(i, v, 0)]["stance"]
                b += by[(i, v, 1)]["stance"]
    print(f"stance label agreement: raw={sum(x == y for x, y in zip(a, b) if x and y)/sum(1 for x, y in zip(a, b) if x and y):.3f}  kappa={kappa(a, b):.3f}")
    pa, pb = [], []
    for i in reps:
        for v in variants:
            if (i, v, 1) in by:
                pa += by[(i, v, 0)]["presence"]
                pb += by[(i, v, 1)]["presence"]
    print(f"presence label agreement: kappa={kappa(pa, pb):.3f}")

    print("\n== Wrong-number test (numpert vs plain) ==")
    ks = [i for i in range(n) if (i, "numpert", 0) in S and S[(i, "numpert", 0)][0] is not None and S[(i, "numpert", 0)][1] is not None]
    for name, idx, floor in (("presence", 0, None), ("proper", 1, None)):
        d = [S[(i, "numpert", 0)][idx] - S[(i, "plain", 0)][idx] for i in ks]
        print(f"{name}: n={len(d)} mean Δ={st.mean(d):+.3f}  frac penalised (Δ<0)={sum(x < 0 for x in d)/len(d):.2f}  frac Δ<-0.05={sum(x < -0.05 for x in d)/len(d):.2f}")
    # contradicted labels triggered by numpert
    c_np = sum(s == "contradicted" for i in ks for s in by[(i, "numpert", 0)]["stance"])
    c_pl = sum(s == "contradicted" for i in ks for s in by[(i, "plain", 0)]["stance"])
    print(f"'contradicted' labels: numpert {c_np} vs plain {c_pl} over {len(ks)} prompts")

    print("\n== Item-level credit by k (positive items) ==")
    for v in ["plain", "disj1", "disj3", "disj9", "hedged"]:
        pres_cr, comm, hedg = [], [], []
        for i in range(n):
            if (i, v) in refused or (i, v, 0) not in by:
                continue
            r = by[(i, v, 0)]
            for p, m, s in zip(r["points"], r["presence"], r["stance"]):
                if p > 0 and m is not None and s is not None:
                    pres_cr.append(bool(m)); comm.append(s == "committed"); hedg.append(s == "hedged")
        print(f"{v:7s} items={len(pres_cr)}  P(presence credit)={st.mean(pres_cr):.3f}  P(committed)={st.mean(comm):.3f}  P(hedged)={st.mean(hedg):.3f}")
    print("negative items (penalty fired):")
    for v in ["plain", "disj1", "disj3", "disj9", "hedged"]:
        pen = [bool(m) for i in range(n) if (i, v) not in refused and (i, v, 0) in by
               for p, m in zip(by[(i, v, 0)]["points"], by[(i, v, 0)]["presence"]) if p < 0 and m is not None]
        if pen:
            print(f"  {v:7s} items={len(pen)} P(penalty)={st.mean(pen):.3f}")

    print("\n== Implied commitment threshold tau = (R_hedge - R_wrong)/(R_right - R_wrong) (prompt-mean rewards) ==")
    for name, idx in (("presence", 0), ("proper", 1)):
        ks = [i for i in range(n) if all((i, v, 0) in S and S[(i, v, 0)][idx] is not None and (i, v) not in refused for v in ("plain", "numpert", "disj3"))]
        Rr = st.mean(S[(i, "plain", 0)][idx] for i in ks); Rw = st.mean(S[(i, "numpert", 0)][idx] for i in ks); Rh = st.mean(S[(i, "disj3", 0)][idx] for i in ks)
        tau = (Rh - Rw) / (Rr - Rw) if Rr != Rw else float("nan")
        print(f"{name}: n={len(ks)} R_right={Rr:.3f} R_wrong={Rw:.3f} R_hedge(disj3)={Rh:.3f} -> tau={tau:.2f}")

    print("\n== Pareto dominance of aware over ideal (rep 0) ==")
    for label, fn in (("presence", lambda r: [bool(x) for x in r["presence"]]),
                      ("stance-committed", lambda r: [s == "committed" for s in r["stance"]])):
        dom = tot = strict = 0
        for i in range(n):
            if (i, "aware", 0) not in by or (i, "ideal", 0) not in by:
                continue
            A, I, pts = fn(by[(i, "aware", 0)]), fn(by[(i, "ideal", 0)]), by[(i, "ideal", 0)]["points"]
            ok = all((a >= b) if p > 0 else (a <= b) for a, b, p in zip(A, I, pts))
            tot += 1; dom += ok; strict += ok and A != I
        print(f"{label}: aware weakly dominates ideal in {dom}/{tot} = {dom/tot:.2f} (strictly {strict/tot:.2f})")


def stage_b():
    rows = [json.loads(l) for l in (HERE / "pilot1b_results.jsonl").open()]
    pools = collections.defaultdict(list)
    for r in rows:
        p, s, _ = scores(r)
        pools[r["pool"]].append((r["gold"], p, s))
    res = {"presence": [], "proper": [], "random": [], "oracle": []}
    hit = {"presence": [], "proper": []}
    conc = {"presence": [], "proper": []}
    for pi, xs in pools.items():
        if len(xs) != 4 or any(x[1] is None or x[2] is None for x in xs):
            continue
        golds = [x[0] for x in xs]
        best = max(golds)
        res["random"].append(st.mean(golds)); res["oracle"].append(best)
        for name, idx in (("presence", 1), ("proper", 2)):
            top = max(x[idx] for x in xs)
            picks = [x for x in xs if x[idx] == top]
            g = st.mean(x[0] for x in picks)
            res[name].append(g)
            hit[name].append(st.mean(x[0] == best for x in picks))
            c = []
            for a in range(4):
                for b in range(a + 1, 4):
                    if xs[a][0] != xs[b][0]:
                        c.append(1.0 if (xs[a][idx] - xs[b][idx]) * (xs[a][0] - xs[b][0]) > 0 else (0.5 if xs[a][idx] == xs[b][idx] else 0.0))
            if c:
                conc[name].append(st.mean(c))
    m = len(res["random"])
    print(f"\nStage B (physician BoN-4): pools={m}")
    for k, v in res.items():
        print(f"  mean physician gold of pick under {k:8s}: {st.mean(v):.3f}")
    for k in hit:
        print(f"  {k}: P(pick is physician-best)={st.mean(hit[k]):.3f}   pairwise concordance with physicians={st.mean(conc[k]):.3f}")
    d = [a - b for a, b in zip(res["proper"], res["presence"])]
    print(f"  gold(proper pick) - gold(presence pick) = {st.mean(d):+.3f}  95% CI {tuple(round(x,3) for x in boot_ci(d))}")


if __name__ == "__main__":
    w = sys.argv[1] if len(sys.argv) > 1 else "ab"
    if "a" in w:
        stage_a()
    if "b" in w:
        stage_b()
