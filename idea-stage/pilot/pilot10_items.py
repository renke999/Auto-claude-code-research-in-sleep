"""Pilot 10 (refine round 2): item-aligned probes to measure the judge-dependent quantities behind tau_eff.

For content items (axis:accuracy/completeness, positive) whose criterion contains a number, in the 100 bank prompts:
  right : a short reply (written by Haiku) that commits to exactly the item's content
  wrong : 'right' with its numbers scaled x3 or /3 (programmatic)
  hedge : a menu containing both, without choosing: "Depending on your situation, either may apply: (a) right (b) wrong"
Each probe is judged against THAT ONE item by (i) the presence judge and (ii) the v3 COMMIT judge (with recheck).
Estimates per item: f = P(contradicted|right), q = P(contradicted|wrong), and per credit rule the expected credit of
right / wrong / hedge -> tau_eff = (H - W)/(R - W) and the c* that hits a target threshold.
Also: (b) Opus adjudication of contradicted flags on natural answers (plain/ideal) and on perturbed answers (precision),
using the quotes logged in the cached COMMIT3 outputs; (c) enlarged G1: re-judge numpert/numsub (run #2).
"""
from __future__ import annotations

import json
import random
import re
import statistics as st
from pathlib import Path

import judges as J
import llm
from common import convo_text, load_examples
from pilot0b_numeric import NUM

HERE = Path(__file__).parent
ANYNUM = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)")
WRITE = ("Conversation:\n{convo}\n\nWrite a short assistant reply (1-3 sentences) that clearly and definitively states "
         "ONLY the following point, applied to this user, keeping all numbers exactly as given:\n\"{crit}\"\n\nOutput only the reply.")


def scale_numbers(text, rng):
    spans = list(ANYNUM.finditer(text))
    if not spans:
        return None
    for m in reversed(spans):
        v = float(m.group(1))
        if v == 0:
            continue
        nv = v * 3 if rng.random() < 0.5 else v / 3
        s = f"{nv:.0f}" if nv >= 10 or float(nv).is_integer() else f"{nv:.1f}"
        text = text[:m.start()] + s + text[m.end():]
    return text


def single_item_ex(ex, i):
    e = dict(ex)
    e["rubrics"] = [ex["rubrics"][i]]
    return e


def probes(n=100, max_items=220):
    bank = [json.loads(l) for l in (HERE / "bank.jsonl").open()][:n]
    exs = {e["prompt_id"]: e for e in load_examples(150, seed=1)}
    items = []
    for b in bank:
        ex = exs[b["prompt_id"]]
        for i in J.content_idx(ex):
            if ANYNUM.search(ex["rubrics"][i]["criterion"]):
                items.append((ex, i))
    random.Random(0).shuffle(items)
    items = items[:max_items]
    rights = llm.call_many([WRITE.format(convo=convo_text(ex["prompt"]), crit=ex["rubrics"][i]["criterion"]) for ex, i in items],
                           "claude-haiku-5-5", workers=10)
    rng = random.Random(3)
    jobs, keys = [], []
    for k, ((ex, i), r) in enumerate(zip(items, rights)):
        w = scale_numbers(r, rng)
        if not w or w == r or not ANYNUM.search(r):
            continue
        h = f"Depending on your situation, either of these may apply: (a) {r} (b) {w}"
        e1 = single_item_ex(ex, i)
        for name, t in (("right", r), ("wrong", w), ("hedge", h)):
            jobs.append((e1, t, "")); keys.append((k, name))
    pres = J.judge_many(jobs, "presence", workers=10)
    com = J.commit3_many(jobs, workers=10)
    out = [{"k": k, "probe": nm, "prompt_id": e["prompt_id"], "points": e["rubrics"][0]["points"],
            "met": bool(p[0]) if p and p[0] is not None else None, "label": c[0]} for (k, nm), (e, _, _), p, c in zip(keys, jobs, pres, com)]
    (HERE / "pilot10_probes.jsonl").write_text("\n".join(json.dumps(o) for o in out) + "\n")
    return out


def summarize(out, target=0.75):
    by = {}
    for o in out:
        by.setdefault(o["k"], {})[o["probe"]] = o
    ks = [k for k, d in by.items() if all(x in d for x in ("right", "wrong", "hedge"))]
    lab = lambda nm: [by[k][nm]["label"] for k in ks]
    f = st.mean(l == "contradicted" for l in lab("right")); q = st.mean(l == "contradicted" for l in lab("wrong"))
    print(f"items={len(ks)}  v3 judge: f=P(contradicted|right)={f:.3f}  q=P(contradicted|wrong)={q:.3f}")
    for nm in ("right", "wrong", "hedge"):
        L = lab(nm)
        print(f"   {nm:5s} labels: " + ", ".join(f"{x} {sum(l == x for l in L)/len(L):.2f}" for x in ("committed", "evasive", "not_addressed", "contradicted")))
    pm = {nm: st.mean(bool(by[k][nm]["met"]) for k in ks) for nm in ("right", "wrong", "hedge")}
    print(f"   presence met rate: right {pm['right']:.2f} wrong {pm['wrong']:.2f} hedge {pm['hedge']:.2f}")
    g = lambda l, m, h, c: {"committed": 1.0, "evasive": h, "not_addressed": 0.0, "contradicted": c}.get(l, 1.0 if m else 0.0)
    rules = {"presence": None, "v3 h0 c-1": (0, -1), "v3 h0 c-3": (0, -3), "v3 h1 c-3": (1, -3), "v3 h1 c-1 (ConRub-like)": (1, -1), "v3 h0.5 c-3": (0.5, -3)}
    print("   rule: E[credit] right / wrong / hedge -> tau_eff = (H-W)/(R-W)  (commit beats hedge iff p >= tau_eff; <0 = always commit, >1 = never)")
    for name, cfg in rules.items():
        if cfg is None:
            E = {nm: pm[nm] for nm in ("right", "wrong", "hedge")}
        else:
            E = {nm: st.mean(g(by[k][nm]["label"], by[k][nm]["met"], *cfg) for k in ks) for nm in ("right", "wrong", "hedge")}
        tau = (E["hedge"] - E["wrong"]) / (E["right"] - E["wrong"]) if E["right"] != E["wrong"] else float("nan")
        print(f"   {name:24s} {E['right']:+.3f} / {E['wrong']:+.3f} / {E['hedge']:+.3f} -> tau_eff = {tau:+.2f}")
    # c* for h=0 hitting the target threshold, using measured label distributions
    best = None
    for c10 in range(-1, -101, -1):
        c = c10 / 10
        E = {nm: st.mean(g(by[k][nm]["label"], by[k][nm]["met"], 0, c) for k in ks) for nm in ("right", "wrong", "hedge")}
        tau = (E["hedge"] - E["wrong"]) / (E["right"] - E["wrong"])
        if best is None or abs(tau - target) < abs(best[1] - target):
            best = (c, tau)
    print(f"   c* (h=0) for target tau={target}: c*={best[0]:.1f} (tau_eff={best[1]:.2f})")


def adjudicate(n=100, k_max=60):
    """Opus adjudicates contradicted flags (quotes from cached COMMIT3 outputs) on natural vs perturbed answers."""
    import pilot1_stance as P
    rows = P.build_variants(n)
    cand = {"natural": [], "perturbed": []}
    for ex, v in rows:
        for nm, grp in (("plain", "natural"), ("ideal", "natural"), ("numpert", "perturbed")):
            t = v.get(nm)
            if not t:
                continue
            for i, qt in J.commit3_quotes(ex, t).items():
                cand[grp].append((ex, t, i, qt))
    ADJ = ("A grader flagged the response below as CONTRADICTING a physician-written rubric item.\n\n<conversation>\n{c}\n</conversation>\n\n"
           "<response>\n{r}\n</response>\n\nRubric item: \"{it}\"\nFlagged response text: \"{q}\"\n\n"
           "Is the flag correct, i.e. does the response state something factually incompatible with the item that a careful physician "
           "would consider wrong for this user? Answer ONLY JSON: {{\"correct_flag\": true|false, \"reason\": \"<short>\"}}")
    res = {}
    for grp, xs in cand.items():
        random.Random(1).shuffle(xs)
        xs = xs[:k_max]
        outs = llm.call_many([ADJ.format(c=convo_text(ex["prompt"]), r=t, it=ex["rubrics"][i]["criterion"], q=qt) for ex, t, i, qt in xs], "claude-opus-5-5", workers=6)
        ok = []
        for o in outs:
            try:
                ok.append(bool(llm.extract_json(o)["correct_flag"]))
            except Exception:
                pass
        res[grp] = (st.mean(ok) if ok else float("nan"), len(ok), len(cand[grp]))
        print(f"adjudicated precision of 'contradicted' flags on {grp} answers: {res[grp][0]:.2f} (n={res[grp][1]} of {res[grp][2]} flags)")
    return res


def g1_enlarged(n=100):
    import pilot1_stance as P
    from pilot8_twostage import perturb_sub
    rows = P.build_variants(n)
    rng = random.Random(7)
    jobs = []
    for ex, v in rows:
        sub = perturb_sub(v["plain"], rng)
        for t in (v["numpert"], sub):
            if t:
                jobs.append((ex, t, ""))
    a = J.commit3_many(jobs, workers=10)
    b = J.commit3_many([(ex, t, "independent grading run #2") for ex, t, _ in jobs], workers=10)
    same = tot = 0
    for la, lb in zip(a, b):
        for x, y in zip(la, lb):
            if x == "contradicted":
                tot += 1; same += y == "contradicted"
    print(f"G1 (enlarged, numpert+numsub): contradicted repeat rate {same/tot:.2f} (n={tot} flags)")


if __name__ == "__main__":
    out = probes()
    summarize(out)
    g1_enlarged()
    adjudicate()
