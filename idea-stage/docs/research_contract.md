# Research Contract: Stance Credit — Pricing Commitment Makes Truth Penalties Safe in Rubric RL

> 当前选定想法的聚焦工作文档（W1 → W1.5 交接）。新会话/上下文压缩后先读本文件，而不是整个 `IDEA_REPORT.md`。

## Selected Idea

- **Description**：逐条 presence 型 rubric 奖励（"提到即得分"）在 RL 下会被利用：含糊提及也得分、错误具体值几乎不扣分；单独加真实性惩罚（如 +1/0/−1 三态）又会把压力推向含糊。我们只对**内容型**条目（axis:accuracy/completeness）按回答的立场给分——承诺 +w、含糊 0、未覆盖 0、矛盾 c*·w（矛盾须引文 + 复问确认；c* 按 judge 的召回/误报标定）——行为条目与负向条目保持 presence。理论：承诺优于含糊的阈值 τ(h,c)=(h−c)/(1−c)，考虑 judge 能力时 τ_eff=(h_eff−1+q(1−c))/((q−f)(1−c))；h=1 时任何真实性惩罚都只会推高含糊。
- **Source**：`idea-stage/IDEA_REPORT.md`，Idea I1（经 research review + 2 轮 method review 修订为 v3）
- **Selection rationale**：triage 第一（唯一同时针对三种 hack 的单一机制）；新颖性 PROCEED 6/10（无已发表 rubric 奖励含 hedged 状态；最近邻 ConRub-Med、Kalai et al.）；静态 pilot 支持核心论点（含糊错误 − 承诺错误：h=1,c=−3 下 +0.127 vs h=0,c=−3 下 −0.016）；对照组 I12（induced action）被 pilot 淘汰。

## Core Claims

1. **主**：在 GRPO 下，只加真实性惩罚（h=1）会提高含糊；stance credit（h=0, c*）同时降低错误具体值与含糊。
2. **辅**：stance credit 与医师判断非劣（医师 BoN-4；RL 后共识指标 ≥ presence − 0.01）。
3. **机制/范围**：效果由 τ_eff 决定（h、c、judge 召回 q）；不解决"看过 rubric 的承诺式堆砌"与 rubric 之外的编造（明确的范围限制）。

## Method Summary

奖励（闭式）：对内容条目 ℓ_i ∈ {committed, evasive, not_addressed, contradicted}，g = {1, h, 0, c}；其余正向条目与所有负向条目用 presence 判定 m_i；R = [Σ_content w_i g(ℓ_i) + Σ_other w_i m_i] / Σ_{w_i>0} w_i，不裁剪；缺失标签回退为 presence；h=0，c=c*。判定：Stage-1 presence（全部条目，≤4 条/调用），Stage-2 COMMIT3（仅内容条目，≤4 条/调用；"在备选之间的不确定"= evasive；条件式建议仅在给出"条件→行动"时算 committed；contradicted 必须引用回答原文，复问一次两次一致才计入）。实现：`idea-stage/pilot/judges.py`（`COMMIT3`、`commit3_many`、`v3_score`）。

训练：Qwen3-8B（预演 4B），GRPO G=8，~500 step，std 归一化（mean-only 为消融）；训练 judge 为开源 Qwen3-32B 级（非思考、T=0）；评测用不同模型族的 judge + meta-eval 医师标注校准。

## Experiment Design

- **Datasets**：HealthBench（5,000 → 4,000 训练 / 1,000 held-out；held-out 取自 3,671 个带共识条目的 prompt）；meta-eval 医师标注（BoN-4）；迁移 RaR-Science-20k。
- **Baselines**：A presence（h=1,c=0）；B truth-only（h=1,c=c*）；消融 h=0,c=−1；h=0.5,c=c*；ConRub 式 h=1,c=−1；mean-only 归一化。
- **Metrics**：共识条目分（跨族 judge）；含糊（跨族 evasive + 定义无关的备选数/hedge 词典）；错误（rubric-free 每条声明错误数，拆 rubric 覆盖 / 之外）；长度、断言密度、not_addressed；行为条目样板指标；训练 vs 跨族 judge 差值。
- **Key hyperparameters**：h（0）、c（c*，由 P10 标定）、G、KL、归一化方式。
- **Compute budget**：~100 H100-h / 8B run；~1,200–1,400 H100-h 总计。

## Baselines

| Method | Dataset | Metric | Score | Source |
|---|---|---|---|---|
| presence（逐条 rubric，chunked Haiku judge） | HealthBench meta-eval（医师 BoN-4，100 池） | 选中回答医师分 / P(best) / 一致性 | 0.852 / 0.733 / 0.727 | 本项目 P7 |
| 整体两两判断（Sonnet，无 rubric） | 同上 | 同上 | 0.825 / 0.622 / 0.657 | 本项目 P7 |
| induced-action agreement | 同上（180 池） | 选中回答医师分 / 一致性 | 0.761 / 0.587 | 本项目 P3（淘汰） |

## Current Results（API-only，静态；RL 未做）

| Method | Dataset | Metric | Score | Notes |
|---|---|---|---|---|
| v3 (h0,c−3) vs presence | HB 100 prompt | Δ 含糊改写 / uncwrap / numpert / numsub（相对 plain） | −0.160/−0.211/−0.255/−0.173 vs −0.048/−0.110/−0.066/−0.064 | P9；经同文本重判校准 |
| v3 闸门 | 同上 | G1 / G3 / G4 | 0.80 / −0.101 [−0.142,−0.060] / PASS | P9 |
| 含糊错误 − 承诺错误 | 同上 | presence / h1c−3 / h0c−3 | −0.049 / +0.127 / −0.016 | P9（逃生通道的静态证据） |
| v3 (h0,c−3) vs presence | meta-eval BoN-4（进行中） | 选中回答医师分差 | 见 IDEA_REPORT P9c | B1/B2 再登记 |
| 条目对齐探针 | HB 含数字内容条目 | f、q、τ_eff、c* | 见 IDEA_REPORT P10 | 进行中 |

## Key Decisions

- 只对内容条目给立场分：避免误伤医师要求的"承认不确定/索取信息"（由行为条目的 presence 定价）。
- h=0 而非 0.5：τ 最低、且让最不稳定的 evasive/not_addressed 边界不影响奖励。
- c 由 judge 标定（c*）而非固定 −1：q<0.5 时 c=−1 会让"承诺错误"重新有利可图（P9 静态数据已显示）。
- 原 G2 闸门撤回（设计错误），改为人工裁决精确率 G2'；所有偏离均在 `IDEA_REPORT.md` 公开记录。
- 已知局限：rubric 之外的编造不被惩罚；"看过 rubric 的承诺式堆砌"不在范围；所有 pilot judge 为 Claude 系；HealthBench 理想回答过时。

## Status

- [x] Idea selected
- [x] Static pilots (API-only) + pre-registered gates（部分进行中：P9c、P10）
- [ ] 训练 judge（开源 32B）上复现闸门（M1）
- [ ] 4B 预演（M2）
- [ ] 8B 主实验（M3）
- [ ] 消融（M4）
- [ ] 跨族评测 + 人工抽检（M5）
- [ ] Paper draft

**Next step**：`/experiment-bridge` 或 `/run-experiment`，按 `refine-logs/EXPERIMENT_PLAN.md` 的 M1 → M2 顺序执行。
