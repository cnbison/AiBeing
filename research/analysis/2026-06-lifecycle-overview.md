---
date: 2026-06-05
topic: 单轮对话生命周期总览 — Genome v10 Hybrid 的 12 步全景图
scope: agent/chat_agent.py, 整个 12-step lifecycle
status: active
related: ../ARCHITECTURE.md, ../guides/persona-creation.md
---

> Genome v10 Hybrid 的单轮对话不是简单的"接收消息 → 调用 LLM → 返回回复"，而是一个包含感知、代谢、计算、学习、记忆的完整认知循环。理解这 12 步的顺序和依赖关系，是理解整个 AiBeing 引擎的核心。

---

## 一、为什么要设计 12 步生命周期？

传统聊天机器人的架构通常是：

```
用户输入 → 系统提示 + 历史 → LLM → 回复
```

这个模型的缺陷在于：**LLM 是唯一的智能来源**。角色的所有行为都取决于 prompt 工程和 LLM 的内建知识，没有独立的"心理状态"、没有"学习"、没有"记忆"的累积效应。每轮对话都是孤立的。

Genome v10 的设计哲学是：**LLM 只是角色表达的工具，真正的"人格"存在于引擎内部** —— 一个由驱动（drives）、神经网络权重、情感状态、记忆构成的动态系统。每轮对话不仅产生回复，还会**改变角色的内部状态**，这些状态会影响下一轮的行为。

12 步生命周期就是这种哲学的工程实现。

---

## 二、12 步生命周期的全景图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         单轮对话生命周期 (Genome v10 Hybrid)                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Step -1   [前置] Task Skill ReAct Loop                                    │
│            用户请求的任务型技能（天气、搜索）在人格引擎之前执行                  │
│                                                                             │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                                             │
│  Step 0    [感知层] EverMemOS Session Context                              │
│            首次对话：异步加载用户画像、历史叙事、前瞻                            │
│            后续对话：复用已加载的 session context                              │
│                                                                             │
│  Step 1    [代谢层] Time Metabolism                                        │
│            物理时间流逝对驱动挫败感的影响：冷却 + 饥饿                          │
│                                                                             │
│  Step 2    [感知层] Critic Perception                                      │
│            LLM 分析用户输入 → 8D 上下文 + 5D 挫败变化 + 3D 关系变化            │
│                                                                             │
│  Step 2.5  [涌现层] Relationship EMA                                       │
│            将 LLM 判断的关系变化与前一轮的先验融合，形成后验                      │
│                                                                             │
│  Step 3    [代谢层] LLM Metabolism → Reward                                │
│            将 Critic 的挫败变化量转化为奖励信号                                │
│                                                                             │
│  Step 3.5  [演化层] Drive Baseline Evolution                               │
│            根据挫败变化调整驱动基线（长期性格漂移）                             │
│                                                                             │
│  Step 4    [记忆层] Crystallization Gate                                   │
│            判断上一轮是否值得结晶为长期风格记忆                                │
│                                                                             │
│  Step 5    [计算层] Compute Signals                                        │
│            随机神经网络：context + drives + recurrent → 8D behavioral signals  │
│                                                                             │
│  Step 6    [扰动层] Thermodynamic Noise                                    │
│            挫败感越高 → 温度越高 → 行为越不可预测                              │
│                                                                             │
│  Step 7    [记忆层] KNN Style Retrieval                                    │
│            在风格记忆中检索最相似情境下的历史反应                               │
│                                                                             │
│  Step 8    [表达层] Build Actor Prompt                                     │
│            组装单轮提示：身份 + 信号注入 + few-shot 示例                        │
│                                                                             │
│  Step 8.5  [记忆层] Profile/Episode Memory Injection                        │
│            将用户画像和历史叙事注入 Actor prompt                               │
│                                                                             │
│  Step 9    [表达层] Single-Pass LLM Actor                                  │
│            LLM 生成：内心独白 + 最终回复 + 表达方式                            │
│                                                                             │
│  Step 10   [学习层] Hebbian Learning                                       │
│            根据奖励信号强化/削弱神经网络连接权重                               │
│                                                                             │
│  Step 11   [存储层] EverMemOS Store Turn                                   │
│            异步存储本轮对话到长期记忆（非阻塞）                                 │
│                                                                             │
│  Step 12   [检索层] EverMemOS Search                                       │
│            异步搜索与本轮相关的记忆，供下一轮注入                                │
│                                                                             │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                                             │
│  [后置]    Modality Skill Execution                                        │
│            根据 Actor 选择的表达方式执行技能（语音、照片、静默）                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 三、三层架构视角

从架构分层看，12 步可以归为三个层次：

### 感知层（Perception）— 理解用户

| 步骤 | 功能 | 输出 |
|---|---|---|
| Step 0 | 加载长期记忆上下文 | user_profile, episode_summary, foresight |
| Step 1 | 时间代谢 | 更新后的 frustration 状态 |
| Step 2 | Critic 感知 | 8D context + 5D frustration_delta + 3D relationship_delta + 5D drive_satisfaction |
| Step 2.5 | 关系 EMA | 4D relationship state (depth, trust, valence, foresight) |

**作用**：把用户的原始文本输入转换成机器可处理的数值向量，让引擎"理解"当前对话情境。

### 计算层（Computation）— 决定如何回应

| 步骤 | 功能 | 输出 |
|---|---|---|
| Step 3 | 奖励计算 | reward (float) |
| Step 3.5 | 基线演化 | 更新后的 drive_baseline |
| Step 4 | 结晶判断 | 是否将上轮记忆存入 style_memory |
| Step 5 | 信号计算 | 8D behavioral signals |
| Step 6 | 噪声注入 | noisy_signals |
| Step 7 | 风格检索 | few-shot 示例 |
| Step 8 | Prompt 构建 | single_prompt (system message) |
| Step 8.5 | 记忆注入 | 增强后的 single_prompt |

**作用**：基于感知结果，计算角色当前的行为状态和表达方式。

### 表达层（Expression）— 生成回复

| 步骤 | 功能 | 输出 |
|---|---|---|
| Step 9 | Actor 生成 | monologue + reply + modality |
| Step 10 | Hebbian 学习 | 更新的 W1, W2, b1, b2 权重 |
| Step 11 | 异步存储 | EverMemOS 长期记忆 |
| Step 12 | 异步检索 | 供下轮使用的相关记忆 |

**作用**：让 LLM 根据计算出的状态"表演"角色，同时从本轮交互中学习。

---

## 四、关键数据流

### 4.1 核心数据对象及其流转

```
user_message: str
    ↓
[Step -1] 可能被 task_skill  enriched（加入天气/搜索结果）
    ↓
[Step 0] evermemos_session_ctx: dict
    │   ├── user_profile: str
    │   ├── episode_summary: str
    │   └── foresight: str
    ↓
[Step 1] metabolism.time_metabolism(now)
    │   更新: frustration[5 drives]
    ↓
[Step 2] critic_sense(user_message, llm, frustration, ...)
    │   输出: context(8D), frustration_delta(5D), rel_delta(3D), drive_satisfaction(5D)
    ↓
[Step 2.5] _apply_relationship_ema(relationship_prior, rel_delta, depth)
    │   输出: relationship_4d → merge into context → 12D context
    ↓
[Step 3] metabolism.apply_llm_delta(frustration_delta)
    │   输出: reward (float)
    ↓
[Step 3.5] drive_baseline evolution
    │   更新: agent.drive_baseline[5 drives]
    ↓
[Step 4] _should_crystallize(reward, context)
    │   可能触发: style_memory.crystallize(...)
    ↓
[Step 5] agent.compute_signals(context)
    │   输出: base_signals (8D)
    ↓
[Step 6] metabolism.apply_thermodynamic_noise(base_signals)
    │   输出: noisy_signals (8D)
    ↓
[Step 7] style_memory.build_few_shot_prompt(context, ...)
    │   输出: few_shot (str)
    ↓
[Step 8] _build_single_prompt(few_shot, noisy_signals, ...)
    │   输出: single_prompt (str)
    ↓
[Step 8.5] memory injection (profile + episode + foresight + relevant)
    │   输出: enriched_single_prompt (str)
    ↓
[Step 9] llm.chat(single_messages)
    │   输出: raw_response → extract_reply() → monologue, reply, modality
    ↓
[Step 10] agent.step(context, reward, drive_satisfaction)
    │   内部: compute_signals → learn → tick_drives → age++
    │   更新: W1, W2, b1, b2, drive_state, recurrent_state
    ↓
[Step 11] _evermemos_store_bg(user_message, reply)
    │   asyncio.create_task() 非阻塞
    ↓
[Step 12] _evermemos_search_bg(user_message)
    │   asyncio.create_task() 非阻塞
    ↓
result: {reply: str, modality: str, [audio_path|image_path|segments|delays_ms]}
```

### 4.2 数据依赖图

```
context_12d ────────┬──→ Step 5 compute_signals ──→ Step 6 noise ──→ Step 7 KNN
                    │                                    │
                    │                                    ↓
                    │                               Step 8 prompt
                    │                                    │
                    │                                    ↓
                    │                               Step 9 Actor
                    │                                    │
                    └──→ Step 4 crystallize ←──────┘    │
                                                       ↓
                                                  Step 10 learn
                                                       │
                                                  context_12d (next turn)
```

注意上下文 `context_12d` 是一个贯穿始终的核心数据结构，它在第 5 步驱动信号计算，在第 10 步作为学习的环境输入，同时也会影响下一轮的判断。

---

## 五、每一步的必要性论证

### 为什么需要 Critic（Step 2）？

没有 Critic，引擎只能基于规则（关键词匹配）来理解用户输入。Critic 用 LLM 的语义理解能力将自然语言转换成结构化的数值感知，这是后续所有计算的基础。

### 为什么需要 Time Metabolism（Step 1）？

没有 Time Metabolism，角色会变成一个"无时间感"的存在 —— 无论用户隔了多久再发消息，角色的内部状态都一样。Time Metabolism 让角色会"忘记"之前的挫败，也会"想念"用户（connection hunger），这是拟人化的关键。

### 为什么需要 Hebbian Learning（Step 10）？

没有 Hebbian Learning，角色的神经网络权重是静态的。每轮对话产生同样的信号模式，角色永远不会"成长"或"改变"。Hebbian Learning 让角色的行为模式随着交互历史而演化。

### 为什么需要 Thermodynamic Noise（Step 6）？

没有 Noise，角色的行为是完全确定性的 —— 同样的输入永远产生同样的输出。Noise 引入了生物学般的随机性，让角色在高压（高 frustration）下表现得更加"情绪化"和不可预测。

### 为什么需要 Crystallization（Step 4）？

没有 Crystallization，Style Memory 会无限增长。Crystallization 通过"相似上下文合并"机制，将高频出现的反应模式压缩成更重的记忆节点，实现记忆的" gravitation "（引力凝聚）。

### 为什么需要 Async Memory（Step 11-12）？

EverMemOS 的存储和检索是跨会话的、网络 I/O 密集的。如果同步等待，每轮对话会增加 200-1000ms 的延迟。Async 让记忆操作在后台进行，不阻塞对话流。

---

## 六、并发与锁机制

```
async with self._turn_lock:
    await self._chat_inner(...)
```

每轮对话由一个 `asyncio.Lock` 串行化。这意味着：
- `chat()`、`chat_stream()`、`proactive_tick()` 不能并发执行
- 内部状态（drive_state, W1/W2, frustration）不会被竞态条件破坏
- 代价：如果某一步阻塞（如 LLM 调用超时），整个会话会卡住

这是一个**强一致性 vs 低延迟**的权衡。考虑到人格状态的一致性比毫秒级延迟更重要，这个设计是合理的。

---

## 七、后续文档导航

本系列共 13 篇文档，逐一深度分析每个步骤：

| # | 文档 | 分析步骤 | 核心代码 |
|---|---|---|---|
| 1 | [lifecycle-overview.md](lifecycle-overview.md) | 总览 | chat_agent.py |
| 2 | [lifecycle-step-00-evermemos.md](lifecycle-step-00-evermemos.md) | EverMemOS 会话上下文 | agent/evermemos_mixin.py |
| 3 | [lifecycle-step-01-metabolism.md](lifecycle-step-01-metabolism.md) | 时间代谢 | engine/genome/drive_metabolism.py |
| 4 | [lifecycle-step-02-critic.md](lifecycle-step-02-critic.md) | Critic 感知 | engine/genome/critic.py |
| 5 | [lifecycle-step-02p5-relationship.md](lifecycle-step-02p5-relationship.md) | 关系 EMA | chat_agent.py:_apply_relationship_ema |
| 6 | [lifecycle-step-03-reward.md](lifecycle-step-03-reward.md) | 奖励计算 | drive_metabolism.py:apply_llm_delta |
| 7 | [lifecycle-step-03p5-baseline.md](lifecycle-step-03p5-baseline.md) | 驱动基线演化 | chat_agent.py:baseline evolution loop |
| 8 | [lifecycle-step-04-crystal.md](lifecycle-step-04-crystal.md) | 结晶门 | style_memory.py:crystallize |
| 9 | [lifecycle-step-05-signals.md](lifecycle-step-05-signals.md) | 信号计算 | genome_engine.py:compute_signals |
| 10 | [lifecycle-step-06-noise.md](lifecycle-step-06-noise.md) | 热力学噪声 | drive_metabolism.py:apply_thermodynamic_noise |
| 11 | [lifecycle-step-07-knn.md](lifecycle-step-07-knn.md) | KNN 风格检索 | style_memory.py:retrieve/build_few_shot |
| 12 | [lifecycle-step-08-prompt.md](lifecycle-step-08-prompt.md) | Prompt 构建 | prompt_builder.py:_build_single_prompt |
| 13 | [lifecycle-step-09-actor.md](lifecycle-step-09-actor.md) | Actor 生成 | chat_agent.py:LLM call + parser.py |
| 14 | [lifecycle-step-10-hebbian.md](lifecycle-step-10-hebbian.md) | Hebbian 学习 | genome_engine.py:learn/step |
| 15 | [lifecycle-step-11-12-async.md](lifecycle-step-11-12-async.md) | 异步记忆 | evermemos_mixin.py + chat_agent.py |
| 16 | [lifecycle-summary.md](lifecycle-summary.md) | 完整串联汇总 | 全系统 |

---

## 八、一句话总结

> Genome v10 的单轮对话是一个**认知循环**：感知用户 → 更新内部状态 → 计算行为信号 → 生成表达 → 从反馈中学习。12 步不是冗余的 ceremony，而是让角色从"LLM 的 puppet"变成"有持续内在状态的 agent"的最小必要集合。
