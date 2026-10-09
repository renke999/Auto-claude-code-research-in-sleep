# Experiment Plan

**Problem**: 逐条 presence 型 rubric 奖励在 RL 下被优化成"rubric 分高、专家标准更差"的回答（含糊、罗列断言、错误具体值）；单独加真实性惩罚会把压力转移到含糊。
**Method Thesis**: 对内容型 rubric 条目按立场给分（承诺 +w / 含糊 0 / 未覆盖 0 / 矛盾 −3w），把隐含承诺阈值 τ(h,c)=(h−c)/(1−c) 从 1 降到 0.75——同时给承诺与真实定价；行为条目与负向条目保持 presence。
**Date**: 2026-10-09
**Source**: `refine-logs/FINAL_PROPOSAL.md`（round-1 refinement）；pilot 证据见 `idea-stage/IDEA_REPORT.md`。

## Claim Map

| Claim | Why It Matters | Minimum Convincing Evidence | Linked Blocks |
|---|---|---|---|
| C1（主）：只加真实性惩罚（h=1）会把优化压力转移到含糊；h=0 的 stance credit 同时降低错误与含糊 | 解释并修复"修一个 hack 引出另一个"的 rubric RL 核心失败模式 | GRPO 下：B 臂（h=1,c=−3）相对 A 的含糊指标显著↑而错误↓；C 臂（h=0,c=−3）错误↓且含糊不↑；2 seeds 方向一致；由跨族 judge + 定义无关指标测得 | B1, B2 |
| C2（辅）：stance credit 不牺牲与医师判断的一致性 | 用户的另一核心关切：对齐人类理想标准 | 医师 BoN-4 非劣（API，Pilot 8/9）；RL 后 held-out 共识指标 C ≥ A − 0.01 | B0, B3 |
| C3（机制）：效果由 τ 决定，而非某个具体组件 | 把方法变成可推广的设计原则 | 实测各臂训练后有效阈值与 τ(h,c) 预测排序一致；h=0.5（τ=0.875）介于中间 | B2 |
| Anti-claim：收益不是因为"回答变短/省略" | 排除 2608.00301 式退缩 | C 臂长度、not_addressed 比例、共识分不劣化；mean-only 消融 | B2, B4 |

## Paper Storyline
- 主文：τ(h,c) 命题 + 静态敏感度（Pilot 1/8/9）→ GRPO 三臂主结果（压力转移与关闭）→ 医师锚定的非劣 → 消融（h、c、归一化）→ 迁移（RaR-Science）。
- 附录：pilot 全记录（含被淘汰的 induced-action、HealthBench 理想回答过时的校准、judge 规模 vs 框架）。
- 刻意不放：整体 judge 守卫、rubric 之外的编造检测、演化 rubric。

## Experiment Blocks

### Block 0（API，进行中）：静态闸门与医师 BoN-4
- **Claim tested**：C2 前置 + C1 的静态版本。
- **Data**：HealthBench oss_eval 100 prompt × 13 变体（含 uncwrap/numsub）；meta-eval 1,000 个医师标注池。
- **Systems**：presence；v2 two-stage（Pilot 8）；v3 内容条目 stance（Pilot 9）；h∈{0,0.5,1} × c∈{−1,−3} 网格。
- **Metrics**：配对 Δ（标准化）、同文本重判误罚率、contradicted 重现率/触发率、经验 τ、医师 BoN-4 pick gold / P(best) / 一致性（分 hedging/context 子群）。
- **Success criterion**：Pilot 8 B1 非劣（CI 下界 > −0.01）、B2（hedging 子群 > −0.02）；Pilot 9 G1–G4 全部通过。
- **Failure interpretation**：G1/G2 不过 → c→−1 或换更强训练 judge 后重测；B2 不过 → 检查 v3 的内容/行为分工是否已修复（v3 设计目标）。
- **Priority**：MUST-RUN（已在运行）。

### Block 1（GPU）：GRPO 三臂主实验
- **Claim tested**：C1、C2。
- **Dataset / split**：HealthBench 5,000 prompt 按 prompt_id → 4,000 训练 / 1,000 held-out（held-out 取自 3,671 个带共识条目的 prompt；训练只用 example 级条目）。
- **Compared systems**：A presence（h=1,c=0）；B truth-only（h=1,c=−3；补充 h=1,c=−1 = ConRub 式）；C stance（h=0,c=−3）。相同训练 judge（Qwen3-32B 级，非思考，T=0，两阶段 v3 提示）。
- **Setup**：Qwen3-8B，GRPO，G=8，64 prompt/step，~500 step，lr 1e-6，KL 0.001，std 归一化；2 seeds/臂；每 50 step 存 checkpoint。
- **Metrics**（held-out，**跨模型族** judge，如 GPT-4.1 / Gemini 系，经 meta-eval 医师标注校准）：
  - 主：共识条目分（医师验证的 cluster 级条目）。
  - 含糊：跨族 judge 的 evasive 比例 + **定义无关指标**（每条建议的备选数、hedge 词典命中率）。
  - 真实性：rubric-free 每条声明错误数（P4 框架），拆成 rubric 覆盖 / rubric 之外。
  - 其他：长度、断言密度、not_addressed 比例、presence 分（训练 judge 与跨族 judge 各一）。
- **Success criterion**：B 的含糊指标相对 A ↑（2 seeds 同向，效应 ≥ 0.2 SD），C 的含糊指标 ≤ A 且错误 ↓（≥ 0.2 SD）；共识分 C ≥ A − 0.01。
- **Failure interpretation**：按 `IDEA_REPORT.md` 的 results-to-claims 矩阵：B 不增含糊 → hedge 状态必要性未证；C 坍缩为省略 → 阈值/归一化问题主导；训练 judge 上赢、跨族不赢 → judge 过拟合，放弃方法主张。
- **Priority**：MUST-RUN。

### Block 2（GPU）：机制消融（τ 与归一化）
- **Claim tested**：C3、anti-claim。
- **Systems**：C + {h=0.5,c=−3（τ=0.875）; h=0,c=−1（τ=0.5）; C with mean-only advantage（Dr. GRPO 式）}；1 seed 各。
- **Metrics**：训练后有效承诺阈值（在 held-out 上按策略自报置信/重采样一致性分桶，估计承诺概率对 p 的阶跃位置）、含糊/错误/省略比例、共识分。
- **Success criterion**：有效阈值排序与 τ 预测一致；mean-only 下 c 的边际作用不饱和（std 归一化下单样本优势上界 −√(G−1)）。
- **Priority**：MUST-RUN（h=0.5 与 mean-only）；NICE-TO-HAVE（c=−1）。

### Block 3（GPU + 人工）：人类锚定与 judge 稳健性
- **Claim tested**：C2；排除"定义层面的 hack"。
- **Systems**：A vs C 的最终 checkpoint。
- **Metrics**：100 对盲评人工抽检（优先抽 B vs C 中 evasive 判定分歧的样本；若有医师资源则医师，否则受训标注员 + 明确指南）；训练 judge vs 跨族 judge 的差值曲线。
- **Success criterion**：人工偏好 C ≥ A；训练-跨族差值在 C 中不随训练扩大。
- **Priority**：MUST-RUN（跨族差值）；NICE-TO-HAVE（人工）。

### Block 4（GPU）：迁移
- **Claim tested**：C1 的外部有效性。
- **Data**：RaR-Science-20k（`anisha2102/RaR-Science-20k-o3-mini`，train/val/test），4B 策略，A vs B vs C，1 seed。
- **Metrics**：GPQA-Diamond（若适用）、held-out rubric 分（跨族）、含糊/错误指标。
- **Priority**：NICE-TO-HAVE。

## Run Order and Milestones

| Milestone | Goal | Runs | Decision Gate | Cost |
|---|---|---|---|---|
| M0 | 静态闸门 | Pilot 8/9（API） | B1、B2、G1–G4 全过（否则按预登记调整 c / 判定） | ~1 天 API |
| M1 | 训练 judge 复现 | 在 Qwen3-32B 上重跑 Pilot 9 的 G1–G4（训练 judge ≠ Haiku） | 同上闸门在训练 judge 上成立 | ~4 GPU-h |
| M2 | 4B 预演 | A/B/C 各 1 seed，200 step | 管线正常；B 的含糊趋势可见 | ~150 H100-h |
| M3 | 8B 主实验 | A/B/C × 2 seeds | C1/C2 成功标准 | ~600 H100-h |
| M4 | 消融 | h=0.5、mean-only、(c=−1) | C3 | ~300 H100-h |
| M5 | 评测 + 人工 | 跨族 judge、定义无关指标、人工 100 对 | C2 | ~API + 人工 |
| M6 | 迁移（可选） | RaR-Science 4B | — | ~150 H100-h |

## Compute and Data Budget
- 总计约 1,200–1,400 H100-h（每 8B run ~100 H100-h：策略 + ~1M 次 32B judge 调用）。
- 数据：HealthBench（MIT）、meta-eval 医师标注、RaR-Science-20k；跨族 judge API 预算约 50–100k 次调用。
- 最大瓶颈：judge 吞吐（建议 judge 与策略分卡部署，vLLM 批处理，前缀缓存 rubric/对话）。

## Risks and Mitigations
- **Presence RL 在 4–8B 规模不产生含糊/编造**（前提失败）→ M2 先观察；若不出现，换更易 hack 的较弱训练 judge（Qwen3-8B 级）以复现 hacking 再比较。
- **COMMIT judge 被承诺式措辞欺骗** → 跨族 judge + 定义无关指标 + 人工抽检。
- **省略坍缩**（2608.00301）→ 监控 not_addressed 与长度；mean-only 消融；必要时 c→−1。
- **单一领域** → RaR-Science 迁移。
- **所有 pilot 证据来自 Claude 系 judge** → M1 在开源训练 judge 上复现闸门；评测用非 Claude 跨族 judge。

## Final Checklist
- [ ] 主结果表（A/B/C × 指标 × seeds）
- [ ] 压力转移曲线（含糊、错误、省略随 step）
- [ ] τ 消融图（有效阈值 vs τ 预测）
- [ ] 医师锚定非劣（BoN-4 + 共识分）
- [ ] judge 稳健性（训练 vs 跨族差值）
- [ ] 局限：rubric 之外的编造、单一主领域、HealthBench 理想回答过时
