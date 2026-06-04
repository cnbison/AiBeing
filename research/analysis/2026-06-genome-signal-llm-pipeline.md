---
date: 2026-06-04
topic: Genome 引擎信号如何通过 system prompt 影响 LLM 输出
scope: engine/genome/genome_engine.py, agent/prompt_builder.py, engine/prompts/actor_single.md
status: active
related: ../ARCHITECTURE.md, ../guides/persona-creation.md
---

> Genome 引擎负责计算"此刻角色内心状态"（8D signals），将其文本化为"舞台指令"后嵌入 system prompt，LLM 作为"演员"据此生成符合状态的回复。

## 背景

AiBeing 的人格系统不依赖静态 prompt 描述（如"她很温柔"），而是通过 `genome_seed` 中的 `drive_baseline` 和随机神经网络权重让行为自然涌现。一个关键问题是：**这些数值参数如何穿越代码层，最终影响大模型的输出？**

## 分析对象

涉及的核心文件：

- `engine/genome/genome_engine.py` — `Agent.compute_signals()` 前向传播、`to_prompt_injection_from_signals()` 文本化
- `engine/genome/drive_metabolism.py` — `DriveMetabolism` 时间代谢、热力学噪声
- `agent/prompt_builder.py` — `_build_single_prompt()` 组装 system prompt
- `engine/prompts/actor_single.md` — Single-Pass Actor 模板
- `agent/chat_agent.py` — 12 步生命周期中信号计算与 prompt 注入的调用链

## 数据流：从数字到回复的 5 个环节

### 环节 1：Genome 引擎计算信号（纯数学，无 LLM）

`Agent.compute_signals()` 执行 25D → 24D → 8D 的前向传播：

```
输入（25D）= 5D drive_state + 12D context + 8D recurrent_state
           ↓
    W1(24×25) + b1 → tanh → hidden(24D)
           ↓
    W2(8×24) + b2 → sigmoid → signals(8D)
```

8D signals 是角色的即时行为状态，每个值在 0~1 之间。例如 Luna 可能输出：

```
directness:    0.72   # 比较直接
vulnerability: 0.35   # 有点防御
playfulness:   0.81   # 很 playful
initiative:    0.55   # 适度引导
depth:         0.40   # 浅层对话
warmth:        0.68   # 温暖
defiance:      0.25   # 随和
curiosity:     0.60   # 好奇
```

这些数字来自**随机神经网络 + Hebbian 学习**，不是硬编码规则。

### 环节 2：数字 → 文本（舞台指令）

`to_prompt_injection_from_signals()` 将数字转换为 LLM 可理解的文本：

```
【舞台指令：角色当前状态】
🎯 直接度: 0.72 (0委婉→1直白)
💧 坦露度: 0.35 (0封闭→1袒露)
🎪 玩闹度: 0.81 (0正经→1调皮)
🚀 主动度: 0.55 (0被动→1主导)
🌊 深度: 0.40 (0闲聊→1探底)
🔥 温暖度: 0.68 (0冷淡→1热切)
⚡ 倔强度: 0.25 (0随和→1硬杠)
🔍 好奇度: 0.60 (0无感→1追问)

【舞台指令：角色内在需求】
🔗 联结: 0.78 (基线: 0.75, 渴望: 1.2)
✨ 新鲜: 0.52 (基线: 0.65, 渴望: 0.8)
...
```

关键设计：**只有数字 + 量表端点**，没有描述性文字。这是 CLAUDE.md 明确约束的：

> No static personality prompts: Do not add "she is gentle" to system prompts. Personality emerges from `genome_seed.drive_baseline` and neural network weights.

### 环节 3：System Prompt 组装

`_build_single_prompt()` 将以下部分拼接：

1. **角色身份**：`【角色】\nLuna，22岁，female。`
2. **舞台指令**（上面的 signal injection）
3. **变化趋势**（与上一轮 signals 的差值超过 `trend_delta` 时追加）
4. **KNN 检索的 few-shot 例子**：从 `ContinuousStyleMemory` 中找出最相似情境下的历史独白/回复
5. **Prompt 模板** (`actor_single.md`)：

```markdown
[角色参考]
以下是你在相似情境下的感受和说话方式：

$few_shot

$signal_injection

[指令]
你就是这个角色。你有自己的生活、工作和心事。
先写出你此刻脑海中真实浮现的念头——像正在发生一样，不是描述情绪，而是情绪本身。
然后写出你实际说出口的话，和你选择的表达方式。
...

[输出格式]
【内心独白】
...
【最终回复】
...
【表达方式】
...
```

### 环节 4：热力学噪声注入（可选干扰）

在 signal 进入 prompt 之前，`DriveMetabolism.apply_thermodynamic_noise()` 会根据 total frustration 添加高斯噪声：

```python
temp = max_temp * tanh(total_frustration * temp_coeff / max_temp) + temp_floor
noisy_signal = clamp(base_signal + gauss(0, temp), 0, 1)
```

Frustration 越高，噪声越大，signals 越不稳定 → LLM 收到的"舞台指令"越混乱 → 角色行为越情绪化、不可预测。

### 环节 5：LLM 接收并生成（唯一涉及 LLM 的环节）

LLM 不是"执行代码"或"解析数值做判断"，而是**把数字当作情境上下文来理解**，类似于演员看到剧本旁注：

| Signal 值 | LLM 的内隐关联 |
|---|---|
| `🎪 玩闹度: 0.81` | 俏皮、撒娇、轻松的语气和用词 |
| `💧 坦露度: 0.35` | 有所保留、不深入暴露情感 |
| `🚀 主动度: 0.55` | 适度引导话题，但不会太强势 |
| `⚡ 倔强度: 0.25` | 随和、配合、不顶嘴 |

**为什么数字有效？** LLM（Claude/GPT-4 级别）在预训练中学到了大量关于"情绪强度"、"直接程度"、"亲密程度"等概念的语境关联。`0.81` 配合 `0正经→1调皮` 的量表，提供了一个**可定位的连续空间坐标**，而不是离散标签。

## Drive Baseline 的间接影响路径

`drive_baseline` 不直接出现在 prompt 中，通过两条路径影响输出：

**路径 A：影响 signal 计算**

```
drive_baseline → Agent.compute_signals() 的输入
             → 改变 hidden 层激活
             → 改变 8D signals
             → 改变 prompt 文本
```

例如 Luna 的 `play: 0.80` 基线高，她的神经网络倾向于输出较高的 `playfulness`。

**路径 B：通过 metabolism 影响情绪温度**

```
frustration 累积 → DriveMetabolism.temperature() 上升
               → thermodynamic noise 增大
               → signals 更随机
               → LLM 收到更混乱的指令
```

例如 Luna 长时间无人互动，`connection` frustration 累积到 3.5，temperature 升高，回复变得更情绪化。

## 关键设计决策

| 设计 | 位置 | 理由 |
|---|---|---|
| **De-descriptified signals** | `genome_engine.py:480-489` | 只给数字和量表端点，不给文字描述，避免 LLM 机械执行 |
| **Single-pass Actor** | `actor_single.md` | 一轮 LLM 调用同时生成独白、回复、表达方式，减少延迟和上下文漂移 |
| **KNN few-shot 注入** | `style_memory.py:339` | 用历史真实反应作为示范，而非规则约束 |
| **Trend injection** | `prompt_builder.py:55-72` | 当 signal 变化剧烈时追加趋势提示，帮助 LLM 感知动态转变 |
| **Turn lock** | `chat_agent.py:134` | `asyncio.Lock` 保证每轮 signal 计算 → prompt 组装 → LLM 生成是原子的 |

## 验证方式

1. **日志观察**：`chat_agent.py:455-457` 每轮打印 `reward`, `temperature`, `modality` 和 `drive_sat`，可观察 signal 与输出的对应关系。
2. **Debug 端点**：`get_debug_status()` 返回完整 25D input、24D hidden、8D signals、frustration、relationship EMA 等，供可视化面板使用。
3. **A/B 测试**：修改 `SOUL.md` 中单个 `drive_baseline` 值（如 `play: 0.80 → 0.30`），观察多轮对话后 `playfulness` signal 均值是否下降。

## 总结

| 环节 | 做什么 | 是否涉及 LLM |
|---|---|---|
| Genome 引擎 | 神经网络把 context + drives 算成 8 个 0~1 数字 | 否 |
| 文本化 | 数字转成 `🎯 直接度: 0.72 (0委婉→1直白)` | 否 |
| Prompt 组装 | 角色身份 + 舞台指令 + few-shot 塞进 system prompt | 否 |
| **LLM Actor** | **读取数字和上下文，生成符合该状态的回复** | **是** |

Genome 引擎是**导演**（计算状态），LLM 是**演员**（演绎状态）。两者通过 system prompt 中的"舞台指令"完成协作。
