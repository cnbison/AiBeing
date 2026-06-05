---
date: 2026-06-05
topic: Step 2.5 — 关系 EMA 更新（Semi-Emergent Relationship Update）
scope: agent/chat_agent.py:_apply_relationship_ema
status: active
related: 2026-06-lifecycle-overview.md
---

> 关系 EMA 是 Genome v10 的"情感记账本"。它将 Critic 判断的本轮关系变化与历史累积的关系状态融合，形成渐进式的关系演化。这让角色对用户的认知不是突变式的，而是在长期互动中慢慢加深或疏远。

---

## 一、业务场景

假设你们已经聊了 20 轮：

**第 20 轮，Critic 判断**：用户刚才的回复比较冷淡，`relationship_delta = -0.2`

没有 EMA 的版本：
- relationship_depth 从 0.8 直接跳到 0.6（一次对话关系倒退很多）
- 角色突然变得疏远，感觉不真实

有 EMA 的版本：
- EMA 融合：`alpha × 本轮变化 + (1-alpha) × 历史状态`
- 由于有 19 轮的累积，单轮 -0.2 只让 depth 从 0.8 降到 0.75
- 角色仍把你当老朋友，只是察觉到一丝冷淡

**第 3 轮，同样的 -0.2**：
- 由于没有太多历史累积，EMA 后 depth 从 0.2 降到 0.12
- 角色明显感觉到关系在变冷

这就是 EMA 的核心价值：**同样的行为变化，在历史关系深浅不同时，产生不同的感知强度**。

---

## 二、代码位置

```python
# chat_agent.py:277-279
relationship_4d = self._apply_relationship_ema(
    relationship_prior, rel_delta, context.get('conversation_depth', 0.0)
)
context.update(relationship_4d)  # Merge 8D + 4D → 12D

# chat_agent.py (具体实现在 _apply_relationship_ema 方法)
```

---

## 三、核心算法

### 3.1 数学公式

关系 EMA 使用指数移动平均（Exponential Moving Average）：

```
posterior = clip(prior + LLM_delta, -1, 1)
alpha = clip(0.15 + 0.5 × depth, 0.15, 0.65)
ema_state = alpha × posterior + (1 - alpha) × previous_ema
```

**三个关键操作**：

1. **Posterior（后验）**：`prior + delta`
   - 将 Critic 判断的"变化量"叠加到历史先验上
   - `clip` 防止超出 [-1, 1] 范围

2. **Alpha（学习率）**：`0.15 + 0.5 × conversation_depth`
   - 对话越深，alpha 越大（对新变化越敏感）
   - 范围限制在 [0.15, 0.65]
   - 浅层聊天：alpha ≈ 0.15（历史权重 85%，变化影响小）
   - 深度交流：alpha ≈ 0.65（历史权重 35%，变化影响大）

3. **EMA 融合**：`alpha × posterior + (1-alpha) × prev`
   - 经典 EMA 公式
   - 产生平滑的渐进式更新

### 3.2 为什么 alpha 与 conversation_depth 正相关？

**直觉解释**：
- 刚认识的陌生人（depth=0.1）：一次深聊可能大幅改变印象（但我们限制 alpha ≤ 0.65，防止过度敏感）
- 老朋友（depth=0.8）：应该已经了解对方，单次行为的改变不应该大幅改变整体关系判断

等一下，这和公式似乎矛盾。让我们重新理解：

```
alpha = 0.15 + 0.5 × depth
```

- depth=0.1 → alpha=0.20 → 新信息权重 20%
- depth=0.8 → alpha=0.55 → 新信息权重 55%

**深层逻辑**：在深度对话中，用户透露的信息更多、更真实，所以本轮的 `relationship_delta` 更可靠，值得更高的权重。而在浅层对话中，用户的反应可能只是礼貌性敷衍，不应过度解读。

---

## 四、详细执行流程

### 4.1 输入

```python
relationship_prior: dict   # 来自 Step 0 (EverMemOS) 或上一轮 EMA
    {
        'relationship_depth': 0.3,
        'trust_level': 0.2,
        'emotional_valence': 0.1,
        'pending_foresight': 0.0,
    }

rel_delta: dict            # 来自 Step 2 (Critic)
    {
        'relationship_delta': 0.2,
        'trust_delta': 0.15,
        'emotional_valence': 0.3,
    }

conversation_depth: float  # 来自 Critic context (当前轮)
```

### 4.2 计算过程

```python
# 1. 计算 posterior
posterior_depth = clip(prior['relationship_depth'] + rel_delta['relationship_delta'], -1, 1)
posterior_trust = clip(prior['trust_level'] + rel_delta['trust_delta'], -1, 1)
posterior_valence = clip(prior['emotional_valence'] + rel_delta['emotional_valence'], -1, 1)

# 2. 计算 alpha
alpha = clip(0.15 + 0.5 * conversation_depth, 0.15, 0.65)
# 例：depth=0.5 → alpha=0.40

# 3. EMA 融合
new_depth = alpha * posterior_depth + (1 - alpha) * prior['relationship_depth']
new_trust = alpha * posterior_trust + (1 - alpha) * prior['trust_level']
new_valence = alpha * posterior_valence + (1 - alpha) * prior['emotional_valence']

# 4. 构建 4D 输出
relationship_4d = {
    'relationship_depth': new_depth,
    'trust_level': new_trust,
    'emotional_valence': new_valence,
    'pending_foresight': prior.get('pending_foresight', 0.0),
}
```

### 4.3 合并到 Context

```python
context.update(relationship_4d)  # 8D + 4D → 12D
```

这 12 维 context 就是后续 `Agent.compute_signals()` 的输入。

---

## 五、数值示例

### 场景 A：新用户第一次深聊

```
Prior:  {depth: 0.0, trust: 0.0, valence: 0.0}
Delta:  {relationship: 0.3, trust: 0.2, valence: 0.4}
Depth:  0.7 (Critic 判断这是一次深度对话)

Alpha = 0.15 + 0.5 × 0.7 = 0.50

Posterior_depth = 0.0 + 0.3 = 0.3
New_depth = 0.5 × 0.3 + 0.5 × 0.0 = 0.15

Posterior_trust = 0.0 + 0.2 = 0.2
New_trust = 0.5 × 0.2 + 0.5 × 0.0 = 0.10

Result: {depth: 0.15, trust: 0.10, valence: 0.20}
```

**解读**：虽然是深度对话且 delta 正向，但 EMA 让关系增长保持克制。不会因为一次好对话就变成挚友。

### 场景 B：老朋友一次冷淡回复

```
Prior:  {depth: 0.8, trust: 0.7, valence: 0.6}
Delta:  {relationship: -0.2, trust: -0.1, valence: -0.3}
Depth:  0.3 (Critic 判断这次回复比较敷衍)

Alpha = 0.15 + 0.5 × 0.3 = 0.30

Posterior_depth = 0.8 + (-0.2) = 0.6
New_depth = 0.3 × 0.6 + 0.7 × 0.8 = 0.18 + 0.56 = 0.74

Result: {depth: 0.74, trust: 0.58, valence: 0.33}
```

**解读**：虽然有负面变化，但 70% 的历史权重让关系只轻微下降。角色仍把你当老朋友，只是察觉到不对劲。

---

## 六、与后续步骤的关系

```
Step 2.5 输出: relationship_4d
    ↓
merged into context → 12D context
    ↓
Step 5 (compute_signals): W1 的输入包含 relationship_depth, trust_level 等
    ↓
Step 9 (Actor prompt): relationship 信息也会通过 context 间接影响 prompt
```

relationship_depth 等维度在 `Agent.compute_signals()` 中作为输入特征，影响 hidden 层激活，进而影响 8D signals 的输出。这意味着：**角色越信任你，她的行为信号（直接度、坦露度、温暖度等）会自然变化**。

---

## 七、必要性论证

### 如果没有 Relationship EMA：

1. **关系突变不真实**：一轮对话就能让角色从"陌生人"变成"挚友"，或反之
2. **无历史累积**：每次新 session 的关系状态完全取决于 Critic 的单轮判断
3. **无法体现"了解"的深度**：老朋友应该对新信息有更强的"免疫力"（更稳定的判断）
4. **缺少长期叙事连续性**：角色无法形成"我们认识很久了"的持续感知

### 为什么是 EMA 而不是简单累加？

简单累加的问题：
- `depth += delta` → 20 轮正向 delta(0.1) = depth=2.0（超出范围）
- 需要不断 clip，导致后期 delta 完全无效

EMA 的优势：
- 天然有界（在 [-1, 1] 范围内）
- 历史权重衰减但永不消失（长期关系有累积效应）
- 对新变化的敏感度可调节（通过 alpha）

---

## 八、总结

> Step 2.5 是角色的"情感记账本"。它用指数移动平均将 Critic 的单轮判断与历史关系状态平滑融合，让角色的关系认知既不是反应过度的敏感，也不是冷漠不变的迟钝。EMA 的 alpha 与 conversation_depth 正相关，意味着越深的对话，角色的关系判断越愿意被更新 —— 就像人类在深聊后会重新评估对一个人的了解。
