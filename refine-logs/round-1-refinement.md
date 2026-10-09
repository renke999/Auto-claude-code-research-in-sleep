# Round 1 Refinement

## Problem Anchor（逐字复用 Round 0）

- **Bottom-line problem**：用逐条 rubric 作为奖励的 RL（Rubric RL）会把开放式回答（以医疗问答为代表）优化成"rubric 分高、但按专家标准更差"的回答——泛泛而谈（含糊、不承诺）、只在罗列断言、具体事实错误。
- **Must-solve bottleneck**：主流 rubric 奖励是逐条 **presence** 给分（"这条内容提到了吗？"）。它 (i) 对回答是否**承诺**于条目内容不敏感（含糊提及也得分）；(ii) 对**错误的具体值**几乎不扣分——隐含承诺阈值 τ ≤ 0，虚张声势没有成本；(iii) 单独补上真实性惩罚（如三态 +1/0/−1）会打开"用含糊逃避惩罚"的逃生通道（Reward Bias Substitution）。
- **Non-goals**：不做新的 rubric 生成方法；不用整体（holistic）judge 取代 rubric；不追求"判断力/堆砌"通道的理论证明；不处理 deep-research 引用任务；不改 RL 优化器本身（只改奖励）。
- **Constraints**：GPU 实验按需规划（用户要求忽略 GPU 限制）；训练 judge 必须是可本地部署的开源模型（成本与可复现）；人类金标准有限（HealthBench meta-eval 医师标注）；HealthBench（MIT）为主数据，至少一个非医疗 rubric 数据集做迁移。
- **Success condition**：在 GRPO 下，相对 presence 奖励，stance 奖励 (1) 降低错误具体值的比例，(2) 不增加含糊/逃避，而只加真实性惩罚的对照臂会增加含糊；(3) 在 held-out、由跨模型族 judge 评分、经医师标注校准的共识指标上非劣（≥ presence − 0.01）。

## Anchor Check
- Round-1 评审：无漂移。两条范围说明均已采纳：(a) 不用 rubric-free 找错器去补"rubric 之外的错误"（那是第二个机制）——作为局限报告；(b) std 归一化 GRPO 为主设定，mean-only 为配对消融（配置选择，不是改优化器）。

## Simplicity Check
- 采纳简化 1：**按条目类型分工**（内容条目用 stance，行为条目与负向条目用 presence）→ 去掉了"h→0.5 回退"这一补丁。
- 采纳简化 2：**单一标签空间**——内容条目的分数只由 COMMIT 标签决定（presence 是 h=1, c=0 的特例），去掉 v2 中 "met + not_addressed → +w" 之类的交叉表规则；presence 判定只用于行为条目与负向条目。
- 采纳简化 3：把"诊断 + BoN-4 协议"从贡献中删除，并入评测。
- 拒绝：任何新增模块（整体守卫、rubric-free 找错通道、演化 rubric）。

## Changes Made（逐条回应 Round-1 评审）
| 评审意见 | 处理 | 理由 |
|---|---|---|
| CRITICAL 不确定性漏洞（v2 把"诚实的不确定"算 committed） | 改为按条目类型判定：内容条目（axis:accuracy/completeness，78%）上"在备选之间的不确定"= evasive；条件式建议仅当给出"条件→行动"才 committed；行为条目由医师自己的 presence 条目定价不确定性 | 关闭新形式的逃生通道而不误伤合理的不确定性；新增 uncwrap 探针检验（Pilot 9 G3） |
| CRITICAL −3w 乘在最噪的标签上 | contradicted 必须给出原文引文并字符串匹配；被标条目复问一次、两次一致才计；RL 前置闸门：重现率 ≥ 0.60、理想回答触发率 ≤ plain（Pilot 9 G1/G2）；若不过，c→−1 或换更强训练 judge | 让 −3w 建立在可靠标签上 |
| CRITICAL 需要决策论主干 | 加入 τ(h,c) = (h−c)/(1−c) 命题与实测有效 (h,c) | 论文主张变为一句话："只有 h ≤ 0 时真实性惩罚才安全" |
| 闭式规格缺口 | 写出完整奖励公式：不裁剪，除以正向分总和；缺失标签 → 回退该条目的 presence 判定并记录；训练 judge 非思考模式、temperature 0 | 可实现性 |
| 数据划分算错 | 全部 5,000 prompt 按 prompt_id 划分 4,000 训练 / 1,000 held-out；held-out 从 3,671 个有共识条目的 prompt 中抽取（以便用医师校准的共识条目评测）；奖励无可训练参数，无需排除 meta-eval prompt | 评审核实：oss_eval 5,000 中 3,671 有 cluster 级共识条目 |
| 验证部分循环 | 新增与标签定义无关的含糊指标：每条建议的备选数 + hedge 词典命中率；人工抽检对准 B vs C 的 evasive 样本；错误拆为 rubric 覆盖 / rubric 之外 | 防止"定义层面的 hack"逃过评测 |
| 迁移集与非目标冲突 | ResearchRubrics → **RaR-Science-20k**（`anisha2102/RaR-Science-20k-o3-mini`，已在 HF 核实存在 train/val/test） | 非检索型 rubric-RL 数据 |
| 算力估计偏乐观 | 上调为 ~100 H100-h/run | 1M 次 judge 调用 × ~1.5k token |

## Revised Proposal

# Research Proposal: Pricing Commitment Makes Truth Penalties Safe — Stance Credit for Rubric RL

## Technical Gap
- 逐条 presence 给分把每个条目变成"提到即得分"。把它看作一个单条目决策问题：回答者对条目内容有置信度 p，可以 **承诺**（对则 +1，错则 c）、**含糊**（给一个包含正确答案的选项菜单，得 h）或 **省略**（0）。承诺优于含糊当且仅当 **p ≥ τ(h,c) = (h−c)/(1−c)**。
  - presence（h=1, c=0）：τ = 1——任何不确定下含糊都弱占优；相对省略，承诺（哪怕是错的）永远不亏 → **虚张声势免费**。
  - 三态真实性惩罚 ConRub-Med（h=1, c=−1）以及 h=1, c=−3：τ = 1——惩罚错误但含糊仍弱占优 → **逃生通道**。
  - **stance credit（h=0, c=−3）：τ = 0.75**——只在足够有把握时承诺，否则省略或交给医师自己写的"承认不确定/索取信息"行为条目定价。
- 现有修复都是单轴的（聚合：ProRubric/GEAR/Dropout；生成：RubricArmor；真实性门控：ConRub-Med、MetaRubric、CaRR），且都没有 hedged 状态；Kalai et al.（2509.04664）的阈值打分只针对短答 IDK，把 hedging 留作未来工作。
- 实证（API-only pilot；v1 判定，**v3 数字待 Pilot 9 填入**）：presence 对含糊改写与 ×3/÷3 错数值的标准化效应只有 −0.27 / −0.30 SD（≈ 同文本重判噪声）；stance 为 −0.54 / −0.81 SD；三态（h=1）下含糊改写 Δ = +0.00；且含糊改写版每条目的 contradicted 标签更少（0.015 vs 0.026）——**静态数据中已能看到逃生通道**。

## Method Thesis
**对内容型 rubric 条目，按回答的立场给分——承诺 +w、含糊 0、未覆盖 0、矛盾 −3w——把隐含承诺阈值从 1 降到 0.75：同时给"承诺"与"真实"定价，关闭虚张声势通道，且不打开含糊逃生通道；行为条目与负向条目保持 presence 不变。**

## Contribution Focus
- **Dominant contribution**：带 hedge 状态的 stance credit + τ(h,c) 命题：在逐条 rubric 奖励这一族中，只有 h ≤ 0 时加入真实性惩罚才不会把优化压力转移到含糊；并在 GRPO 下验证（逃生通道在 h=1 臂出现，在 h=0 臂关闭）。
- **Explicitly rejected complexity**：整体 judge 守卫、induced-action 奖励（pilot 淘汰）、rubric-free 找错通道、演化 rubric、新 rubric 生成、任何可训练新组件。

## Proposed Method

### Complexity Budget
- 冻结/复用：策略、GRPO、HealthBench 医师逐例 rubric、presence judge 提示词。
- 新增：一个 COMMIT 判定阶段（仅内容条目）+ 一个闭式打分函数；0 个可训练组件。

### Reward (closed form)
对回答 y 与 rubric {(criterion_i, w_i, axis_i)}：
```
content(i) := w_i > 0 and axis_i ∈ {accuracy, completeness}
ℓ_i ∈ {committed, evasive, not_addressed, contradicted}  (COMMIT judge, content items only)
m_i ∈ {0,1}                                              (PRESENCE judge, all other items)
g(ℓ) = {committed: 1, evasive: h, not_addressed: 0, contradicted: c};  h = 0, c = −3
R(y) = [ Σ_{content i} w_i·g(ℓ_i) + Σ_{non-content i, w_i>0} w_i·m_i + Σ_{i: w_i<0} w_i·m_i ] / Σ_{i: w_i>0} w_i
```
- 不裁剪（范围约 [−3, 1]；GRPO 组内标准化吸收尺度）。缺失/解析失败的 ℓ_i → 该条目回退为 presence 判定并记日志。
- contradicted 规则：必须附与回答原文匹配的引文（否则降为 not_addressed）；被标条目复问一次，两次一致才计入。
- 判定提示：≤4 条/调用；训练 judge 为开源 Qwen3-32B 级，非思考模式，temperature 0。

### Integration
- 作为 drop-in 奖励替换 RaR/HealthBench 式 presence 奖励；与聚合类修复正交（可叠加，但本文不叠加以保持单一机制）。

### Training Plan
- 策略 Qwen3-8B（预演 Qwen3-4B），GRPO，G=8，~400–600 step，std 归一化（主）/ mean-only（消融）。
- 数据：HealthBench 5,000 prompt 按 prompt_id 划分 4,000 训练 / 1,000 held-out（held-out 取自 3,671 个带共识条目的 prompt）。迁移：RaR-Science-20k。

### Failure Modes and Diagnostics
- 退缩为省略（2608.00301：GRPO 重置有效阈值）→ 监控 not_addressed 比例、长度、共识分；mean-only 消融；实测训练后的有效阈值。
- COMMIT judge 被 hack（承诺式措辞但内容不对/含糊）→ 训练 judge vs 跨族 judge 差值；定义无关的含糊指标；B vs C evasive 样本人工抽检 100 对。
- rubric 之外的编造不被惩罚 → 作为局限报告，错误拆为 rubric 覆盖 / rubric 之外分别统计。

### Novelty and Elegance Argument
- 一个状态（hedged=0）+ 一个阈值命题，就把"真实性惩罚为何会诱发含糊"解释清楚并修好；与 ConRub-Med 的差别恰是该状态，与 Kalai 的差别是逐条 rubric + 含糊动作。可一句话复述："**给真实定价时必须同时给承诺定价。**"

## Claim-Driven Validation Sketch
- **C1（主）**：GRPO 三臂 A presence（h=1,c=0）/ B 真实性-only（h=1,c=−3；另 h=1,c=−1）/ C stance（h=0,c=−3）。预期：A 的 rubric 覆盖错误随训练↑；B 的含糊↑（定义无关指标 + 跨族 judge 的 evasive）且错误↓；C 两者都↓。
- **C2（辅）**：C 在 held-out 共识指标（跨族 judge 评分，经 meta-eval 医师标注校准）上非劣于 A（margin 0.01），并在医师 BoN-4（API）上非劣。
- 前置闸门：Pilot 8（B1/B2）与 Pilot 9（G1–G4）。

## Compute & Timeline
- ~100 H100-h/run；主实验 3 臂 × 2 seeds + 消融（mean-only、h=0.5、c=−1）≈ 10 runs ≈ 1,000 H100-h；4B 预演 ≈ 150 H100-h。
- 时间：Pilot 8/9（API，1 天）→ 4B 预演（3 天）→ 8B 主实验（1–1.5 周）→ 跨族评测 + 人工抽检（4 天）。
