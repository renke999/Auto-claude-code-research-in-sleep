# Research Proposal (Round 0): Safe Truth Penalties for Rubric RL — Stance Credit with a Hedge State

## Problem Anchor（冻结；后续每轮逐字复用）

- **Bottom-line problem**：用逐条 rubric 作为奖励的 RL（Rubric RL）会把开放式回答（以医疗问答为代表）优化成"rubric 分高、但按专家标准更差"的回答——泛泛而谈（含糊、不承诺）、只在罗列断言、具体事实错误。
- **Must-solve bottleneck**：主流 rubric 奖励是逐条 **presence** 给分（"这条内容提到了吗？"）。它 (i) 对回答是否**承诺**于条目内容不敏感（含糊提及也得分）；(ii) 对**错误的具体值**几乎不扣分——隐含承诺阈值 τ ≤ 0，虚张声势没有成本；(iii) 单独补上真实性惩罚（如三态 +1/0/−1）会打开"用含糊逃避惩罚"的逃生通道（Reward Bias Substitution）。
- **Non-goals**：不做新的 rubric 生成方法；不用整体（holistic）judge 取代 rubric；不追求"判断力/堆砌"通道的理论证明；不处理 deep-research 引用任务；不改 RL 优化器本身（只改奖励）。
- **Constraints**：GPU 实验按需规划（用户要求忽略 GPU 限制）；训练 judge 必须是可本地部署的开源模型（成本与可复现）；人类金标准有限（HealthBench meta-eval 医师标注）；HealthBench（MIT）为主数据，至少一个非医疗 rubric 数据集做迁移。
- **Success condition**：在 GRPO 下，相对 presence 奖励，stance 奖励 (1) 降低错误具体值的比例，(2) 不增加含糊/逃避，而只加真实性惩罚的对照臂会增加含糊；(3) 在 held-out、由跨模型族 judge 评分、经医师标注校准的共识指标上非劣（≥ presence − 0.01）。

## Technical Gap

- 现有修复都是**单轴**的：聚合侧（ProRubric 2609.38847、GEAR 2606.03361、Rubric Dropout 2608.11669）、rubric 生成侧（RubricArmor 2610.05308）、真实性门控（ConRub-Med 2608.10996 三态、CaRR 2601.06021、MetaRubric 2610.02824）。ConRub-Med 与 MetaRubric 都**没有 hedged 状态**：含糊提及在它们那里仍算覆盖。
- Kalai et al.（2509.04664）给出 t/(1−t) 阈值打分，但只针对短答与 IDK，明确把 hedging 留作未来工作；2608.00301 指出 GRPO 组归一化会重置有效阈值。
- 我们的 pilot（HealthBench，API-only）：presence 对"含糊改写"只降 −0.27 SD、对 ×3/÷3 数值错误只降 −0.30 SD（≈ 同文本重判噪声）；stance 给分分别为 −0.54 SD 与 −0.81 SD；三态（hedged 算覆盖）下含糊改写 Δ = +0.00 → 逃生通道在静态数据中已可见。

## Method Thesis

**在不改变 presence 判定的前提下，对每个正向 rubric 条目按回答的"立场"给分——承诺 +w、逃避式提及 h·w（h≈0）、未覆盖 0、矛盾 −3w：同时给"承诺"与"真实"定价，关闭虚张声势通道，又不打开含糊逃生通道。**

## Contribution Focus

- **Dominant contribution**：一个"安全的真实性惩罚"——带 hedge 状态的 stance credit；以及它为什么必要的证据（只加真实性惩罚 → 含糊逃生；只看 presence → 虚张声势）。
- **Supporting contribution**：一个可复用的静态"奖励敏感度"诊断 + 医师 BoN-4 人类锚定评测协议（训练前即可量化某个 rubric 奖励对含糊/错误的敏感度）。
- **Explicitly rejected complexity**：整体 judge 守卫、induced-action 奖励（pilot 已淘汰）、"判断力/堆砌"第三通道、新 rubric 生成、演化 rubric、额外可训练模块。

## Proposed Method

### Complexity Budget
- 冻结/复用：策略模型、GRPO、rubric（HealthBench 医师逐例 rubric）、presence judge 提示词。
- 新增：**一个**judge 调用阶段（COMMIT，仅针对正向条目）与**一个**打分函数。0 个新可训练组件。

### System Overview
```
prompt → policy rollout y
  ├─ Stage 1  PRESENCE judge (all items, ≤4 items/call)        → met_i ∈ {0,1}
  ├─ Stage 2  COMMIT judge (positive items only, ≤4 items/call) → ℓ_i ∈ {committed, evasive, not_addressed, contradicted}
  └─ reward R(y) = [ Σ_{i:w_i>0} w_i·g(met_i, ℓ_i) + Σ_{i:w_i<0} w_i·met_i ] / Σ_{i:w_i>0} w_i
       g = c (=−3) if ℓ=contradicted;  h (=0) if met ∧ ℓ=evasive;  1 if met;  0 otherwise
```

### Core Mechanism
- **COMMIT 定义**（修正版）：committed = 以用户可执行的形式告诉其"该做什么/是什么"，**条件式建议、诚实的不确定性表达、向用户索取缺失信息都算 committed**；evasive = 内容只出现在一个没有说明哪项适用的选项菜单里，或泛到无法据此行动；contradicted = 陈述/推荐与条目事实上不相容的内容（剂量、阈值、时机、药物、相反建议）。
- **为什么 h≈0、c=−3**：h=0 让"逃避式提及"与沉默等价（关闭含糊通道）；c=−3 对应承诺阈值 0.75（Kalai t/(1−t)）；两者缺一不可（静态消融已显示各自负责一个通道）。
- **GRPO 交互**：std 归一化下单个被重罚样本的优势被 Samuelson 界限制在 −√(G−1)，惩罚强度 c 的边际作用饱和（2608.00301 亦指出阈值重置）。→ 主实验用 std 归一化（默认），并加一个 mean-only（Dr. GRPO 式）消融，实测训练后策略的有效阈值。

### Optional Supporting Component
- 无（rubric 之外的错误不在本方法范围内；作为已知局限与未来工作：rubric-free 找错框架在 pilot 中检出率 0.82–0.90，但会引入第二个机制）。

### Modern Primitive Usage
- LLM-as-judge（开源 Qwen3-32B 级，vLLM 部署）作为两阶段逐条判定器；GRPO 作为优化器。没有为了"新潮"而加的组件。

### Integration
- 作为 drop-in 奖励函数替换 RaR/HealthBench 式 presence 奖励；与 ProRubric/GEAR/Dropout 等聚合修复正交，可叠加。

### Training Plan
- 策略：Qwen3-8B（消融用 Qwen3-4B），GRPO，G=8，~400–600 step，KL 小。
- 数据：HealthBench 按 prompt_id 划分：~3.0k 训练 / ~1.0k held-out；**meta-eval 的 3,671 个 prompt 全部排除在训练之外**（留作医师锚定评测）。
- 训练 judge：开源 Qwen3-32B 级（两阶段提示，chunk≤4）；评测 judge：**不同模型族**（如 GPT/Gemini 系）+ 医师 meta-eval 校准。

### Failure Modes and Diagnostics
- 退缩为沉默/遗漏（2608.00301）→ 监控 not_addressed 比例、长度、共识分；必要时 h→0.5 或降低 |c|。
- judge 被 hack（策略学会"承诺式措辞"骗过 COMMIT judge）→ 训练 judge vs 跨族 judge 的差值；人工抽检 100 对。
- hedge 状态误伤合理的不确定性 → 分 hedging/context-seeking 子群报告（P8 预登记 B2）。

### Novelty and Elegance Argument
- 与 ConRub-Med 的区别是一个状态（hedged），但正是这个状态决定了真实性惩罚是否安全；与 Kalai 的区别是逐条应用于开放式 rubric 并处理"含糊"这一第三动作。一句话可复述：**"给真实定价时必须同时给承诺定价。"**

## Claim-Driven Validation Sketch

### Claim 1（主）：只加真实性惩罚会把压力转移到含糊；stance credit 同时关闭两个通道
- 实验：GRPO 三臂 A presence / B 真实性-only（ConRub 式 h=1, c=−1；以及 h=1, c=−3）/ C stance（h=0, c=−3），2–3 seeds。
- 指标：跨族 judge 下 held-out 的 evasive 比例、contradicted 比例、rubric-free 每条声明错误数、长度、断言密度、共识分。
- 预期：B 的 evasive↑ 而 contradicted↓；C 两者都↓；A 的 contradicted/错误数随训练↑。

### Claim 2（辅）：stance credit 与医师判断非劣
- 实验：医师 BoN-4（API，P8，1000 池）+ RL 后在医师校准的共识指标上的非劣检验（margin 0.01）。

## Experiment Handoff Inputs
- 必跑：P8（API 预登记，进行中）；三臂 GRPO；h/c/归一化消融；跨族评测。
- 关键数据：HealthBench oss_eval、meta-eval（医师标注）；迁移：ResearchRubrics（含负向条目）。

## Compute & Timeline Estimate
- 每个 8B GRPO run：~400 step × 64 prompt × 8 rollout ≈ 2×10^5 rollouts；judge ≈ 5 次调用/rollout ≈ 1M 次 32B 推理 → 约 40 H100-h/run（策略 + judge）。
- 主实验 3 臂 × 2 seeds + 消融 4 runs ≈ 10 runs ≈ 400 H100-h；4B 预演 ≈ 60 H100-h。
- 时间：P8（1 天，API）→ 4B 预演（2–3 天）→ 8B 主实验（1 周）→ 跨族评测与分析（3–4 天）。
