# 代码分析文档索引

> `research/analysis/` 目录存放对特定代码模块、API 接口、或技术问题的深度分析文档。
>
> 命名规范：`YYYY-MM-{topic}.md`
> 创建新文档时，请在下方表格中登记。

---

## 现有文档

| 日期 | 文档 | 分析范围 | 状态 |
|------|------|---------|------|
| 2026-06-01 | [everos-cloud-api-audit.md](everos-cloud-api-audit.md) | `providers/memory/evermemos/evermemos_client.py` 云端 API 模式 | active |
| 2026-06-02 | [2026-06-api-access-methods.md](2026-06-api-access-methods.md) | 后端对话接入方式（REST + WebSocket + 内置客户端） | active |
| 2026-06-04 | [2026-06-genome-signal-llm-pipeline.md](2026-06-genome-signal-llm-pipeline.md) | Genome 引擎信号如何通过 system prompt 影响 LLM 输出 | active |
| 2026-06-05 | [2026-06-voice-conversation-feasibility.md](2026-06-voice-conversation-feasibility.md) | 流式语音对话可行性分析与延迟优化方案 | active |
| 2026-06-05 | [lifecycle-overview.md](lifecycle-overview.md) | 单轮对话 12 步生命周期总览 | active |
| 2026-06-05 | [lifecycle-step-00-evermemos.md](lifecycle-step-00-evermemos.md) | Step 0: EverMemOS 会话上下文 | active |
| 2026-06-05 | [lifecycle-step-01-metabolism.md](lifecycle-step-01-metabolism.md) | Step 1: 时间代谢 | active |
| 2026-06-05 | [lifecycle-step-02-critic.md](lifecycle-step-02-critic.md) | Step 2: Critic 感知 | active |
| 2026-06-05 | [lifecycle-step-02p5-relationship.md](lifecycle-step-02p5-relationship.md) | Step 2.5: 关系 EMA | active |
| 2026-06-05 | [lifecycle-step-03-reward.md](lifecycle-step-03-reward.md) | Step 3: 奖励计算 | active |
| 2026-06-05 | [lifecycle-step-03p5-baseline.md](lifecycle-step-03p5-baseline.md) | Step 3.5: 驱动基线演化 | active |
| 2026-06-05 | [lifecycle-step-04-crystal.md](lifecycle-step-04-crystal.md) | Step 4: 结晶门 | active |
| 2026-06-05 | [lifecycle-step-05-signals.md](lifecycle-step-05-signals.md) | Step 5: 信号计算 | active |
| 2026-06-05 | [lifecycle-step-06-noise.md](lifecycle-step-06-noise.md) | Step 6: 热力学噪声 | active |
| 2026-06-05 | [lifecycle-step-07-knn.md](lifecycle-step-07-knn.md) | Step 7: KNN 风格检索 | active |
| 2026-06-05 | [lifecycle-step-08-prompt.md](lifecycle-step-08-prompt.md) | Step 8/8.5: Prompt 构建 | active |
| 2026-06-05 | [lifecycle-step-09-actor.md](lifecycle-step-09-actor.md) | Step 9: Actor 生成 | active |
| 2026-06-05 | [lifecycle-step-10-hebbian.md](lifecycle-step-10-hebbian.md) | Step 10: Hebbian 学习 | active |
| 2026-06-05 | [lifecycle-step-11-12-async.md](lifecycle-step-11-12-async.md) | Step 11-12: 异步记忆 | active |
| 2026-06-05 | [lifecycle-summary.md](lifecycle-summary.md) | 完整串联汇总 | active |
| 2026-06-06 | [LLM_and_Cognitive_Architecture_Complete_Discussion.md](LLM_and_Cognitive_Architecture_Complete_Discussion.md) | LLM 局限性与认知架构维度（记忆、状态、主体性） | active |
| 2026-06-06 | [2026-06-aibeing-cognitive-architecture-gap-analysis.md](2026-06-aibeing-cognitive-architecture-gap-analysis.md) | 对照理论框架的全项目技术差距审计（16 项差距 + 4 阶段路线图） | active |

---

## 文档模板

创建新分析文档时，建议在文件头包含以下信息：

```markdown
---
date: 2026-06-15
topic: 分析主题
scope: 涉及的文件/模块
status: active | superseded | archived
related: 关联的其他文档（如 ARCHITECTURE.md）
---

> 一句话总结本次分析的结论。

## 背景

为什么做这次分析？

## 分析对象

具体代码位置、接口、或问题描述。

## 发现

1. 问题 A
2. 问题 B

## 建议

1. 修复方案
2. 优先级

## 验证

如何验证修复是否生效？
```

---

## 待分析清单（由 ROADMAP/ARCHITECTURE 驱动）

- [ ] WebSocket 协议完整规范
- [ ] 12 步生命周期性能瓶颈分析
- [ ] Critic prompt 质量评估
- [ ] StyleMemory KNN 检索准确性
- [ ] Hebbian 学习效果量化
