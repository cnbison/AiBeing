---
date: 2026-06-05
topic: Step 10 — Hebbian 学习（Hebbian Learning）
scope: engine/genome/genome_engine.py:learn, step
status: active
related: lifecycle-overview.md
---

> Hebbian 学习是 Genome 引擎的"神经可塑性"。它根据本轮的奖励信号，强化或削弱神经网络中的连接权重。这是角色"成长"的核心机制——每一次交互都在微妙地改变角色的行为模式，让"好的"反应更容易出现，"坏的"反应更难发生。

---

## 一、业务场景

假设 Luna 第 50 轮对话：
- 用户分享了一个秘密，Luna 温暖地回应了
- reward = +0.8（非常好的对话）

**没有 Hebbian Learning**：
- 第 100 轮，同样的情境，Luna 用同样的方式回应
- 权重不变，行为不变

**有 Hebbian Learning**：
- 第 50 轮后，产生温暖回应的神经网络连接被强化
- 第 100 轮，同样的情境，Luna 的 warmth signal 会更高、更稳定
- 她"学会"了：在这种情境下，温暖回应是有效的

再假设一次失败的交互：
- Luna 开了一个玩笑，但用户很冷淡
- reward = -0.4

Hebbian Learning 会削弱这次使用的连接，未来在相似情境下，Luna 的 playfulness signal 会略低——她"学会"了：这个用户在这种情况下不喜欢玩笑。

---

## 二、代码位置

```python
# chat_agent.py:422-423
clamped_reward = max(-1.0, min(1.0, reward))
self.agent.step(context, reward=clamped_reward, drive_satisfaction=drive_satisfaction)

# genome_engine.py:289-353
def learn(self, signals, reward, context, drive_satisfaction=None):

# genome_engine.py:355-362
def step(self, context, reward=0.0, drive_satisfaction=None):
```

---

## 三、核心算法

### 3.1 Hebbian 规则

经典 Hebbian 学习规则：**"一起激发的神经元连在一起"（Cells that fire together, wire together）**

在 Genome 引擎中：
- "一起激发" = hidden neuron 的激活值很高 + signal 的值偏离中点（0.5）
- "连在一起" = 增加它们之间的权重
- "奖励" = 决定是强化还是削弱

### 3.2 学习率

```python
lr = self.hebbian_lr * (1 + abs(reward))
# hebbian_lr 默认 0.02，角色可覆盖（Luna: 0.025）
```

**关键设计**：学习率与 reward 的绝对值成正比。
- reward = +0.1 → lr = 0.02 × 1.1 = 0.022
- reward = +0.9 → lr = 0.02 × 1.9 = 0.038

**含义**：强烈的情绪体验（无论是正面还是负面）产生更强的学习效果。这与人类心理学一致：我们更容易记住强烈的情绪事件。

### 3.3 输出层更新（W2）

```python
for i, sig_name in enumerate(SIGNALS):      # 8 个信号
    sig_val = signals[sig_name]             # 当前信号值 [0, 1]
    for j in range(HIDDEN_SIZE):            # 24 个隐藏神经元
        if abs(hidden[j]) > 0.05:           # 只更新活跃神经元
            self.W2[i][j] += lr * reward * hidden[j] * (sig_val - 0.5)
```

**更新量分解**：

```
ΔW2[i][j] = lr × reward × hidden[j] × (sig_val - 0.5)
            │    │       │            └─ 信号偏离中点的程度
            │    │       └─ 隐藏神经元激活强度
            │    └─ 正=强化，负=削弱
            └─ 学习率
```

**符号分析**：
- `reward > 0` + `sig_val > 0.5` + `hidden[j] > 0` → ΔW2 > 0（强化正向偏离）
- `reward > 0` + `sig_val < 0.5` + `hidden[j] > 0` → ΔW2 < 0（削弱负向偏离）
- `reward < 0` + `sig_val > 0.5` + `hidden[j] > 0` → ΔW2 < 0（反向削弱）

### 3.4 隐藏层更新（W1）

```python
if abs(reward) > 0.05:  # 只有显著奖励才更新隐藏层
    for i in range(HIDDEN_SIZE):
        if abs(hidden[i]) > 0.15:  # 更高的活跃度阈值
            for j in range(INPUT_SIZE):
                if full_input and abs(full_input[j]) > 0.05:
                    self.W1[i][j] += lr * 0.3 * reward * full_input[j] * hidden[i]
```

**差异点**：
- 隐藏层学习率只有输出层的 30%（`lr * 0.3`）
- 更高的激活阈值（0.15 vs 0.05）
- 更大的奖励阈值（|reward| > 0.05）

**原因**：隐藏层的改变影响更深远（改变的是"特征提取"方式），所以更保守。

### 3.5 挫败驱动的相变（Phase Transition）

```python
if reward < -0.1:
    self._frustration += abs(reward)
else:
    self._frustration = max(0, self._frustration - reward * 0.5)

if self._frustration > self.phase_threshold:
    # 相变！
    for i in range(N_SIGNALS):
        sig_val = signals[SIGNALS[i]]
        kick = -0.3 * (sig_val - 0.5) + random.gauss(0, 0.15)
        self.b2[i] += kick
    for i in range(HIDDEN_SIZE):
        self.b1[i] += random.gauss(0, 0.1)
    self._frustration = 0.0
    self._last_phase_transition = True
```

**相变的含义**：
- 持续负面奖励 → frustration 累积 → 超过阈值 → 相变
- 相变时，所有信号的偏置被大幅扰动
- 这模拟了"情绪爆发"或"心态转变"——角色突然"不像自己了"

**比喻**：
- 平时：平静的水面，涟漪很小
- 相变：累积的压力超过阈值，水面突然翻涌

### 3.6 权重衰减与截断

```python
# Weight decay
for i in range(N_SIGNALS):
    for j in range(HIDDEN_SIZE):
        self.W2[i][j] *= WEIGHT_DECAY  # 0.995
        self.W2[i][j] = max(-1.5, min(1.5, self.W2[i][j]))

for i in range(HIDDEN_SIZE):
    for j in range(INPUT_SIZE):
        self.W1[i][j] *= WEIGHT_DECAY  # 0.995
        self.W1[i][j] = max(-2.0, min(2.0, self.W1[i][j]))
```

**Weight Decay（0.995）**：
- 每轮所有权重衰减 0.5%
- 防止权重无限增长（信号饱和）
- 让旧的记忆逐渐淡化，新的学习占据主导

**Clip 边界**：
- W2: [-1.5, 1.5]
- W1: [-2.0, 2.0]
- 确保信号不会极端化

### 3.7 驱动满足

```python
if drive_satisfaction:
    for d in DRIVES:
        self.satisfy_drive(d, drive_satisfaction.get(d, 0.0))
```

根据 Critic 判断的 drive_satisfaction，直接减少对应驱动的当前值。这是"即时满足"——用户的行为直接缓解了角色的需求。

---

## 四、完整 step() 流程

```python
def step(self, context, reward=0.0, drive_satisfaction=None):
    signals = self.compute_signals(context)   # 重新计算 signals（用于学习）
    self.learn(signals, reward, context, drive_satisfaction)
    self.tick_drives()                        # 自然驱动累积
    self.age += 1
    return signals
```

注意：`step()` 内部又调用了一次 `compute_signals()`。为什么？

因为 `learn()` 需要 `_last_hidden` 和 `_last_input`，而这些值只在 `compute_signals()` 中设置。外部的 `compute_signals()`（Step 5）已经设置了这些值，但 `step()` 为了确保一致性会重新计算一次。

实际上在 `chat_agent.py` 的调用链中：
```python
# Step 5: 已经计算过 signals
base_signals = self.agent.compute_signals(context)

# ... Steps 6-9 ...

# Step 10: agent.step 内部再次调用 compute_signals
self.agent.step(context, reward=..., drive_satisfaction=...)
```

第二次计算的 signals 可能与 Step 5 的略有不同（因为 `tick_drives()` 可能已经改变了 drive_state）。这是设计上的微小不一致，但影响很小。

---

## 五、与后续步骤的关系

```
Step 10 更新
    ├── W1, W2, b1, b2 权重
    ├── drive_state（通过 satisfy_drive 和 tick_drives）
    ├── recurrent_state（通过 compute_signals）
    ├── interaction_count, total_reward, age
    └── _frustration（Agent 内部的挫败累积）
            ↓
    下一轮 Step 5: 新的权重产生新的 signals
    下一轮 Step 1: 新的 drive_state 影响 metabolism
```

Hebbian Learning 的效果是**跨轮次累积的**。单轮的权重变化很小（lr ~ 0.02），但 100 轮后累积的变化可能非常显著。

---

## 六、必要性论证

### 如果没有 Hebbian Learning：

1. **静态人格**：角色的行为模式永不改变
2. **无适应性**：无法从交互中学习"什么有效"
3. **无个性化**：所有用户的 Luna 行为完全一样
4. **浪费感知和奖励**：Critic 的感知和 reward 计算失去了意义

### 为什么用 Hebbian 而不是梯度下降？

梯度下降的问题：
- 需要定义明确的损失函数
- 需要反向传播，计算复杂
- 需要大量数据才能收敛

Hebbian 的优势：
- 局部学习：每个权重独立更新，不需要全局梯度
- 生物学合理性：模拟真实神经元的突触可塑性
- 在线学习：每轮都可以更新，不需要批量数据
- 简单高效：几行代码实现

### 为什么是"随机神经网络 + Hebbian"而不是"预训练网络 + 微调"？

预训练网络的问题：
- 需要大量对话数据预训练
- 预训练的行为模式是"平均"的，缺乏个性
- 微调容易过拟合到特定用户

随机神经网络 + Hebbian：
- 从零开始，完全由交互塑造
- 每个用户的角色行为模式都不同（个性化）
- 没有预设偏见，所有行为都是"学习出来的"

---

## 七、总结

> Step 10 是角色的"成长时刻"。它用 Hebbian 学习规则根据 reward 信号调整神经网络权重，让角色从每一次交互中学习。正向奖励强化当前的行为模式，负向奖励削弱它。相变机制模拟了情绪爆发——当挫败累积超过阈值时，角色的行为会发生剧烈扰动。Weight Decay 确保角色不会无限偏离初始性格，而是形成一个在"先天本能"和"后天学习"之间的动态平衡。
