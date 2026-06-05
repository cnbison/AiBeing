---
date: 2026-06-05
topic: Step 2 — Critic 感知（Critic Perception）
scope: engine/genome/critic.py
status: active
related: lifecycle-overview.md
---

> Critic 是 Genome 引擎的"感官系统"。它用 LLM 的语义理解能力将用户的自然语言输入转换成结构化的数值向量 —— 8 维情境感知 + 5 维挫败变化 + 3 维关系变化 + 5 维需求满足。这些数值是后续所有计算的基础。

---

## 一、业务场景

用户输入："今天被老板骂了，心情好差。"

没有 Critic 的版本（纯关键词匹配）：
- 检测到"骂"→ 冲突度高
- 检测到"心情差"→ 用户情绪负面
- 但无法理解：这是需要安慰？还是需要空间？还是只是发泄？

有 Critic 的版本（LLM 语义理解）：
```json
{
  "context": {
    "user_emotion": -0.7,        // 明显负面情绪
    "topic_intimacy": 0.6,        // 工作话题，有一定私人色彩
    "conversation_depth": 0.5,    // 中等深度
    "user_engagement": 0.8,       // 用户主动分享，投入度高
    "conflict_level": 0.4,        // 不是和用户冲突，是外部冲突
    "novelty_level": 0.5,         // 新信息
    "user_vulnerability": 0.7,    // 用户敞开心扉了
    "time_of_day": 0.5
  },
  "frustration_delta": {
    "connection": -0.4,           // 用户主动倾诉 → 联结需求被缓解
    "novelty": 0.0,
    "expression": 0.1,            // 想表达安慰但不确定该说什么
    "safety": 0.3,                // 用户遇到麻烦 → 安全感下降
    "play": -0.2                  // 不是玩闹的场合
  },
  "drive_satisfaction": {
    "connection": 0.15,           // 用户信任并倾诉 → 联结被满足
    "safety": 0.0,
    "expression": 0.05,           // 有机会表达关心
    "novelty": 0.0,
    "play": 0.0
  },
  "relationship_delta": 0.2,      // 用户敞开心扉 → 关系加深
  "trust_delta": 0.15,           // 被信任
  "emotional_valence": -0.3      // 整体负面基调
}
```

Critic 不仅识别了情绪，还理解了**这对角色意味着什么** —— 用户的倾诉满足了角色的联结需求，但也让角色感到需要保护的焦虑。

---

## 二、代码位置

```python
# chat_agent.py:269-274
context, frustration_delta, rel_delta, drive_satisfaction = await critic_sense(
    user_message, self.llm, frust_dict,
    user_profile=self._user_profile,
    episode_summary=self._episode_summary,
    persona_hint=_persona_hint,
)

# engine/genome/critic.py:76
def critic_sense(stimulus, llm, frustration, user_profile, episode_summary, persona_hint)
```

---

## 三、详细执行流程

### 3.1 构建 Critic Prompt

Critic 的 prompt 由四个部分组成：

```
[系统指令]
你是一个角色扮演 Agent 的情感感知器。分析用户输入，输出四组数据：

1. 对话上下文感知（8 维）
2. Agent 5 个驱力的挫败变化量
3. 关系感知变化量
4. Agent 5 个内在需求的满足量

[角色锚定]
你正在为以下角色感知用户意图：Luna (ENFP) — 明朗、活泼、甜美
请根据此角色的性格特点判断 drive_satisfaction。

[长期记忆]
关于这个用户的历史画像：{user_profile}
与此用户的历史对话叙事：{episode_summary}

[当前状态]
Agent 当前挫败值：{frustration_json}

[用户输入]
请分析以下用户输入并输出JSON："{stimulus}"
```

**关键设计**：Critic 是**角色感知**的 —— 同一个用户输入，对 Luna（ENFP）和 Kai（ISTP）的 `drive_satisfaction` 判断应该不同。Luna 可能从"用户倾诉"中获得大量联结满足，而 Kai 可能更关注"用户是否尊重他的空间"。

### 3.2 LLM 调用

```python
messages = [
    ChatMessage(role="system", content=prompt),
    ChatMessage(role="user", content=f'请分析以下用户输入并输出JSON："{stimulus}"'),
]
response = await llm.chat(messages, temperature=0.2)
```

**为什么 temperature=0.2？**

Critic 是一个"分析任务"而非"创意任务"，需要稳定、可预测的结构化输出。低 temperature 减少随机性，提高 JSON 解析成功率。

### 3.3 输出解析

Critic 的输出是纯 JSON。解析过程包含多层容错：

```python
raw = response.content.strip()

# 1. 剥离 think 标签（Qwen3 模型输出）
raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()

# 2. 清理 markdown 代码块
raw = re.sub(r'```json\s*', '', raw)
raw = re.sub(r'```\s*', '', raw)

# 3. JSON 解析
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    # 4. 回退：通过括号计数提取第一个完整 JSON 对象
    start = raw.find('{')
    for i in range(start, len(raw)):
        if raw[i] == '{': depth += 1
        elif raw[i] == '}': depth -= 1
        if depth == 0:
            data = json.loads(raw[start:i+1])
            break
```

### 3.4 数值提取与截断

解析成功后，提取四个输出组：

**8D Context**（Critic 输出维度）：
```python
for feat in _CRITIC_CONTEXT_KEYS:
    v = float(raw_ctx.get(feat, 0.5))
    if feat == 'user_emotion':
        context[feat] = max(-1.0, min(1.0, v))   # 情绪范围 [-1, 1]
    else:
        context[feat] = max(0.0, min(1.0, v))    # 其他维度 [0, 1]
```

**5D Frustration Delta**（挫败变化量）：
```python
for d in DRIVES:
    v = float(raw_delta.get(d, 0.0))
    frustration_delta[d] = max(-3.0, min(3.0, v))  # 变化量范围 [-3, 3]
```

**3D Relationship Delta**（关系变化量）：
```python
rel_delta = {
    'relationship_delta': max(-1.0, min(1.0, ...)),  # [-1, 1]
    'trust_delta': max(-1.0, min(1.0, ...)),         # [-1, 1]
    'emotional_valence': max(-1.0, min(1.0, ...)),   # [-1, 1]
}
```

**5D Drive Satisfaction**（需求满足量）：
```python
for d in DRIVES:
    v = float(raw_sat.get(d, 0.0))
    drive_satisfaction[d] = max(0.0, min(0.3, v))   # [0, 0.3]
```

### 3.5 错误回退

如果解析完全失败（JSON 损坏、字段缺失），Critic 会**重试一次**（用更明确的 JSON 指令），如果仍然失败则返回默认值：

```python
return _DEFAULT_CONTEXT, _DEFAULT_DELTA, _DEFAULT_REL_DELTA, _DEFAULT_SATISFACTION
```

默认值为中性：`context=0.5`, `delta=0`, `satisfaction=0`。

---

## 四、输出详解

### 4.1 8D Context（情境感知）

| 维度 | 范围 | 含义 | 示例值解读 |
|---|---|---|---|
| `user_emotion` | [-1, 1] | 用户情绪 | -0.7=难过，0.8=开心 |
| `topic_intimacy` | [0, 1] | 话题私密性 | 0.9=深夜心事，0.1=天气闲聊 |
| `conversation_depth` | [0, 1] | 对话深度 | 0.2=寒暄，0.8=灵魂交流 |
| `user_engagement` | [0, 1] | 用户投入度 | 0.9=长文倾诉，0.1="嗯嗯" |
| `conflict_level` | [0, 1] | 冲突程度 | 0.8=吵架中，0=和谐 |
| `novelty_level` | [0, 1] | 信息新鲜度 | 0.9=全新话题，0.1=重复询问 |
| `user_vulnerability` | [0, 1] | 用户敞开度 | 0.8=卸下防备，0.2=敷衍 |
| `time_of_day` | [0, 1] | 时间氛围 | 0.95=深夜，0.1=清晨 |

### 4.2 5D Frustration Delta（挫败变化量）

**正** = 更挫败（这个驱动未被满足，更渴望了）
**负** = 被缓解（这个驱动被满足了，不渴望了）

| 驱动 | 正值含义 | 负值含义 |
|---|---|---|
| `connection` | 用户疏远/冷漠 → 更想联结 | 用户主动亲近 → 联结需求被满足 |
| `novelty` | 话题重复无聊 → 更想新鲜事 | 用户带来新信息 → 好奇心被满足 |
| `expression` | 被打断/不被倾听 → 更想表达 | 用户认真倾听 → 表达欲被满足 |
| `safety` | 被批评/威胁 → 更想安全 | 用户接纳/肯定 → 安全感被满足 |
| `play` | 气氛严肃沉重 → 更想玩闹 | 用户开玩笑 → 玩闹欲被满足 |

### 4.3 3D Relationship Delta（关系变化量）

| 维度 | 正值 | 负值 |
|---|---|---|
| `relationship_delta` | 关系加深（用户更信任/亲近） | 关系疏远（用户冷淡/防御） |
| `trust_delta` | 信任增加 | 信任减少 |
| `emotional_valence` | 对话整体正面 | 对话整体负面 |

### 4.4 5D Drive Satisfaction（需求满足量）

与 Frustration Delta 的区别：
- **Frustration Delta** 是"变化"（relative）— 这一轮相比上一轮，挫败感变了多少
- **Drive Satisfaction** 是"绝对量"（absolute）— 这一轮用户的具体行为，直接满足了多少需求

**为什么两者可能同时非零？**

举个复杂例子：
- 用户说了"你好"然后立刻离开（冷落）
- Frustration Delta: `connection: +0.5`（联结需求更挫败了，因为被冷落）
- Drive Satisfaction: `connection: 0.0`（用户的行为没有直接满足联结需求）

另一个例子：
- 用户主动分享了一个秘密
- Frustration Delta: `connection: -0.3`（联结需求被缓解了，因为用户亲近了）
- Drive Satisfaction: `connection: 0.15`（用户的行为直接满足了联结需求）

---

## 五、与后续步骤的关系

```
Step 2 输出
    ├── context (8D) ───────────→ Step 5 (compute_signals 的输入)
    ├── frustration_delta (5D) ─→ Step 3 (apply_llm_delta → reward)
    ├── rel_delta (3D) ─────────→ Step 2.5 (Relationship EMA)
    └── drive_satisfaction (5D) ─→ Step 10 (Hebbian learning)
```

Critic 的四个输出分别流向四个不同的后续步骤，这是 Critic 作为"感知中枢"的核心地位。

---

## 六、必要性论证

### 如果没有 Critic：

1. **引擎无法理解自然语言**：只能做关键词匹配，无法理解隐喻、反讽、潜台词
2. **无反馈闭环**：Hebbian Learning 需要 reward，reward 来自 frustration_delta，frustration_delta 来自 Critic
3. **无关系演进**：Relationship EMA 需要 rel_delta，rel_delta 来自 Critic
4. **Context 缺失**：Agent.compute_signals() 需要 12D context，其中 8D 来自 Critic

### 为什么用 LLM 做 Critic，而不是规则引擎？

规则引擎的局限：
- "被老板骂了" → 规则：包含"骂"→ 冲突度高 → 但这不是用户和角色的冲突
- "你真好" → 规则：正面词汇 → 但可能是讽刺

LLM 的优势：
- 理解上下文和意图
- 处理隐喻和反讽
- 根据 persona 调整判断（同样的输入，对 Luna 和 Kai 的 satisfaction 不同）

### 代价

Critic 是单轮对话中**最昂贵的步骤之一**：
- 一次完整的 LLM API 调用（~200-2000ms）
- 每次都需要发送完整的 prompt（含 user_profile、episode、frustration 状态）

这是延迟与智能之间的 trade-off。在语音对话分析中，这也是主要的延迟瓶颈之一。

---

## 七、总结

> Step 2 是 Genome 引擎的"感官神经"。它把用户的自然语言转换成机器可处理的数值向量，让引擎"理解"当前对话的情绪、深度、冲突和关系变化。没有 Critic，后续的 signal 计算、reward 反馈、Hebbian 学习都将失去依据。它是连接"人类语言"和"机器认知"的桥梁。
