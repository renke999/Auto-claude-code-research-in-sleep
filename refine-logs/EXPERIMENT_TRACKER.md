# Experiment Tracker

| Run ID | Milestone | Purpose | System / Variant | Split | Metrics | Priority | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| P8-A | M0 | 静态闸门（v2 two-stage） | presence vs v2，13 变体 | HB oss_eval 100 prompt | 配对 Δ、重判误罚率、evasive 份额 | MUST | RUNNING | 预登记 A1–A3 |
| P8-B | M0 | 医师 BoN-4 非劣（v2） | presence vs v2，h×c 网格 | meta-eval 1,000 池（seed 5） | pick gold、P(best)、一致性；hedging 子群 | MUST | RUNNING | 预登记 B1、B2 |
| P9 | M0 | v3 闸门（内容条目、引文 + 复问） | presence vs v3，含 uncwrap / uncwrap_wrong / numsub | HB oss_eval 100 prompt + 20 重判 | G1 重现率、G2 触发率、G3 漏洞、G4 真实性、经验 τ | MUST | RUNNING | 预登记 G1–G4 |
| R0 | M1 | 训练 judge 复现闸门 | v3 on Qwen3-32B（vLLM） | 同 P9 | G1–G4 | MUST | TODO | 训练 judge ≠ Haiku |
| R1 | M2 | 4B 预演 | A presence / B h1c−3 / C h0c−3 | HB 4k/1k | 含糊、错误、共识分、长度 | MUST | TODO | 1 seed，200 step |
| R2 | M3 | 8B 主实验 A | presence | HB 4k/1k | 全部 | MUST | TODO | seeds 0,1 |
| R3 | M3 | 8B 主实验 B | h=1, c=−3（+ h=1,c=−1） | HB 4k/1k | 全部 | MUST | TODO | seeds 0,1 |
| R4 | M3 | 8B 主实验 C | h=0, c=−3 | HB 4k/1k | 全部 | MUST | TODO | seeds 0,1 |
| R5 | M4 | 消融 τ=0.875 | h=0.5, c=−3 | HB 4k/1k | 有效阈值 | MUST | TODO | 1 seed |
| R6 | M4 | 消融 归一化 | C + mean-only advantage | HB 4k/1k | 有效阈值、c 边际作用 | MUST | TODO | 1 seed |
| R7 | M4 | 消融 τ=0.5 | h=0, c=−1 | HB 4k/1k | 有效阈值 | NICE | TODO | 1 seed |
| R8 | M5 | 跨族评测 + 人工 | A vs C（+B） | held-out 1k | 共识分、定义无关含糊、错误拆分、人工 100 对 | MUST | TODO | 非 Claude judge |
| R9 | M6 | 迁移 | A/B/C 4B | RaR-Science-20k | rubric 分、GPQA-D、含糊/错误 | NICE | TODO | 1 seed |
