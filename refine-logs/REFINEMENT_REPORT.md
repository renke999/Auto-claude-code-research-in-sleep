# Refinement Report

**Problem**: Rubric RL 奖励对齐人类理想标准并减少 hack（泛泛而谈 / 罗列断言 / 真实性差）
**Initial Approach**: stance-proper rubric credit（I1）
**Date**: 2026-10-09
**Rounds**: 2 / 5（+ 1 轮 research review）
**Final Score**: 7.4 / 10（same-family）
**Final Verdict**: REVISE

## Problem Anchor
见 `FINAL_PROPOSAL.md`（逐字冻结）。

## Output Files
- Review summary: `refine-logs/REVIEW_SUMMARY.md`
- Final proposal: `refine-logs/FINAL_PROPOSAL.md`
- Round files: `round-0-initial-proposal.md`, `round-1-review.md`, `round-1-refinement.md`, `round-2-review.md`
- Score history: `refine-logs/score-history.md`
- Experiment plan / tracker: `refine-logs/EXPERIMENT_PLAN.md`, `refine-logs/EXPERIMENT_TRACKER.md`

## Score Evolution
| Round | Problem Fidelity | Method Specificity | Contribution Quality | Frontier Leverage | Feasibility | Validation Focus | Venue Readiness | Overall | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 7 | 6 | 6 | 7 | 6 | 6 | 5 | 6.3 | REVISE |
| 2 | 8 | 8 | 7 | 7 | 7 | 7 | 6 | 7.4 | REVISE |

## Final Proposal Snapshot
- 对内容型 rubric 条目（axis:accuracy/completeness）按立场给分：承诺 +w / 含糊 0 / 未覆盖 0 / 矛盾 c·w；行为条目与负向条目保持 presence。
- 论点：在逐条 rubric 奖励中，承诺优于含糊的阈值 τ(h,c)=(h−c)/(1−c)；h=1（presence、ConRub 式三态）时 τ=1，加真实性惩罚只会把压力推向含糊；h=0 才能同时给承诺与真实定价。考虑 judge 召回 q 与误报 f 时用 τ_eff，并据此选 c*。
- 证据：API-only pilot（HealthBench，Claude 系 judge，经同文本重判校准）；RL 未做。

## Method Evolution Highlights
1. v1 → v2：把负向条目交还 presence（修极性 bug）；但 v2 把"不确定"算承诺，重开漏洞（P8 A1 FAIL）。
2. v2 → v3：只对内容条目问立场；"在备选之间的不确定"= 含糊；矛盾须引文 + 复问。
3. 理论：τ(h,c) → τ_eff(q, f, h_eff, c)，惩罚强度按 judge 能力标定（c*）。

## Pushback / Drift Log
| Round | Reviewer Said | Author Response | Outcome |
|---|---|---|---|
| R1 | 用 rubric-free 找错器补 rubric 之外的错误? | 不采纳为方法组件（第二个机制），作为局限报告 | rejected（scope） |
| R1 | 主设定改 mean-only 归一化? | 保持 std 归一化为主、mean-only 为配对消融 | accepted as ablation |
| R1 | G2 闸门（理想回答触发率 ≤ plain） | 采纳并预登记 | 后被 R2 判为设计错误并撤回 |
| R2 | c=−1 默认会丢掉真实性定价 | 接受；撤回"按预登记降到 c=−1"的补救，改由 τ_eff 选 c*，c=−1 作消融 | accepted（偏离已在 IDEA_REPORT 公开记录） |

## Remaining Weaknesses
- 无 RL 证据；静态变体是构造的。
- judge 全为 Claude 系；生成器 = judge（Haiku）。
- 医师 BoN-4 粗粒度、功效有限；HealthBench 理想回答过时。
- rubric 之外的编造不被惩罚。

## Raw Reviewer Responses
<details>
<summary>Round 1 / Round 2</summary>

见 `refine-logs/round-1-review.md` 与 `refine-logs/round-2-review.md`（原文保存在各自的 `<details>` 块中）。研究评审（research-review）原文保存在本地 `.aris/traces/research-review/2026-10-09_run01/`。

</details>

## Next Steps
- 若 P10 的 G1'/G2' 通过且 P9c 的 B1/B2 不劣：进入 `/run-experiment`（M1 训练 judge 复现 → M2 4B 预演）。
- 若 G2' 不过：先换更强训练 judge 或收紧 grounding，再测。
