"""Chunked rubric judges for the idea pilots.

presence: HealthBench-style binary "criterion met?" (status quo reward)
stance:   for each criterion, what the response actually DOES with its content:
            committed     - states/recommends it definitively, tailored to this user
            hedged        - mentions it only as one possibility among alternatives, or vaguely/conditionally
            absent        - does not address it
            contradicted  - commits to something incompatible with it (e.g. a different dose/threshold/action)
          For negative-point criteria (undesirable behaviour), "committed" means the behaviour is clearly present,
          "hedged" means it appears only as one option / in passing.
Chunking (<= CHUNK criteria per call) avoids the many-verdicts-per-call overload artefact (2608.06422).
"""
from __future__ import annotations

import llm
from common import convo_text

CHUNK = 4
JUDGE = "claude-haiku-5-5"

PRESENCE = """You are grading an AI assistant's response against rubric items written by physicians.

<conversation>
{convo}
</conversation>

<response>
{response}
</response>

Rubric items (positive points = desirable behaviour; negative points = undesirable behaviour):
{items}

For EACH item decide whether the response meets the described criterion (for negative-point items, "met" means the undesirable behaviour IS present). Judge only what the response actually says.
Return ONLY a JSON list in order: [{{"id": <id>, "met": true|false}}, ...]"""

STANCE = """You are grading an AI assistant's response against rubric items written by physicians. For each item, classify what the response actually DOES with the item's content.

<conversation>
{convo}
</conversation>

<response>
{response}
</response>

Rubric items (positive points = desirable behaviour; negative points = undesirable behaviour):
{items}

Labels:
- "committed": the response clearly and definitively states/does what the item describes, applied to this user's situation.
- "hedged": the item's content appears only as one possibility among several alternatives, conditionally, vaguely, or without committing (e.g. "options include X, Y or Z", "you might consider X").
- "absent": the response does not address the item at all.
- "contradicted": the response commits to something incompatible with the item (e.g. a different dose, threshold, timing, or recommendation).
Return ONLY a JSON list in order: [{{"id": <id>, "stance": "committed"|"hedged"|"absent"|"contradicted"}}, ...]"""


def _items(rubrics, idx):
    return "\n".join(f"{i}. ({rubrics[i]['points']:+d} pts) {rubrics[i]['criterion']}" for i in idx)


def prompts(ex, response, mode="presence", tag=""):
    r = ex["rubrics"]
    tpl = PRESENCE if mode == "presence" else STANCE
    out = []
    for s in range(0, len(r), CHUNK):
        idx = list(range(s, min(s + CHUNK, len(r))))
        p = tpl.format(convo=convo_text(ex["prompt"]), response=response, items=_items(r, idx))
        out.append((idx, p + (f"\n\n[{tag}]" if tag else "")))
    return out


def parse(outputs, chunks, n, mode="presence"):
    key = "met" if mode == "presence" else "stance"
    res = [None] * n
    for (idx, _), o in zip(chunks, outputs):
        try:
            arr = llm.extract_json(o)
        except Exception:
            continue
        for obj in arr:
            try:
                i = int(obj["id"])
            except Exception:
                continue
            if i in idx:
                res[i] = obj.get(key)
    return res


def judge_many(jobs, mode="presence", workers=16, model=JUDGE):
    """jobs: list of (ex, response, tag). Returns list of per-criterion verdict lists."""
    chunk_lists = [prompts(ex, resp, mode, tag) for ex, resp, tag in jobs]
    flat = [p for cl in chunk_lists for _, p in cl]
    outs = llm.call_many(flat, model, workers=workers)
    res, k = [], 0
    for (ex, _, _), cl in zip(jobs, chunk_lists):
        res.append(parse(outs[k:k + len(cl)], cl, len(ex["rubrics"]), mode))
        k += len(cl)
    return res


def presence_score(rubrics, met):
    pos = sum(r["points"] for r in rubrics if r["points"] > 0)
    got = sum(r["points"] for r, m in zip(rubrics, met) if m)
    return max(0.0, min(1.0, got / pos)) if pos else 0.0


def stance_as_presence(rubrics, st):
    """What a presence judge would give if it credited committed OR hedged mentions."""
    return presence_score(rubrics, [s in ("committed", "hedged") for s in st])


PROPER = {"committed": 1.0, "hedged": 0.0, "absent": 0.0, "contradicted": -3.0}


def proper_score(rubrics, st):
    """Commitment-proper credit (Brier relative to silence, rescaled so a committed hit = presence credit):
    positive item: committed +w, hedged/absent 0, contradicted -3w; negative item: committed -|w|,
    hedged -|w|/2, absent/contradicted 0. Normalised by positive points; not clipped below 0."""
    pos = sum(r["points"] for r in rubrics if r["points"] > 0)
    tot = 0.0
    for r, s in zip(rubrics, st):
        if s is None:
            continue
        if r["points"] > 0:
            tot += r["points"] * PROPER.get(s, 0.0)
        else:
            tot += r["points"] * {"committed": 1.0, "hedged": 0.5}.get(s, 0.0)
    return tot / pos if pos else 0.0


def ablation_score(rubrics, st, hedged=0.0, contra=-3.0):
    """Stance-credit family for ablations: positive items committed +1, hedged `hedged`, absent 0,
    contradicted `contra`; negative items as in proper_score. hedged=1,contra=-1 ~ ConRub-Med three-state
    (no hedged state: a hedged mention counts as correct); hedged=1,contra=-3 isolates the hedged state."""
    pos = sum(r["points"] for r in rubrics if r["points"] > 0)
    tot = 0.0
    for r, s in zip(rubrics, st):
        if s is None:
            continue
        if r["points"] > 0:
            tot += r["points"] * {"committed": 1.0, "hedged": hedged, "contradicted": contra}.get(s, 0.0)
        else:
            tot += r["points"] * {"committed": 1.0, "hedged": 0.5}.get(s, 0.0)
    return tot / pos if pos else 0.0


# ---------------------------------------------------------------------------------------------------------------
# v2 (after review round 1): two-stage stance credit.
#   Stage 1 = the unchanged PRESENCE judge (all items).
#   Stage 2 = COMMIT judge on POSITIVE items only (fixes the negative-item polarity bug), with definitions that
#   separate evasive alternatives from appropriate conditional advice, and example wording that does not reuse
#   the phrases of the hedge-rewrite template.
# Credit (positive item, weight w): contradicted -> c*w (any presence verdict); presence met & evasive -> h*w;
#   presence met otherwise -> +w; presence unmet & not contradicted -> 0. Negative items: presence verdict only.
# ---------------------------------------------------------------------------------------------------------------
COMMIT = """You are checking HOW an AI assistant's response handles specific rubric items written by physicians.

<conversation>
{convo}
</conversation>

<response>
{response}
</response>

Rubric items (each describes something a good response should do):
{items}

For each item choose exactly one label:
- "committed": the response tells this user what to do / what is the case for the item's content, in a form the user can act on. Conditional guidance that says what to do under which circumstance (e.g. "if your temperature stays above 39 °C for two days, see a doctor"), honest statements of uncertainty, and questions asking the user for missing information all count as committed.
- "evasive": the item's content appears, but only inside a menu of alternatives with no indication of which one applies to this user or how to choose between them, or so non-specifically that the user could not act on it.
- "not_addressed": the response does not cover the item's content.
- "contradicted": the response states or recommends something factually incompatible with the item (e.g. a different dose, threshold, timing, drug, or the opposite recommendation).
Return ONLY a JSON list in order: [{{"id": <id>, "label": "committed"|"evasive"|"not_addressed"|"contradicted"}}, ...]"""


def commit_prompts(ex, response, tag=""):
    r = ex["rubrics"]
    pos = [i for i, x in enumerate(r) if x["points"] > 0]
    out = []
    for s in range(0, len(pos), CHUNK):
        idx = pos[s:s + CHUNK]
        items = "\n".join(f"{i}. {r[i]['criterion']}" for i in idx)
        p = COMMIT.format(convo=convo_text(ex["prompt"]), response=response, items=items)
        out.append((idx, p + (f"\n\n[{tag}]" if tag else "")))
    return out


def commit_many(jobs, workers=16, model=JUDGE):
    chunk_lists = [commit_prompts(ex, resp, tag) for ex, resp, tag in jobs]
    flat = [p for cl in chunk_lists for _, p in cl]
    outs = llm.call_many(flat, model, workers=workers)
    res, k = [], 0
    for (ex, _, _), cl in zip(jobs, chunk_lists):
        lab = [None] * len(ex["rubrics"])
        for (idx, _), o in zip(cl, outs[k:k + len(cl)]):
            try:
                arr = llm.extract_json(o)
            except Exception:
                continue
            for obj in arr:
                try:
                    i = int(obj["id"])
                except Exception:
                    continue
                if i in idx:
                    lab[i] = obj.get("label")
        res.append(lab)
        k += len(cl)
    return res


def two_stage_score(rubrics, met, lab, h=0.0, c=-3.0):
    pos = sum(r["points"] for r in rubrics if r["points"] > 0)
    tot = 0.0
    for r, m, l in zip(rubrics, met, lab):
        w = r["points"]
        if w > 0:
            if l == "contradicted":
                tot += c * w
            elif m:
                tot += (h * w) if l == "evasive" else w
        elif m:
            tot += w
    return tot / pos if pos else 0.0


# ---------------------------------------------------------------------------------------------------------------
# v3 (after refine round 1): content items only + quote-grounded, double-checked contradictions.
#   - COMMIT labels are asked ONLY for positive items tagged axis:accuracy / axis:completeness ("content items").
#     Behaviour items (context_awareness, communication_quality, instruction_following) and all negative items keep
#     the presence verdict, so physicians' own "acknowledges uncertainty / seeks context" items price legitimate
#     uncertainty.
#   - On content items, uncertainty BETWEEN alternatives is evasive; conditional advice is committed only if it gives
#     an explicit condition -> action rule for this user.
#   - "contradicted" must quote the conflicting response span; spans that do not occur in the response are
#     downgraded; flagged items are re-asked once and count only if both runs say contradicted.
# Credit (single label space; presence = special case h=1, c=0):
#   content item: committed +w, evasive h*w, not_addressed 0, contradicted c*w   (missing label -> presence verdict)
#   other positive items and negative items: presence verdict.   Reward unclipped, / sum of positive points.
# ---------------------------------------------------------------------------------------------------------------
CONTENT_AXES = {"axis:accuracy", "axis:completeness"}

COMMIT3 = """You are checking HOW an AI assistant's response handles specific content items from a physician-written rubric.

<conversation>
{convo}
</conversation>

<response>
{response}
</response>

Content items (each names content a good response should state):
{items}

For each item choose exactly one label:
- "committed": the response states the item's content as its answer for this user. A conditional rule counts only if it gives an explicit condition and the action to take under it (e.g. "if X happens, do Y").
- "evasive": the item's content appears, but the response does not commit to it: it is one of several alternatives without a choice between them, it is wrapped in uncertainty between it and another option (e.g. "maybe X, or possibly Y"), or it is too non-specific to act on.
- "not_addressed": the response does not cover the item's content.
- "contradicted": the response states something factually incompatible with the item (different dose, threshold, timing, drug, or the opposite recommendation). You MUST copy the exact conflicting words from the response into "quote".
Return ONLY a JSON list in order: [{{"id": <id>, "label": "...", "quote": "<exact words from the response, only for contradicted>"}}, ...]"""


def content_idx(ex):
    return [i for i, r in enumerate(ex["rubrics"]) if r["points"] > 0 and CONTENT_AXES & set(r.get("tags", []))]


def _norm(s):
    return " ".join((s or "").lower().replace("’", "'").split())


def commit3_many(jobs, workers=10, model=JUDGE, recheck=True):
    """jobs: (ex, response, tag). Returns per-job label lists (None for non-content items)."""
    def chunks(ex, resp, tag):
        idx = content_idx(ex)
        out = []
        for s in range(0, len(idx), CHUNK):
            sub = idx[s:s + CHUNK]
            items = "\n".join(f"{i}. {ex['rubrics'][i]['criterion']}" for i in sub)
            p = COMMIT3.format(convo=convo_text(ex["prompt"]), response=resp, items=items)
            out.append((sub, p + (f"\n\n[{tag}]" if tag else "")))
        return out

    cls = [chunks(ex, resp, tag) for ex, resp, tag in jobs]
    outs = llm.call_many([p for cl in cls for _, p in cl], model, workers=workers)
    labs, k = [], 0
    for (ex, resp, _), cl in zip(jobs, cls):
        lab = [None] * len(ex["rubrics"])
        nr = _norm(resp)
        for (sub, _), o in zip(cl, outs[k:k + len(cl)]):
            try:
                arr = llm.extract_json(o)
            except Exception:
                continue
            for obj in arr:
                try:
                    i = int(obj["id"])
                except Exception:
                    continue
                if i in sub:
                    l = obj.get("label")
                    if l == "contradicted" and (not obj.get("quote") or _norm(obj["quote"])[:60] not in nr):
                        l = "not_addressed"  # ungrounded contradiction -> downgrade
                    lab[i] = l
        labs.append(lab)
        k += len(cl)
    if recheck:
        flagged = [(j, i) for j, lab in enumerate(labs) for i, l in enumerate(lab) if l == "contradicted"]
        if flagged:
            rj = [(jobs[j][0], jobs[j][1], (jobs[j][2] + " recheck").strip()) for j, _ in flagged]
            # re-ask the whole content set for the flagged responses (cached per response)
            seen = {}
            uniq = []
            for (j, i), job in zip(flagged, rj):
                if j not in seen:
                    seen[j] = len(uniq); uniq.append(job)
            re = commit3_many(uniq, workers, model, recheck=False)
            for j, i in flagged:
                if re[seen[j]][i] != "contradicted":
                    labs[j][i] = re[seen[j]][i] or "not_addressed"
    return labs


def v3_score(rubrics, met, lab, h=0.0, c=-3.0):
    pos = sum(r["points"] for r in rubrics if r["points"] > 0)
    tot = 0.0
    for r, m, l in zip(rubrics, met, lab):
        w = r["points"]
        if w > 0 and l is not None:
            tot += w * {"committed": 1.0, "evasive": h, "not_addressed": 0.0, "contradicted": c}.get(l, 1.0 if m else 0.0)
        elif m:
            tot += w
    return tot / pos if pos else 0.0


def commit3_quotes(ex, response, tag="", model=JUDGE):
    """Re-parse the (cached) COMMIT3 outputs for one response and return {item_index: quote} for contradicted labels."""
    idx = content_idx(ex)
    out = {}
    for s0 in range(0, len(idx), CHUNK):
        sub = idx[s0:s0 + CHUNK]
        items = "\n".join(f"{i}. {ex['rubrics'][i]['criterion']}" for i in sub)
        p = COMMIT3.format(convo=convo_text(ex["prompt"]), response=response, items=items) + (f"\n\n[{tag}]" if tag else "")
        try:
            arr = llm.extract_json(llm.call(p, model))
        except Exception:
            continue
        for obj in arr:
            try:
                i = int(obj["id"])
            except Exception:
                continue
            if i in sub and obj.get("label") == "contradicted":
                out[i] = obj.get("quote", "")
    return out
