# Review Summary

**Problem**: Rubric RL 的奖励如何更对齐人类（医师）理想标准，并减少 rubric 带来的 hack（泛泛而谈、只在罗列断言、真实性差）
**Initial Approach**: 由 /idea-discovery 产生的 23 个候选中，triage 选出 I1 "stance-proper rubric credit"（按承诺/含糊/缺席/矛盾逐条给分）
**Date**: 2026-10-09
**Rounds**: 2 / 5（method review）+ 1 轮研究评审（research-review）
**Final Score**: 7.4 / 10（同族 reviewer；跨模型 reviewer 不可用）
**Final Verdict**: REVISE（剩余阻塞项均为待跑的预登记实验，见下）

## Problem Anchor
（见 `FINAL_PROPOSAL.md` 顶部，三轮逐字未变）

## Round-by-Round Resolution Log

| Round | Main Reviewer Concerns | What This Round Simplified / Modernized | Solved? | Remaining Risk |
|---|---|---|---|---|
| Research review R1 | stance 提示词缺负向条目极性规则（导致医师 BoN 劣势）；hedge 示例与构造模板同词、把条件式算 hedged；τ / Pareto 论证无统计或逻辑支撑；选择性报告；整体判断一致性差异不显著 | 两阶段判定（presence 不变 + 仅正向条目的 COMMIT）；撤回 Pareto/"可证明"主张；论点锐化为"真实性惩罚需要 hedge 状态" | partial | v2 判定重开了含糊漏洞（P8 A1 FAIL） |
| Method R1（6.3） | v2 把"诚实的不确定"算 committed → 漏洞换形式重开；−3w 乘在最噪标签（重现率 36%）；缺决策论主干；规格缺口；数据划分算错；迁移集与非目标冲突 | τ(h,c) 主干；内容/行为条目分工；单一标签空间；引文 + 复问的矛盾判定；闭式奖励；4k/1k 划分；RaR-Science 迁移 | yes（P9：G1/G3/G4 通过） | G2（理想回答触发率）未过 |
| Method R2（7.4） | c=−1 默认会丢掉真实性定价（h=0 时需 q>1/(1−c)）；G2 设计错误；需以含 judge 召回/误报的 τ_eff 为主干并据此选 c*；9c 尚无结果；文档数字口径 | 撤回 c=−1 默认（改为消融），G2 → 人工裁决精确率闸门 G2'；τ_eff 与 c* 由条目对齐探针测得（P10）；文档更正 | pending（P10、P9c 运行中） | 训练 judge 上复现；RL 本身 |

## Overall Evolution
- 方法更具体：从"四态标签 + 一个分数表"到闭式奖励（单一标签空间、只对内容条目、引文 + 复问、缺失回退规则、不裁剪）。
- 主贡献更聚焦：从"一条规则修三种 hack"收缩为"给真实定价时必须同时给承诺定价"（τ / τ_eff 命题），明确放弃"堆砌/判断力"通道。
- 去掉的复杂度：整体守卫、induced-action（pilot 淘汰）、rubric-free 找错通道、h→0.5 补丁、v2 交叉表规则、诊断协议作为独立贡献。
- 现代化：只引入"引文 grounding + 复问"（commit-first/grounded judging 一线）；可选用开源 judge 的 contradiction logprob 阈值替代复问。
- 漂移：三轮均判定无漂移；R2 提醒"若保留 c=−1 默认会悄悄把论文缩窄为只给承诺定价"，已据此撤回。

## Final Status
- Anchor status: preserved
- Focus status: tight（一个机制 + 一个阈值命题）
- Modernity status: appropriately frontier-aware（LLM judge + GRPO；无强行加的组件）
- Strongest parts: 静态逃生通道证据（含糊错误 − 承诺错误：h=1,c=−3 下 +0.127，h=0,c=−3 下 −0.016，差 +0.143 [0.09, 0.20]）；漏洞关闭（G3）；错误敏感度（G4）；经同文本重判校准。
- Remaining weaknesses: 无 RL 结果；所有判定来自 Claude 系 judge（训练 judge 需开源复现）；医师锚定的 BoN 功效有限；rubric 之外的编造不在范围内；理想回答作为锚点已过时。
