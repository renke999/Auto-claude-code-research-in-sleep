# Round 1 Review: Safe Truth Penalties for Rubric RL (same-family reviewer)

> Reviewer: claude-opus-5-5, **same model family as the author**. This is not a cross-model receipt.
> Reviewed: `refine-logs/round-0-initial-proposal.md`, with `idea-stage/IDEA_REPORT.md` (Pilot Results + External Critical Review), `idea-stage/pilot/judges.py` (v2 COMMIT + `two_stage_score`), and recomputation from `pilot1a_results.jsonl` and the HealthBench files.

## Parsed summary

| Dimension | Score | Weight |
|---|---|---|
| Problem Fidelity | 7 | 15% |
| Method Specificity | 6 | 25% |
| Contribution Quality | 6 | 25% |
| Frontier Leverage | 7 | 15% |
| Feasibility | 6 | 10% |
| Validation Focus | 6 | 5% |
| Venue Readiness | 5 | 5% |
| **Overall** | **6.3** | |

**Verdict: REVISE.** Drift: NONE (two scope notes).

**Top action items**
1. **CRITICAL:** The v2 COMMIT label counts "honest uncertainty" as committed, which reopens the hedge escape channel. Fix by factorizing on item type: stance applies only to accuracy/completeness items, and behavior items are scored on presence only.
2. **CRITICAL:** The −3w penalty multiplies the least reliable label. In v1, `contradicted` is reproduced on re-judge only 36% of the time and fires on 23% of physician-written answers. Fix with quote-grounded contradiction and a second confirming call on any flagged item, and gate RL on the measured reliability.
3. **CRITICAL (claim):** Make τ(h,c) = (h−c)/(1−c) the spine of the method. Measure each judge's effective h, and add a hedge(wrong-value) static probe.
4. **IMPORTANT:** The data split cannot work as written: excluding meta-eval leaves 1,329 prompts. Every cited static number comes from the superseded v1 judge, and P8 has no results yet. Add one hedging metric that does not depend on the label definition, and swap the transfer set off deep research.

<details>
<summary>Raw reviewer response</summary>

**Anchor check.** The method targets the must-solve bottleneck, which has three parts: (i) commitment blindness, (ii) free bluffing, (iii) the hedge escape channel. Assertion listing is named in the bottom line, but the proposal correctly leaves it alone (P1: rubric-aware lists gain +0.92 SD under both rules). The paper must state outright that it makes no claim about listing.

**Checked against raw data** (`pilot1a_results.jsonl`, v1 STANCE judge, positive items):
- Same-text re-judge stability: `contradicted` P(rep1|rep0) = **0.36** (Jaccard 0.26). For comparison: `hedged` 0.68, `committed` 0.91, presence-met 0.91.
- At least one `contradicted` label lands on **23% of physician ideal answers** and 20% of plain answers (numpert: 58%).
- The `hedged` rewrite has a *lower* contradiction rate than plain (0.015 vs 0.026 per item). This is label-level evidence that hedging already dodges the truth penalty. It supports the escape-channel premise better than the Δ=+0.00 you cite.
- oss_eval has 5,000 prompts and meta-eval covers 3,671 of them. Excluding meta-eval leaves **1,329**, not ~4k.
- P8 has no results yet. Every static number you cite (−0.54/−0.81 SD, Δ=+0.00) comes from the superseded v1 judge, not the proposed COMMIT judge.

### Scores
| Dim | Score |
|---|---|
| 1 Problem Fidelity | 7 |
| 2 Method Specificity | 6 |
| 3 Contribution Quality | 6 |
| 4 Frontier Leverage | 7 |
| 5 Feasibility | 6 |
| 6 Validation Focus | 6 |
| 7 Venue Readiness | 5 |
| **Overall** | **6.3** |

**C1: uncertainty loophole (CRITICAL; Problem Fidelity / Method).** v2 counts "honest statements of uncertainty" and "asking for missing info" as committed. Under RL, a hedge like "likely 500 mg, though 1000 mg is possible; I can't be certain" gets labeled committed and earns +w. The escape channel reopens in a new surface form, so bottleneck (iii) is no longer solved.
*Fix:* factorize by **item type**, not by response form. Apply COMMIT only to content items (HealthBench `axis:accuracy` + `axis:completeness`, 72% of positive items). For these items:
- uncertainty between alternatives is *evasive*;
- conditional advice counts as committed only when it gives a decision rule (condition → action) for this user.

Behavior items (context_awareness, communication, instruction_following) stay presence-only. Physicians' own "acknowledges uncertainty / seeks context" items then price legitimate uncertainty. This fixes the B2 subgroup harm by construction, removes the carve-out, and saves calls. For transfer data, tag items once offline. Add an "uncertainty-wrapped" rewrite to P8-A and pre-register evasive(uw) ≥ evasive(hedged).

**2. Method Specificity (IMPORTANT).** The code is concrete, but three load-bearing choices are unspecified or wrong:
- The committed/evasive boundary (C1).
- The reward range: unclipped ≈[−3,1] vs presence clipped to [0,1]. This matters for the mean-only arm.
- The data split, which cannot be done as written.

Also unstated: the parse-failure fallback (met∧None currently gives +w, i.e. silent presence) and the Qwen3-32B thinking mode.
*Fix:* write R_{h,c} in closed form, including fallback and clipping. Split all 5,000 prompts by prompt_id (~4k/1k, stratified by theme). Excluding meta-eval is unnecessary: the reward has no trainable parameters, and physician BoN-4 scores fixed completions. If you want calibration on the same prompts, draw the held-out set from meta-eval.

**3. Contribution Quality.** The delta over ConRub-Med is one state, and over Kalai it is per-item application. The paper stands only if the RL pressure-transfer result appears (arm B hedging↑). The cited "ConRub Δ=+0.00 on the hedge rewrite" shows that hedging a *correct* answer is free. It does not show that hedging beats committing to an *uncertain* value. The supporting contribution (diagnostic + BoN-4 protocol) adds sprawl.
*Fix (CRITICAL for the claim; cheap):* make the decision theory the spine of the method. Let p = P(policy's specific is correct). Then:
- commit EV = p + (1−p)c
- hedge-containing-truth EV = h
- omit EV = 0
- commit ≥ hedge iff **p ≥ τ(h,c) = (h−c)/(1−c)**

This gives presence (h≈1, c=0) → 1; ConRub (1,−1) → 1; (1,−3) → 1; stance (0,−3) → 0.75; your h=0.5 fallback → 0.875. The result is a one-line thesis ("a truth penalty is safe iff h ≤ 0") and a falsifiable prediction for each arm. It also shows that raising h to protect uncertainty raises the commitment threshold. It predicts that presence *also* has the channel, damped only by the judge's partial disjunction penalty, so measure each judge's **effective h**. Add one static probe: hedge(numpert) ("X or Y", one value true) vs numpert, under each R_{h,c}. Fold the supporting contribution into evaluation.

**5. Feasibility (CRITICAL).** The −3w term multiplies the noisiest label. With G=8, spurious contradictions (36% reproducible) will dominate the advantages. They push the policy to drop specifics or to echo the rubric (aware lists have the lowest contra rate, 0.013). Pilot labels came from Haiku, while training uses Qwen3-32B, whose evasive/contradicted κ is unmeasured. The 40 H100-h/run estimate looks 2–3× optimistic for ~1M 32B calls of ~1.5k tokens, though this is not blocking.
*Fix:* quote-grounded contradiction.
1. The judge must return the conflicting response span and the item's value.
2. A span that fails a string match is downgraded to not_addressed.
3. A flagged item is re-queried once and counts only if both runs agree (~+3% calls).

Gate RL on P8 data: P(contra|contra) ≥ 0.6 and contra rate on ideal ≤ plain. Rerun P8-A with Qwen3-32B (κ plus the key deltas).

**6. Validation Focus (IMPORTANT).** Claim 1's evasive rate is measured with the reward's own label *definition*. A cross-family judge removes judge quirks but not definition-level hacking (C1). ResearchRubrics is a deep-research set, which conflicts with a stated non-goal.
*Fix:*
- Add one hedging metric that does not depend on the label definition: alternatives per recommendation plus hedge-cue rate.
- Aim the 100-pair human spot-check at C-vs-B evasive cases.
- Split rubric-free errors into rubric-covered vs off-rubric claims, since the truth price only reaches covered content (static τ 0.31 vs 0.75 design).
- For transfer, use a non-retrieval rubric-RL set, e.g. RaR-Science-20k (`anisha2102/RaR-Science-20k-o3-mini`), or justify the choice.

**7. Venue Readiness (IMPORTANT).** No result exists yet for the proposed judge. Restate the Technical Gap with P8 numbers and label v1 numbers as such.

### Simplification Opportunities
1. Item-type factorization (C1). It removes the prompt carve-out, shrinks the COMMIT set, and makes the h→0.5 fallback unnecessary.
2. Score positive items from the COMMIT label alone (committed +w / evasive hw / not_addressed 0 / contradicted cw) and use presence only for negative items. This deletes the 2×4 cross-table and its ad-hoc conflict rules (met∧not_addressed→+w; committed∧¬met→0) and cuts ~40% of judge calls. Presence ≈ R_{1,0} then becomes a nested special case. It can be tested for free, because P8 already collects both labels.
3. Remove the "supporting contribution" as a claimed contribution.

### Modernization Opportunities
1. Evidence-grounded (quote-then-verify) contradiction with confirm-on-flag, in line with commit-first / grounded judging (2607.05904). Nothing else: an open LLM judge plus GRPO already fits.

### Drift Warning
NONE. Two notes:
- (a) Do not close the off-rubric-error gap with the rubric-free error finder. That would be a second mechanism; report the gap as a limitation instead.
- (b) Keep std-GRPO as the main setting and mean-only as a matched ablation (a config choice, not an optimizer change). State the threshold claim per sample and verify it empirically.

### Verdict: **REVISE**
This is one focused idea with an honest scope. It becomes a strong paper if three things hold:
- τ(h,c) is the spine of the argument;
- item-type factorization closes the uncertainty loophole;
- the −3w term rests on a reliable label.

</details>
