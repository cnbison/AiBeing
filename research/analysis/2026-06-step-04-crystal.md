---
date: 2026-06-05
topic: Step 4 — 结晶门（Crystallization Gate）
scope: engine/genome/style_memory.py:crystallize, agent/prompt_builder.py:_should_crystallize
status: active
related: lifecycle-overview.md
---

> 结晶门是 Genome 引擎的"记忆筛选器"。它决定上一轮产生的交互是否值得存入长期风格记忆。不是每一轮对话都值得记住——只有那些"有趣、有深度、有正向反馈"的交互才配被结晶。

---

## 一、业务场景

假设你和 Luna 聊了 20 轮：

**第 5 轮**：你分享了工作压力，Luna 给了温暖的安慰 → reward=+0.9，话题亲密度高 → **结晶！** 这条记忆被存入 style_memory，未来在相似情境下会被检索出来作为参考。

**第 12 轮**：你问"今天天气怎么样"，Luna 回答"今天晴天" → reward=+0.1，话题很浅，无新意 → **不结晶。** 这条日常闲聊不值得占用记忆空间。

**第 15 轮**：你们因为某个观点发生了争执 → reward=-0.6 → **不结晶。** 负面交互被主动遗忘（这与人类心理学一致：人们倾向于记住美好回忆）。

结晶门让角色的记忆不是简单的"录音机"，而是有选择性的"意义提取器"。

---

## 二、代码位置

```python
# chat_agent.py:301-309
if self._last_action and self._should_crystallize(reward, context):
    self.style_memory.set_clock(now)
    self.style_memory.crystallize(
        self._last_action['context'],
        self._last_action['monologue'],
        self._last_action['reply'],
        self._last_action['user_input'],
    )

# prompt_builder.py:117-149
def _should_crystallize(self, reward: float, context: dict) -> bool:

# style_memory.py:274
def crystallize(self, context, monologue, reply, user_input=""):
```

---

## 三、核心算法

### 3.1 复合评分

结晶门不使用简单的 `reward > threshold`，而是使用**复合评分**：

```python
crystal_score = (
    0.4 * reward
    + 0.3 * (novelty * engagement)
    + 0.3 * (1.0 - conflict)
)
```

三个维度：

| 维度 | 权重 | 含义 |
|---|---|---|
| `reward` | 40% | 用户反馈有多好（角色是否满足） |
| `novelty × engagement` | 30% | 话题是否有趣且用户投入 |
| `1 - conflict` | 30% | 是否和谐（惩罚冲突） |

**为什么这样设计？**

- 纯 reward 会错过"用户投入但角色不满足"的深度对话
- 纯 novelty 会记录大量猎奇但无意义的对话
- 复合评分确保：**值得记住的 = 正向反馈 + 深度投入 + 和谐氛围**

### 3.2 硬边界

```python
if reward < -0.5:
    return False  # 明显糟糕的交互，绝不记录
if reward > 0.8:
    return True   # 明显优秀的交互，强制记录
```

**硬下限（-0.5）**：即使 novelty 和 engagement 都很高，如果 reward 很差，说明角色在这次交互中很挫败。记录这种记忆会让角色在未来重复失败的行为模式。

**硬上限（0.8）**：无论其他指标如何，只要 reward 极高，就值得记录。这是"黄金样本"——角色做对了什么，未来应该参考。

### 3.3 阈值比较

```python
should = crystal_score > self.crystal_threshold
# crystal_threshold 默认 0.50，角色可覆盖
```

---

## 四、详细执行流程

### 4.1 输入

```python
reward: float               # 来自 Step 3
context: dict               # 来自 Step 2 (Critic 输出的 12D context)
self.crystal_threshold: float  # 默认 0.50，角色可覆盖
```

### 4.2 计算示例

**场景 A：深度安慰**
```
reward = +0.9
novelty = 0.3, engagement = 0.9, conflict = 0.0

crystal_score = 0.4*0.9 + 0.3*(0.3*0.9) + 0.3*(1.0-0.0)
              = 0.36 + 0.081 + 0.3
              = 0.741

0.741 > 0.50 → True (结晶!)
```

**场景 B：日常闲聊**
```
reward = +0.2
novelty = 0.1, engagement = 0.3, conflict = 0.0

crystal_score = 0.4*0.2 + 0.3*(0.1*0.3) + 0.3*1.0
              = 0.08 + 0.009 + 0.3
              = 0.389

0.389 < 0.50 → False (不结晶)
```

**场景 C：激烈争吵**
```
reward = -0.4
novelty = 0.8, engagement = 0.9, conflict = 0.9

crystal_score = 0.4*(-0.4) + 0.3*(0.8*0.9) + 0.3*(1.0-0.9)
              = -0.16 + 0.216 + 0.03
              = 0.086

但 reward=-0.4 < -0.5? 不，-0.4 > -0.5，所以不触发硬下限。
0.086 < 0.50 → False (不结晶)
```

### 4.3 结晶操作

当 `_should_crystallize` 返回 True 时，调用 `style_memory.crystallize()`：

```python
self.style_memory.crystallize(
    context=self._last_action['context'],      # 12D 情境向量
    monologue=self._last_action['monologue'],  # 内心独白
    reply=self._last_action['reply'],          # 最终回复
    user_input=self._last_action['user_input'], # 用户输入
)
```

**注意**：结晶的是**上一轮**的交互（`self._last_action`），而不是当前轮。因为当前轮还没有完成（Actor 还没生成回复），无法判断好坏。

### 4.4 结晶的内部逻辑

`style_memory.crystallize()` 执行两种操作之一：

**A. 引力增厚（Gravitational Thickening）**

如果新 context 与池中某个记忆的物理距离 < 0.25：
```python
self._pool[best_idx]['mass'] += 1.0
self._pool[best_idx]['last_used_at'] = now
# 可选：如果新回复更长更丰富，覆盖原文
```

**含义**："我在类似情境下已经这么回应过很多次了，这个反应模式很重要。"

**B. 创建新记忆**

如果没有相似记忆：
```python
new_mem = {
    "vector": new_vec,         # 8D context 向量
    "monologue": monologue,    # 内心独白
    "reply": reply,            # 最终回复
    "user_input": user_input,  # 用户输入
    "mass": 2.0,               # 初始质量（比 genesis 高）
    "created_at": now,
    "last_used_at": now,
}
self._pool.append(new_mem)
```

**含义**："这是一个全新的情境，我需要记住我是怎么回应的。"

---

## 五、记忆类型

Style Memory 中有两种记忆：

| 类型 | 来源 | mass | 持久性 |
|---|---|---|---|
| **Genesis** | 预加载（seeds.bin） | 1.0（永不增长） | 会话级，重启重置 |
| **Personal** | 结晶产生 | ≥2.0（可增长） | 用户级，跨会话持久 |

**Genesis** 是角色的"先天本能"——出厂时预置的反应模式。
**Personal** 是角色的"后天经验"——从实际交互中学习到的反应模式。

KNN 检索时，Personal 记忆的 mass 更高（有效质量 = mass / distance），因此后天经验会优先于先天本能。

---

## 六、与后续步骤的关系

```
Step 4 (当前轮)
    判断: _should_crystallize(reward, context)
    如果为 True: style_memory.crystallize(...)
        ↓
Step 7 (下一轮及以后)
    style_memory.retrieve(context) → 可能检索到本轮结晶的记忆
        ↓
Step 8 (Prompt)
    few_shot 包含本轮结晶的记忆
```

结晶是一个**延迟生效**的操作：本轮结晶的记忆，最早在**下一轮**的 KNN 检索中可能被使用。

---

## 七、必要性论证

### 如果没有 Crystallization：

1. **记忆无限增长**：每轮都存，style_memory 会膨胀到数千条，KNN 检索变慢
2. **噪声淹没信号**：大量无意义的闲聊记忆会稀释真正有价值的反应模式
3. **负面模式固化**：如果记录了失败的交互，角色会重复错误
4. **无质量差异**：所有记忆权重相同，无法区分"本能反应"和"精心回应"

### 为什么用复合评分而不是简单阈值？

**纯 reward 的问题**：
- 用户问"1+1=？"，角色回答"2" → reward=+0.1（满足但无聊）
- 不应该记住这种交互

**纯 novelty 的问题**：
- 用户说了一个奇怪的梗，角色不知道怎么回应 → novelty=0.9, reward=-0.5
- 不应该记住这种失败

**复合评分的优势**：
- 需要同时满足"正向"、"投入"、"和谐"三个条件
- 更接近人类"值得记住的对话"的判断标准

---

## 八、总结

> Step 4 是角色的"意义筛选器"。它用复合评分（reward × novelty × engagement × harmony）判断上一轮交互是否值得存入长期记忆。只有"好的、深的、和谐的"对话才会被结晶，这让角色的风格记忆保持高质量，同时通过引力增厚机制让高频反应模式自然浮现。没有结晶门，角色会记住一切——包括噪音和失败。
