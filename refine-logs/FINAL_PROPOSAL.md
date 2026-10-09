# Research Proposal: Pricing Commitment Makes Truth Penalties Safe — Stance Credit for Rubric RL

## Problem Anchor（逐字复用 Round 0）

- **Bottom-line problem**：用逐条 rubric 作为奖励的 RL（Rubric RL）会把开放式回答（以医疗问答为代表）优化成"rubric 分高、但按专家标准更差"的回答——泛泛而谈（含糊、不承诺）、只在罗列断言、具体事实错误。
- **Must-solve bottleneck**：主流 rubric 奖励是逐条 **presence** 给分（"这条内容提到了吗？"）。它 (i) 对回答是否**承诺**于条目内容不敏感（含糊提及也得分）；(ii) 对**错误的具体值**几乎不扣分——隐含承诺阈值 τ ≤ 0，虚张声势没有成本；(iii) 单独补上真实性惩罚（如三态 +1/0/−1）会打开"用含糊逃避惩罚"的逃生通道（Reward Bias Substitution）。
- **Non-goals**：不做新的 rubric 生成方法；不用整体（holistic）judge 取代 rubric；不追求"判断力/堆砌"通道的理论证明；不处理 deep-research 引用任务；不改 RL 优化器本身（只改奖励）。
- **Constraints**：GPU 实验按需规划（用户要求忽略 GPU 限制）；训练 judge 必须是可本地部署的开源模型（成本与可复现）；人类金标准有限（HealthBench meta-eval 医师标注）；HealthBench（MIT）为主数据，至少一个非医疗 rubric 数据集做迁移。
- **Success condition**：在 GRPO 下，相对 presence 奖励，stance 奖励 (1) 降低错误具体值的比例，(2) 不增加含糊/逃避，而只加真实性惩罚的对照臂会增加含糊；(3) 在 held-out、由跨模型族 judge 评分、经医师标注校准的共识指标上非劣（≥ presence − 0.01）。


## Technical Gap
- 逐条 presence 给分把每个条目变成"提到即得分"。把它看作一个单条目决策问题：回答者对条目内容有置信度 p，可以 **承诺**（对则 +1，错则 c）、**含糊**（给一个包含正确答案的选项菜单，得 h）或 **省略**（0）。承诺优于含糊当且仅当 **p ≥ τ(h,c) = (h−c)/(1−c)**。
  - presence（h=1, c=0）：τ = 1——任何不确定下含糊都弱占优；相对省略，承诺（哪怕是错的）永远不亏 → **虚张声势免费**。
  - 三态真实性惩罚 ConRub-Med（h=1, c=−1）以及 h=1, c=−3：τ = 1——惩罚错误但含糊仍弱占优 → **逃生通道**。
  - （注：Problem Anchor 中的"τ ≤ 0"指 pilot 中测得的**回答级经验阈值**——presence 下承诺错误值几乎不比承诺正确值少分、且优于含糊；条目级理论值见本节：presence 相对含糊 τ=1，相对省略则承诺永远不亏。两者描述同一现象的两个侧面：presence 同时奖励虚张声势与含糊，只是不惩罚前者。）
  - **stance credit（h=0, c=−3）：τ = 0.75**——只在足够有把握时承诺，否则省略或交给医师自己写的"承认不确定/索取信息"行为条目定价。
  - **考虑 judge 能力的有效阈值**：设 judge 对错误值的召回为 q、对正确内容误标矛盾的概率为 f、含糊菜单的实际得分为 h_eff，则 **τ_eff = (h_eff − 1 + q(1−c)) / ((q − f)(1 − c))**（完美 judge 时退化为 τ(h,c)）。h=0 时只有 q > 1/(1−c) 错误才有成本 → 惩罚强度必须按 judge 标定：**c\* = 使 τ_eff ≈ 0.75 的 c**（由条目对齐探针测得，Pilot 10）。任何 h<1 都会恢复一个有限阈值；h=0 使阈值最低，并使最不稳定的 evasive/not_addressed 边界不影响奖励（稳健性上的额外好处）。
- 现有修复都是单轴的（聚合：ProRubric/GEAR/Dropout；生成：RubricArmor；真实性门控：ConRub-Med、MetaRubric、CaRR），且都没有 hedged 状态；Kalai et al.（2509.04664）的阈值打分只针对短答 IDK，把 hedging 留作未来工作。
- 实证（API-only，HealthBench，v3 判定 = 本方法的判定器；Pilot 9）：相对普通回答，presence 对含糊改写 / "大概 X 也可能 Y"式改写 / ×3÷3 错数值 / ×1.5÷1.5 错数值只降 −0.048 / −0.110 / −0.066 / −0.064；stance（h=0,c=−3）为 −0.160 / −0.211 / −0.255 / −0.173；错数值扣分率 0.67 / 0.63（同文本误罚底 0.40；presence 0.46 / 0.50，底 0.33）。**逃生通道的静态证据**："含糊的错误 − 承诺的错误"在 presence 下为 −0.049（虚张声势更划算），在只加真实性惩罚（h=1,c=−3）下为 **+0.127**（含糊成为避难所），在 stance（h=0,c=−3）下为 −0.016（都不被奖励）。经验 τ 在 v3 规则族内的排序与 τ(h,c) 一致。
- 判定器可靠性：contradicted 同文本重现率 0.80（引文 + 复问后，n=20，Wilson CI [0.58, 0.92]）；Sonnet 作判定器时对注入错误的配对敏感度 0.44 vs 0.00。原 G2（理想回答触发率 ≤ plain）未过（Haiku 0.16 vs 0.12；Sonnet 0.15 vs 0.09），但被 R2 评审判为设计错误（功效不足、锚在过时理想回答上、测频率而非精确率），以人工裁决精确率闸门 G2' 取代（Pilot 10）；"按预登记降到 c=−1"的补救被撤回（会丢掉真实性定价），偏离已公开记录。

## Method Thesis
**对内容型 rubric 条目，按回答的立场给分——承诺 +w、含糊 0、未覆盖 0、矛盾 c\*·w（c\* 按 judge 的召回/误报标定，使有效承诺阈值 ≈ 0.75）——同时给"承诺"与"真实"定价：关闭虚张声势通道，且不打开含糊逃生通道；行为条目与负向条目保持 presence 不变。**

## Contribution Focus
- **Dominant contribution**：带 hedge 状态的 stance credit + 阈值命题（τ(h,c) 及其按 judge 能力修正的 τ_eff）：在逐条 rubric 奖励这一族中，h=1 时任何真实性惩罚都只会把优化压力推向含糊；必须同时给承诺定价（h<1，h=0 最稳健），并按 judge 召回标定惩罚强度；在 GRPO 下验证（逃生通道在 h=1 臂出现，在 h=0 臂关闭）。
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
g(ℓ) = {committed: 1, evasive: h, not_addressed: 0, contradicted: c};  h = 0, c = c* (主臂；由 Pilot 10 的 q、f、h_eff 标定), c = −1 (消融)
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
- **C1（主）**：GRPO 三臂 A presence（h=1,c=0）/ B 真实性-only（h=1,c=c\*）/ C stance（h=0,c=c\*）；消融：h=0,c=−1；h=0.5,c=c\*；h=1,c=−1（ConRub 式）；C + mean-only 归一化。预期：A 的 rubric 覆盖错误随训练↑；B 的含糊↑（定义无关指标 + 跨族 judge 的 evasive）且错误↓；C 两者都↓。
- **C2（辅）**：C 在 held-out 共识指标（跨族 judge 评分，经 meta-eval 医师标注校准）上非劣于 A（margin 0.01），并在医师 BoN-4（API）上非劣。
- 前置闸门：Pilot 9 G1/G3/G4 已通过；G1'（扩大）/ G2'（精确率）与 c\* 见 Pilot 10；医师 BoN-4 非劣（B1/B2 再登记为 Pilot 9c）；训练 judge（开源 32B）上复现全部闸门（M1）。
- **预登记的"行为条目样板"指标**（R2 评审：C 臂可能把压力转向附加"不确定/建议就医/请提供更多信息"之类的通用样板以拿行为条目分）：行为条目得分占比、通用不确定/索取信息样板句的比例（词典 + 跨族 judge）；并在 M2 检查 A 臂的 rubric 覆盖错误率是否随训练上升（前提检验）。

## Compute & Timeline
- ~100 H100-h/run；主实验 3 臂 × 2 seeds + 消融（mean-only、h=0.5、c=−1）≈ 10 runs ≈ 1,000 H100-h；4B 预演 ≈ 150 H100-h。
- 时间：Pilot 8/9（API，1 天）→ 4B 预演（3 天）→ 8B 主实验（1–1.5 周）→ 跨族评测 + 人工抽检（4 天）。
