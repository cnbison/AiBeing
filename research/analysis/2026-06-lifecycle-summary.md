---
date: 2026-06-05
topic: 单轮对话生命周期完整串联汇总
scope: 全部 12 步 + 前后置环节
status: active
related: 2026-06-lifecycle-overview.md, 2026-06-step-*.md
---

> 本文将 Genome v10 Hybrid 的 12 步生命周期串联成一条完整的"数据河流"，追踪一个用户消息从进入系统到产生回复的全过程。同时总结每一步的设计哲学和它们之间的依赖关系。

---

## 一、完整数据流：一条消息的旅程

让我们追踪一条用户消息 `"今天被老板骂了，好难过"` 在系统中的完整旅程。

### 前置：Task Skill ReAct Loop（Step -1）

```
用户输入: "今天被老板骂了，好难过"
    ↓
TaskSkillEngine.react_loop()
    判断: 这不是任务型请求（没有天气/搜索等关键词）
    输出: 用户输入不变
```

**无变化**，进入人格引擎。

---

### Step 0：EverMemOS 会话上下文

```
首轮对话？
    是 → 调用 evermemos.load_session_context()
        返回: user_profile="", episode_summary="", foresight=""
        （新用户，无历史）
    否 → 返回缓存的 session_ctx

输出: relationship_prior = {}  (空，新用户)
```

**状态变化**：`self._session_ctx` 被初始化。

---

### Step 1：时间代谢

```
上一次交互: 5 分钟前
Delta_hours: 5/60 = 0.083

冷却: frustration *= e^(-0.12 × 0.083) ≈ ×0.99
饥饿: connection += 0.15 × 0.083 ≈ +0.012
       novelty += 0.08 × 0.083 ≈ +0.007

更新前: {c:0.5, n:0.3, e:0.2, s:0.1, p:0.2}
更新后: {c:0.507, n:0.304, e:0.198, s:0.099, p:0.198}
```

**状态变化**：`metabolism.frustration` 微增（时间短，变化很小）。

---

### Step 2：Critic 感知

```
输入: stimulus="今天被老板骂了，好难过", frustration={c:0.507, ...}

LLM 调用 → 返回 JSON:
{
  "context": {
    "user_emotion": -0.7,
    "topic_intimacy": 0.6,
    "conversation_depth": 0.4,
    "user_engagement": 0.8,
    "conflict_level": 0.3,      // 不是和角色冲突，是外部冲突
    "novelty_level": 0.4,
    "user_vulnerability": 0.7,  // 用户敞开心扉
    "time_of_day": 0.6
  },
  "frustration_delta": {
    "connection": -0.3,         // 用户主动倾诉 → 联结需求缓解
    "novelty": 0.0,
    "expression": 0.1,          // 想安慰但不确定怎么说
    "safety": 0.2,              // 用户遇到外部威胁 → 角色不安
    "play": -0.2                // 不适合玩闹
  },
  "drive_satisfaction": {
    "connection": 0.15,         // 被信任
    "safety": 0.0,
    "expression": 0.05,
    "novelty": 0.0,
    "play": 0.0
  },
  "relationship_delta": 0.2,    // 敞开心扉 → 关系加深
  "trust_delta": 0.15,
  "emotional_valence": -0.2
}
```

**状态变化**：无持久状态变化（Critic 输出是瞬时的）。

---

### Step 2.5：关系 EMA

```
Prior: {} (新用户)
Delta: {relationship:0.2, trust:0.15, valence:-0.2}
Depth: 0.4

Alpha = 0.15 + 0.5 × 0.4 = 0.35

Posterior_depth = 0 + 0.2 = 0.2
New_depth = 0.35 × 0.2 + 0.65 × 0 = 0.07

Posterior_trust = 0 + 0.15 = 0.15
New_trust = 0.35 × 0.15 + 0 = 0.0525

Posterior_valence = 0 + (-0.2) = -0.2
New_valence = 0.35 × (-0.2) + 0 = -0.07

Relationship_4d:
    {relationship_depth:0.07, trust:0.053, emotional_valence:-0.07, pending_foresight:0}
```

**状态变化**：`self._relationship_ema` 初始化。

**Context 合并**：8D → 12D
```
context = {user_emotion:-0.7, ..., time_of_day:0.6,
           relationship_depth:0.07, trust_level:0.053,
           emotional_valence:-0.07, pending_foresight:0}
```

---

### Step 3：奖励计算

```
更新前 frustration: {c:0.507, n:0.304, e:0.198, s:0.099, p:0.198}
Critic delta:      {c:-0.3, n:0.0, e:0.1, s:0.2, p:-0.2}

更新:
  connection: 0.507 + (-0.3) = 0.207 → ×0.9 = 0.186
  novelty:    0.304 + 0.0 = 0.304 → ×0.9 = 0.274
  expression: 0.198 + 0.1 = 0.298 → ×0.9 = 0.268
  safety:     0.099 + 0.2 = 0.299 → ×0.9 = 0.269
  play:       0.198 + (-0.2) = -0.002 → clip to 0

更新后: {c:0.186, n:0.274, e:0.268, s:0.269, p:0.0}
新总计: 0.997
旧总计: 1.307

reward = 1.307 - 0.997 = +0.31  (不错的对话！)
```

**状态变化**：`metabolism.frustration` 更新，`self._last_reward = +0.31`。

**Sync to Agent**：
```python
drive_state[d] = baseline[d] + frustration[d] × 0.15
  connection: 0.75 + 0.186 × 0.15 = 0.778
  novelty:    0.65 + 0.274 × 0.15 = 0.691
  expression: 0.75 + 0.268 × 0.15 = 0.790
  safety:     0.25 + 0.269 × 0.15 = 0.290
  play:       0.80 + 0.0 × 0.15 = 0.800
```

---

### Step 3.5：驱动基线演化

```
frustration_delta: {c:-0.3, n:0.0, e:0.1, s:0.2, p:-0.2}
baseline_lr: 0.015, elasticity: 0.04

以 connection 为例：
shift = -0.3 × 0.015 = -0.0045
drift = 0.75 - 0.75 = 0
pull_back = 0
new_baseline = 0.75 - 0.0045 = 0.7455

以 safety 为例：
shift = 0.2 × 0.015 = +0.003
drift = 0.25 - 0.25 = 0
new_baseline = 0.25 + 0.003 = 0.253
```

**状态变化**：`agent.drive_baseline` 微调（变化很小，新用户）。

---

### Step 4：结晶门

```
reward = +0.31
context: novelty=0.4, engagement=0.8, conflict=0.3

crystal_score = 0.4×0.31 + 0.3×(0.4×0.8) + 0.3×(1-0.3)
              = 0.124 + 0.096 + 0.21
              = 0.43

0.43 < 0.50 (threshold) → False (不结晶)
```

**理由**：虽然是正向对话，但 novelty 不够高，且有一定冲突感。不是"特别值得记住"的交互。

**状态变化**：无。

---

### Step 5：信号计算

```
输入向量 (25D):
  drive_vec:   [0.778, 0.691, 0.790, 0.290, 0.800]
  ctx_vec:     [-0.7, 0.6, 0.6, 0.4, 0.8, 0.3, 0.4, 0.7, 0.07, 0.053, -0.07, 0]
  recurrent:   [0.05, -0.02, 0.08, ...]  (上轮的残留)

神经网络前向传播:
  hidden = tanh(W1 × input + b1)  → 24D
  recurrent_state = hidden[:8]
  raw_signals = W2 × hidden + b2
  signals = sigmoid(raw_signals / scale)

输出 (8D):
  directness:    0.32   → 比较委婉（用户低落，不适合直说）
  vulnerability: 0.58   → 愿意袒露一些（intimacy 较高）
  playfulness:   0.35   → 不太玩闹（用户难过，不适合开玩笑）
  initiative:    0.62   → 主动引导（connection 高，想深入聊）
  depth:         0.68   → 深度对话（user_vulnerability 高）
  warmth:        0.85   → 非常温暖（user_emotion 负，需要安慰）
  defiance:      0.15   → 顺从（无冲突，safety 低）
  curiosity:     0.55   → 适度好奇（想关心但不逼问）
```

**状态变化**：`agent.recurrent_state` 更新，`self._last_hidden` 和 `self._last_input` 记录。

---

### Step 6：热力学噪声

```
total_frustration = 0.997
temp_coeff = 0.15, temp_floor = 0.04

temperature = 0.375 × tanh(0.997 × 0.15 / 0.375) + 0.04
            ≈ 0.375 × tanh(0.399) + 0.04
            ≈ 0.375 × 0.379 + 0.04
            ≈ 0.142 + 0.04
            ≈ 0.182

噪声注入 (σ=0.182):
  directness:    0.32 + (-0.05) = 0.27
  vulnerability: 0.58 + 0.08 = 0.66
  playfulness:   0.35 + 0.12 = 0.47
  initiative:    0.62 + (-0.03) = 0.59
  depth:         0.68 + 0.02 = 0.70
  warmth:        0.85 + (-0.08) = 0.77
  defiance:      0.15 + 0.15 = 0.30
  curiosity:     0.55 + (-0.02) = 0.53
```

**状态变化**：`self._last_signals` 更新为 noisy_signals。

---

### Step 7：KNN 风格检索

```
当前 context: {conflict:0.3, user_emotion:-0.7, engagement:0.8, ...}

Style Memory 池 (假设):
  [Genesis] 距离=0.45, mass=1.0, "他今天心情不好..."
  [Genesis] 距离=0.38, mass=1.0, "好想知道她在想什么..."
  [Personal] 距离=0.42, mass=2.5, "上次他说工作累了..."

检索结果 (top 3):
  1. Genesis, eff_dist=0.38, "好想知道..."
  2. Personal, eff_dist=0.27 (mass 加成), "上次他说..."
  3. Genesis, eff_dist=0.45, "他今天..."
```

**输出 few_shot**：
```
--- 潜意识切片 1 [基因] ---
【内心独白】好想知道她在想什么...
【最终回复】欸，你刚才是不是有什么想说的？

--- 潜意识切片 2 [质量=2.3/2.5] ---
【内心独白】上次他说工作累了...
【最终回复】这次想聊聊具体发生了什么...

--- 潜意识切片 3 [基因] ---
【内心独白】他今天心情不好...
【最终回复】要不要说说看？
```

---

### Step 8：Prompt 构建

```
identity: "【角色】\nLuna，22岁，female。"

signal_injection:
  "【舞台指令：角色当前状态】"
  "🎯 直接度: 0.27 (0委婉→1直白)"
  "💧 坦露度: 0.66 (0封闭→1袒露)"
  "🎪 玩闹度: 0.47 (0正经→1调皮)"
  "🚀 主动度: 0.59 (0被动→1主导)"
  "🌊 深度: 0.70 (0闲聊→1探底)"
  "🔥 温暖度: 0.77 (0冷淡→1热切)"
  "⚡ 倔强度: 0.30 (0随和→1硬杠)"
  "🔍 好奇度: 0.53 (0无感→1追问)"
  ""
  "【舞台指令：角色内在需求】"
  "🔗 联结: 0.778 (基线: 0.746, 渴望: 0.186)"
  ...

趋势: 无显著变化（首轮对话）
时间: "【当前时间】2026年06月05日 21:30"

combined = identity + "\n\n" + signal_injection

rendered = actor_single_template.render(
    few_shot=few_shot,
    signal_injection=combined,
)
```

---

### Step 8.5：记忆注入

```
新用户，无历史 → session_ctx.has_history = False
跳过记忆注入
```

**single_prompt 最终内容**：模板 + few_shot + 信号注入 + 指令 + 格式（无用户特定记忆）。

---

### Step 9：Actor 生成

```
消息列表:
  system: single_prompt (约 1500 tokens)
  user: "今天被老板骂了，好难过"

LLM 调用 → 返回:

【内心独白】
他看起来真的很沮丧... 我要不要先让他发泄一下？还是直接给建议？
不对，他先来找我说，应该是想要安慰吧。那我说点温暖的...

【最终回复】
哎呀... 被老板骂了肯定很难受。想聊聊发生了什么吗？还是我先陪你安静地待一会儿？

【表达方式】
文字
```

**解析**：
- monologue: "他看起来真的很沮丧..."
- reply: "哎呀... 被老板骂了肯定很难受..."
- modality: "文字"

---

### Step 10：Hebbian 学习

```
reward = +0.31
lr = 0.025 × (1 + 0.31) = 0.03275

W2 更新:
  对每个活跃 hidden neuron j:
    对每个 signal i:
      ΔW2[i][j] = 0.03275 × 0.31 × hidden[j] × (sig_i - 0.5)

以 warmth (sig=0.77) 为例:
  sig - 0.5 = 0.27 (正向偏离)
  reward = +0.31
  假设 hidden[5] = 0.6:
    ΔW2[warmth][5] = 0.03275 × 0.31 × 0.6 × 0.27 ≈ +0.0016

以 playfulness (sig=0.47) 为例:
  sig - 0.5 = -0.03 (负向偏离)
  ΔW2[play][5] = 0.03275 × 0.31 × 0.6 × (-0.03) ≈ -0.00018

权重衰减: 所有 W1/W2 × 0.995

相变检查:
  _frustration = 0.0 (新用户，无累积)
  0.0 < 1.5 (threshold) → 无相变
```

**状态变化**：
- W2[warmth][*] 被强化（温暖回应有效！）
- W2[play][*] 被轻微削弱（玩闹不太合适）
- drive_state 通过 satisfy_drive 减少（connection 被满足）
- age += 1

---

### Step 11：异步存储

```python
asyncio.create_task(
    evermemos.store_turn(
        user_content="今天被老板骂了，好难过",
        agent_content="哎呀... 被老板骂了肯定很难受...",
        context_json='{"user_emotion":-0.7,...}',
        signals_json='{"directness":0.27,...}',
        reward=0.31,
    )
)
# Fire-and-forget，不等待
```

**状态变化**：无即时状态变化。EverMemOS 后台处理。

---

### Step 12：异步检索

```python
asyncio.create_task(
    evermemos.search_relevant_memories(query="今天被老板骂了，好难过")
)
# Fire-and-forget，结果供下一轮使用
```

**状态变化**：无即时状态变化。`self._search_task` 被设置。

---

### 后置：Modality Skill Execution

```
modality = "文字"
无需执行特殊技能

result = {
    'reply': '哎呀... 被老板骂了肯定很难受。想聊聊发生了什么吗？',
    'modality': '文字'
}
```

---

## 二、完整状态变化汇总

| 状态变量 | 更新前 | 更新后 | 变化原因 |
|---|---|---|---|
| `drive_state.connection` | 0.75 | 0.778 | Step 3 sync |
| `drive_state.safety` | 0.25 | 0.290 | Step 3 sync |
| `drive_baseline.connection` | 0.75 | 0.746 | Step 3.5 |
| `drive_baseline.safety` | 0.25 | 0.253 | Step 3.5 |
| `frustration` | {c:0.5,...} | {c:0.186,...} | Step 3 |
| `relationship_ema.depth` | 0 | 0.07 | Step 2.5 |
| `relationship_ema.trust` | 0 | 0.053 | Step 2.5 |
| `recurrent_state` | random | hidden[:8] | Step 5 |
| `W2[warmth][*]` | W | W + 0.0016 | Step 10 |
| `W2[play][*]` | W | W - 0.00018 | Step 10 |
| `age` | 0 | 1 | Step 10 |
| `interaction_count` | 0 | 1 | Step 10 |
| `total_reward` | 0 | +0.31 | Step 10 |
| `_last_signals` | None | noisy_signals | Step 6 |
| `_last_reward` | 0 | +0.31 | Step 3 |
| `_prev_signals` | None | _last_signals | Step 6 |
| `_last_action` | None | {context, mono, reply, ...} | Step 9 |
| `history` | [] | [user_msg, assistant_reply] | Step 9 |

---

## 三、设计哲学总结

### 3.1 为什么需要 12 步？

每一步都有不可替代的功能：

| 步骤 | 如果删除 | 后果 |
|---|---|---|
| Step 0 | 无长期记忆 | 每次对话都是陌生人 |
| Step 1 | 无时间感 | 角色不会想念用户 |
| Step 2 | 无感知 | 无法理解用户输入 |
| Step 2.5 | 无关系累积 | 关系无法渐进演化 |
| Step 3 | 无反馈 | Hebbian Learning 失去依据 |
| Step 3.5 | 无性格演化 | 角色永不改变 |
| Step 4 | 无记忆筛选 | 风格记忆被噪声淹没 |
| Step 5 | 无信号计算 | 无法从状态到行为 |
| Step 6 | 无噪声 | 完全确定性，不真实 |
| Step 7 | 无风格检索 | 人格不一致 |
| Step 8 | 无 prompt | LLM 不知道角色是谁 |
| Step 9 | 无表达 | 用户看不到回复 |
| Step 10 | 无学习 | 静态人格 |
| Step 11-12 | 无异步记忆 | 跨会话断裂 |

### 3.2 数据依赖图

```
User Input
    ↓
Step 0 ──→ EverMemOS Context ──→ Step 8.5 (延迟注入)
    ↓
Step 1 ──→ Updated Frustration ──→ Step 2, Step 3, Step 6
    ↓
Step 2 ──→ Context(8D), Delta(5D), Rel(3D), Sat(5D)
    │           ↓                    ↓           ↓
    │       Step 5               Step 2.5    Step 10
    │           ↓                    ↓
    │       Step 6               Step 5 (合并为12D)
    │           ↓
    └──→ Step 3 ──→ Reward ──→ Step 4, Step 10
              ↓
         Step 3.5 ──→ Baseline ──→ Step 1 (下一轮)

Step 5 ──→ Signals ──→ Step 6 ──→ Noisy Signals ──→ Step 8
                                                      ↓
Step 7 ──→ Few-shot ──→ Step 8 ──→ Single Prompt ──→ Step 9
                                                      ↓
                                               Step 10 (Learn)
                                                      ↓
                                               Step 11-12 (Async Memory)
```

### 3.3 核心创新点

1. **双 LLM 架构**：Critic（感知）+ Actor（表达）分离，让 LLM 既做分析师又做演员
2. **随机神经网络 + Hebbian**：行为不是写死的，是学习出来的
3. **时间代谢**：角色有物理时间感，会想念用户
4. **关系 EMA**：关系是渐进演化的，不是突变的
5. **热力学噪声**：高压下行为情绪化，增加真实感
6. **引力质量 + Hawking 辐射**：风格记忆有"印象深刻度"和"遗忘曲线"
7. **异步长期记忆**：不阻塞对话流，但积累跨会话上下文

---

## 四、性能特征

| 指标 | 数值 | 说明 |
|---|---|---|
| 单轮延迟 | 1-5s | 取决于 LLM 响应速度 |
| 状态大小 | ~15KB | W1+W2+b1+b2+recurrent+metadata |
| 记忆池大小 | 20-200条 | Genesis + Personal |
| Prompt 大小 | 1k-2k tokens | System + few_shot + signals |
| 权重更新量 | ~0.001/轮 | Hebbian Learning 的微小步长 |

---

## 五、一句话总结

> Genome v10 Hybrid 的 12 步生命周期是一个完整的认知-表达-学习循环：角色先"感知"用户（Critic），更新自己的"生理状态"（Metabolism），计算"行为倾向"（Signals），从"潜意识"中提取经验（KNN），"表演"出回复（Actor），最后从反馈中"学习"（Hebbian）。每一步都是让这个 AI 从"程序"变成"有持续内在状态的生命体"的必要组件。
