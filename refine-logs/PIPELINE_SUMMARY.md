# Pipeline Summary

**Problem**: Rubric RL 奖励如何对齐人类（医师）理想标准，并减少泛泛而谈 / 罗列断言 / 真实性差等 hack
**Final Method Thesis**: 对内容型 rubric 条目按立场给分（承诺 +w / 含糊 0 / 未覆盖 0 / 矛盾 c*·w，c* 按 judge 召回/误报标定），使含糊永不最优、低置信时省略、仅在 p ≥ ~0.75 时承诺——给真实定价时同时给承诺定价
**Final Verdict**: REVISE（7.4/10，同族 reviewer；剩余阻塞项为预登记的训练 judge 复现与 RL）
**Date**: 2026-10-09

## Final Deliverables
- Proposal: `refine-logs/FINAL_PROPOSAL.md`
- Review summary: `refine-logs/REVIEW_SUMMARY.md`
- Experiment plan: `refine-logs/EXPERIMENT_PLAN.md`
- Experiment tracker: `refine-logs/EXPERIMENT_TRACKER.md`

## Contribution Snapshot
- Dominant contribution: 带 hedge 状态的 stance credit + 阈值命题（τ(h,c)、τ_eff）——只加真实性惩罚会扩大含糊区域（条目级实测：p<0.62 → p<0.80），h=0 使含糊永不最优
- Optional supporting contribution: 无（诊断协议并入评测）
- Explicitly rejected complexity: 整体 judge 守卫、induced-action 奖励、rubric-free 找错通道、演化 rubric、新 rubric 生成、可训练新组件

## Must-Prove Claims
- C1：GRPO 下只加真实性惩罚（h=1, c*）提高含糊；stance（h=0, c*）同时降低错误与含糊
- C2：stance 与医师判断非劣（医师 BoN-4；RL 后共识指标 ≥ presence − 0.01）

## First Runs to Launch
1. M1：开源训练 judge（Qwen3-32B 级）上重跑 Pilot 9/10 闸门 + 收紧 grounding + 重标 c*
2. M2：4B GRPO 预演 A presence / B h=1,c* / C h=0,c*（1 seed，200 step），先检验 presence 臂是否出现含糊/编造
3. M3：8B 三臂 × 2 seeds

## Main Risks
- RL 下退缩为省略（2608.00301）：监控 not_addressed / 长度 / 共识分；mean-only 消融
- COMMIT judge 被承诺式措辞欺骗：跨族 judge + 定义无关含糊指标 + 人工抽检
- 自然回答上的矛盾 flag 精确率偏低（0.46）：更强训练 judge + 更严格 grounding（M1 闸门）
- 所有 pilot 证据来自 Claude 系 judge：M1 开源 judge 复现；评测用非 Claude judge

## Next Action
- Proceed to `/run-experiment`（M1）
