---
date: 2026-06-05
topic: Step 5 — 信号计算（Compute Signals）
scope: engine/genome/genome_engine.py:compute_signals
status: active
related: 2026-06-lifecycle-overview.md
---

> 信号计算是 Genome 引擎的"大脑皮层"。它将 25 维输入（驱动状态 + 情境上下文 + 循环状态）通过随机神经网络转换成 8 维行为信号。这是从"内心状态"到"外在行为倾向"的核心映射。

---

## 一、业务场景

假设 Luna 当前的状态：
- **Drive state**: connection=0.8（很想你）, play=0.7（想玩闹）, safety=0.2（很放松）
- **Context**: user_emotion=-0.5（用户有点低落）, topic_intimacy=0.8（深夜心事）, conflict_level=0.0（无冲突）
- **Recurrent state**: [0.1, -0.2, 0.3, ...]（上轮留下的"情绪余韵"）

信号计算输出：
```
directness:    0.35  → 委婉一些（深夜心事，用户低落）
vulnerability: 0.65  → 愿意袒露脆弱（ intimacy 高，safety 低）
playfulness:   0.45  → 适度玩闹（play drive 高，但 context 不适合太闹）
initiative:    0.60  → 主动引导话题（connection 高，想深入聊）
depth:         0.75  → 深度对话（topic_intimacy 高）
warmth:        0.80  → 非常温暖（connection 高，user_emotion 负）
defiance:      0.20  → 顺从配合（conflict_level=0，safety 低）
curiosity:     0.55  → 适度好奇（想关心用户，但不逼问）
```

这 8 个数值就是 Luna "此刻的行为状态"——不是 prompt 写死的，而是从她的内心状态实时计算出来的。

---

## 二、代码位置

```python
# chat_agent.py:312
base_signals = self.agent.compute_signals(context)

# genome_engine.py:233-277
def compute_signals(self, context: dict) -> dict:
```

---

## 三、神经网络架构

### 3.1 输入层（25D）

```
输入向量 = [drive_vec(5D)] + [ctx_vec(12D)] + [recurrent_state(8D)]
         = 25 维
```

| 子向量 | 维度 | 来源 | 含义 |
|---|---|---|---|
| drive_vec | 5D | agent.drive_state | 当前驱动状态 |
| ctx_vec | 12D | context (Critic 8D + Relationship 4D) | 对话情境 |
| recurrent_state | 8D | agent.recurrent_state | 上轮隐藏层的"情绪记忆" |

**为什么需要 recurrent_state？**

没有 recurrent_state，每轮的信号计算只依赖当前输入，角色没有"连续性"。recurrent_state 让角色的行为有"惯性"——如果上轮很激动，这轮的 signals 也会带有一些激动的残留。

### 3.2 隐藏层（24D）

```python
hidden = []
for i in range(HIDDEN_SIZE):  # HIDDEN_SIZE = 24
    z = self.b1[i]
    for j, x in enumerate(full_input):
        z += self.W1[i][j] * x
    hidden.append(math.tanh(z))
```

- W1: 24 × 25 权重矩阵
- b1: 24 维偏置向量
- 激活函数: tanh（输出范围 [-1, 1]）

**为什么用 tanh？**

- 输出有界，防止梯度爆炸
- 负值可以表示"抑制"
- 对称性适合作为"情绪"的表示

### 3.3 循环状态更新

```python
self.recurrent_state = hidden[:RECURRENT_SIZE]  # RECURRENT_SIZE = 8
```

隐藏层的前 8 维被截取出来，作为下一轮的 recurrent_state。这是**简单 RNN**的设计——没有 LSTM/GRU 的门控机制，但足以传递"情绪惯性"。

### 3.4 输出层（8D → Signals）

```python
for i in range(N_SIGNALS):  # N_SIGNALS = 8
    z = self.b2[i]
    for j, h in enumerate(hidden):
        z += self.W2[i][j] * h
    z /= math.sqrt(HIDDEN_SIZE / 3)  # 缩放归一化
    raw_signals.append(z)

# Sigmoid → [0, 1]
signals[name] = 1.0 / (1.0 + math.exp(-clip(raw, -10, 10)))
```

- W2: 8 × 24 权重矩阵
- b2: 8 维偏置向量
- 缩放因子: `sqrt(24/3) ≈ 2.83`，防止 sigmoid 饱和
- 最终通过 sigmoid 映射到 [0, 1]

**为什么用 sigmoid？**

- 输出范围 [0, 1]，与信号的语义匹配（0=最低，1=最高）
- 平滑可导，适合 Hebbian Learning

### 3.5 感知噪声

```python
full_input = [v + random.gauss(0, 0.03) for v in full_input]
```

在输入层添加微小的高斯噪声（σ=0.03），模拟生物神经元的感知噪声。这让同样的输入可能产生略微不同的输出，增加行为的自然变化。

---

## 四、权重初始化

```python
# __init__ 中，seed 决定所有随机性
rng = random.Random(seed)

self.W1 = [[rng.gauss(0, 0.6) for _ in range(INPUT_SIZE)] for _ in range(HIDDEN_SIZE)]
self.b1 = [rng.gauss(0, 0.3) for _ in range(HIDDEN_SIZE)]
self.W2 = [[rng.gauss(0, 0.2) for _ in range(HIDDEN_SIZE)] for _ in range(N_SIGNALS)]
self.b2 = [rng.gauss(0, 0.2) for _ in range(N_SIGNALS)]
self.recurrent_state = [rng.gauss(0, 0.1) for _ in range(RECURRENT_SIZE)]
```

**为什么用 seed 控制随机性？**

- 相同的 persona_id → 相同的 seed → 相同的初始权重
- 这让同一角色在不同 session 中有**确定性的初始性格**
- 但后续权重会通过 Hebbian Learning 发散，形成个性化的行为模式

**标准差的设计**：
- W1 (σ=0.6): 输入层→隐藏层，需要较强的信号传递
- W2 (σ=0.2): 隐藏层→输出层，更保守的映射，防止信号极端化

---

## 五、8D Signals 详解

| 信号 | 0 端 | 1 端 | 对 Luna 的典型范围 |
|---|---|---|---|
| `directness` | 委婉暗示 | 直说 | 0.3-0.7（视 safety 而定） |
| `vulnerability` | 防御心理 | 袒露脆弱 | 0.4-0.8（高 warmth 时更高） |
| `playfulness` | 认真严肃 | 玩闹撒娇 | 0.6-0.9（ENFP 典型高值） |
| `initiative` | 被动回应 | 主动引导 | 0.5-0.8（connection 高时更高） |
| `depth` | 表面闲聊 | 深度对话 | 视 intimacy 而定 |
| `warmth` | 冷淡疏离 | 热情关怀 | 0.6-0.9（F 型典型高值） |
| `defiance` | 顺从 | 反抗/嘴硬 | 0.1-0.4（低 safety 时可能升高） |
| `curiosity` | 无所谓 | 追问到底 | 0.4-0.7（N 型典型中高值） |

---

## 六、与后续步骤的关系

```
Step 5 输出: base_signals (8D, 0~1)
    ↓
Step 6 (Thermodynamic Noise): base_signals + noise → noisy_signals
    ↓
Step 7 (KNN): noisy_signals 不直接参与，但 context 用于检索
    ↓
Step 8 (Prompt): noisy_signals 被文本化为"舞台指令"
    ↓
Step 9 (Actor): LLM 根据"舞台指令"生成回复
    ↓
Step 10 (Hebbian): self._last_hidden 和 signals 用于更新 W1/W2
```

---

## 七、必要性论证

### 如果没有 Signal 计算：

1. **行为与状态脱节**：drive_state 和 context 无法转化为具体的行为倾向
2. **无连续性**：每轮独立计算，没有 recurrent_state 的"情绪惯性"
3. **无法学习**：Hebbian Learning 需要 W1/W2 权重，没有神经网络就没有可学习的参数
4. **无个性差异**：所有角色都依赖 prompt 描述，没有内在的、可演化的人格

### 为什么是随机神经网络？

**为什么不直接用规则映射？**

规则映射：
```python
if context['conflict_level'] > 0.5:
    signals['defiance'] = 0.8
```

问题：规则是设计者预设的，角色只能执行已知规则，无法产生"意外"行为。

随机神经网络：
- 权重是随机的，但**模式**会在交互中涌现
- 同样的输入可能产生不同的输出（取决于权重组合）
- Hebbian Learning 让"好的"模式被强化，"坏的"模式被削弱
- 角色的行为是**学习出来的**，不是**写进去的**

---

## 八、总结

> Step 5 是 Genome 引擎的"神经中枢"。25 维输入通过随机神经网络映射到 8 维行为信号，这是从"内心"到"行为"的桥梁。recurrent_state 提供连续性，感知噪声提供自然变化，sigmoid 提供有界的输出。这个网络不是被设计的，而是被学习的——每一轮对话都在通过 Hebbian Learning 微调这些权重，让角色的行为模式越来越贴合用户的交互风格。
