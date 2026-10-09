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
