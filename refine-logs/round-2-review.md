# Round 2 Review: Pricing Commitment Makes Truth Penalties Safe (same-family reviewer)

> Reviewer: claude-opus-5-5, the **same model family as the author** (not a cross-model receipt). Numbers below are recomputed from the pilot9 and pilot9b jsonl files and full oss_eval.

## Parsed summary

| Dimension | R1 | R2 | Weight |
|---|---|---|---|
| Problem Fidelity | 7 | 8 | 15% |
| Method Specificity | 6 | 8 | 25% |
| Contribution Quality | 6 | 7 | 25% |
| Frontier Leverage | 7 | 7 | 15% |
| Feasibility | 6 | 7 | 10% |
| Validation Focus | 6 | 7 | 5% |
| Venue Readiness | 5 | 6 | 5% |
| **Overall** | 6.3 | **7.4** | |

**Verdict: REVISE.**
- **Anchor:** PRESERVED. It is verbatim, and the τ≤0 reconciliation note is fine.
- **Contribution:** sharper, with one thesis.
- **Method:** simpler. It has a single label space and no trainable parts.
- **Blocking issues:** the c→−1 default, the mis-specified G2, and Pilot 9c, which has no results.

<details>
<summary>Raw reviewer response</summary>

**Anchor.** The anchor is verbatim. The item-type split closes bottleneck (iii) without reopening the v2 loophole. G3 also holds at c=−1: −0.105 [−0.142, −0.067]. However, the M2 default of c=−1 puts bottleneck (ii) and success condition (1) at risk.

**Checked against raw data**
- **G1:** 16/20, Wilson CI [0.58, 0.92]; in the reverse direction it is 16/22. This is a point-estimate pass on a small sample.
- **G2:** Paired, the ideal answer fires alone 10 times vs plain alone 6 (Haiku, exact p≈0.45), and 10 vs 4 (Sonnet, p≈0.18). The "FAIL" is not significant.
  - The ideal answer commits less often (45% vs 68% of content labels), but when it commits it is flagged twice as often (7.5% vs 3.4%).
  - Haiku and Sonnet flags overlap on 22 of ~37 items.
  - **Quotes are not saved.** `commit3_many` returns labels only, so the flags cannot be adjudicated.
- **The thesis has real static support.** I computed hedged-wrong − committed-wrong under (h=1,c=−3) minus the same under (h=0,c=−3): +0.143 [0.09, 0.20].
- **Empirical τ CIs are wide:** h0c−3 [−0.27, 0.45], h0.5c−3 [0.13, 0.69], h1c−1 [0.12, 0.87]. "Ordering matches theory" is suggestive only.
- **Content share is wrong.** Content items are 71.8% of positive items (74.4% of points) on oss_eval, not 78%.
- **"Specificity 0.44 vs 0.00" is mislabelled.** It is paired discordance on injected errors, which is a sensitivity measure.
- **Pilot 9c has no output.** The log is empty and there is no results file. The "见下" in IDEA_REPORT points at nothing.

**G2 and c→−1 (main issue)**

*G2 is mis-specified.* I proposed it in round 1, and I retract it:
- It is underpowered: n=100 against a base rate of about 12%.
- It is anchored on ideal answers that P6 shows are not superior (preferred only 52.5% of the time).
- It measures how often flags fire. RL depends instead on precision on correct content (f) and recall on wrong content (q).

*c→−1 is the wrong trade.* It does not change what G2 measures, as the authors concede. It also exposes a missing mechanism: the nominal τ(h,c) ignores the judge. With recall q, false-flag rate f and hedge leak h_eff:

τ_eff = (h_eff − 1 + q(1−c)) / ((q − f)(1−c))

With h=0, bluffing carries any price only if q > 1/(1−c): q > 0.5 at c=−1, q > 0.25 at c=−3.

The pilot suggests q is low. A numpert response (~2 values changed) gains about 0.56 contradicted items over plain; a numsub response (3 values) gains about 0.37. So q is plausibly 0.25–0.55, and at c=−1 the truth price for subtle errors is about zero or negative.

The static data agree. Under h0c−1:
- committed-wrong outscores hedged-correct: uncwrap − numpert = −0.069 [−0.134, −0.000];
- committed-wrong outscores hedged-wrong: −0.098 [−0.167, −0.030];
- the empirical τ (−0.46) is *below* presence (−0.35).

The noise that c=−1 saves is small:

| | c=−3 | c=−1 | presence |
|---|---|---|---|
| Same-text reward SD | 0.167 | 0.145 | 0.136 |
| Truth SNR, numpert | 1.53 | 1.03 | 0.49 |
| Truth SNR, numsub | 1.04 | 0.73 | 0.47 |

So h=0 with c=−1 still prices commitment but probably not truth. Arm C could convert presence's partially credited hedges into confident guesses that are rarely caught, contradicting success condition (1).

*Fix:*
- Measure (q, f, h_eff) with item-aligned probes: perturb only rubric-covered values, hedge exactly that value as "X or Y", and commit correctly on the same span. This is also the round-1 hedge(numpert) probe, still not run.
- Choose c\* to hit a target τ_eff on the training judge (M1).
- Replace G2 with a precision gate on 100 quote-logged flags (50 ideal, 50 plain), adjudicated by an independent judge plus a clinician sample.

**Weak training signal.** Only about 12% of natural responses carry any contradicted flag, so commitment credit dominates the gradient. If 8B presence-RL produces no rubric-covered errors, the A-vs-C error comparison is null by construction. Log A's covered-error rate in M2 before M3.

**Weak integration point (pressure transfer inside C).** 25.6% of positive points stay presence-scored. About 12.5% are uncertainty/context-seeking behaviour items (regex estimate), present in 66% of prompts. Closing the content-hedge channel can push pressure into appended uncertainty boilerplate that collects these points, which your own thesis predicts. To catch it:
- split the definition-free hedge metric into hedges attached to content vs standalone;
- track each arm's behaviour-item credit;
- pre-register both.

**Pseudo-novelty risk.** τ(0,c) is Kalai's threshold, and τ(1,c)=1 is a one-line expected-value fact. "Safe only if h≤0" is imprecise: any h<1 restores a threshold, and h≤0 only adds that hedging never strictly beats omission. The novelty rests on the hedge action in per-item rubric rewards, on τ_eff (which turns a remark into a design rule), and on the RL transfer result.

**Complexity.** The method is simpler; the new sprawl is c∈{−1,−3} in both B and C. Under h=0, evasive and not_addressed pay the same, so the noisiest label boundary (repeat 0.77–0.78) cannot affect arm C's reward. State this as a robustness argument for h=0.

**Spec nits**
- **The documents disagree.** The Thesis says −3w with τ=0.75; the reward section uses c=−1 as default; EXPERIMENT_PLAN Block 1 has C = h0c−3 with c=−1 as nice-to-have. None matches the "10 runs" budget.
- **Unconfirmed contradictions are mis-scored.** They are downgraded to not_addressed (−w relative to committed). Use the recheck label instead.

### Simplification Opportunities
1. Main grid A, B(h=1,c\*), C(h=0,c\*); c=−1 and h=0.5 as single-seed ablations.
2. Under h=0 the reward needs three states (committed / contradicted / other). Keep evasive for diagnostics and arm B.
3. Drop the response-level empirical τ (confounded by how many items each variant touches) in favour of item-aligned (h_eff, q, f).

### Modernization Opportunities
1. *(Optional)* Threshold the open training judge's P(contradicted) logprob instead of making a second call. This gives an f–q curve for choosing c\*.

### Drift Warning
NONE. Note: making c=−1 the default silently narrows the paper to "price commitment" and drops bottleneck (ii). Do not let that happen.

### Remaining Action Items (ranked)
1. **CRITICAL:** Make τ_eff the spine. Run the item-aligned probes, choose c\* from them, and make c=−1 an ablation.
2. **CRITICAL:** Log quotes and replace G2 with a precision gate. Enlarge G1 to ≥50 flags.
3. **CRITICAL:** Get Pilot 9c B1/B2 results, especially the B2 hedging subgroup.
4. **IMPORTANT:** Pre-register the behaviour-boilerplate metrics; check A's covered-error rate in M2.
5. **IMPORTANT:** Reconcile Thesis, reward and plan. Fix the 78%, "specificity" and τ-CI statements, and rephrase the h≤0 claim.
6. **MINOR:** Use the recheck label when a contradiction is not confirmed.

### Verdict: **REVISE**

</details>
