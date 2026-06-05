---
date: 2026-06-05
topic: Step 3 — 奖励计算（LLM Metabolism → Reward）
scope: engine/genome/drive_metabolism.py:apply_llm_delta
status: active
related: lifecycle-overview.md
---

> 奖励计算是 Genome 引擎的"情绪翻译器"。它将 Critic 判断的挫败变化量（frustration_delta）转换成单一的 reward 信号，供 Hebbian Learning 使用。这是一个从多维变化到标量反馈的降维过程，是连接"感知"与"学习"的关键桥梁。

---

## 一、业务场景

假设 Critic 输出了这样的 frustration_delta：

```json
{
  "connection": -0.3,    // 联结需求被缓解（用户亲近了）→ 好事
  "novelty": 0.0,        // 无变化
  "expression": 0.1,     // 表达欲轻微上升（有点想说但没说够）
  "safety": -0.2,        // 安全感提升（用户很友善）→ 好事
  "play": 0.5            // 玩闹欲大幅上升（气氛不够轻松）→ 坏事
}
```

这些多维度变化如何变成"这一轮的对话是好是坏"的单一判断？

**Reward 计算**：总挫败感下降了 0.4 → reward = +0.4 → 这是不错的一轮对话

这个 reward 将告诉 Hebbian Learning："这一轮产生的 signals 是好的，强化它们！"

---

## 二、代码位置

```python
# chat_agent.py:284
reward = self.metabolism.apply_llm_delta(frustration_delta)
self.metabolism.sync_to_agent(self.agent)
self._last_reward = reward

# drive_metabolism.py:89
def apply_llm_delta(self, delta_dict: dict) -> float:
```

---

## 三、核心算法

### 3.1 两个操作

```python
def apply_llm_delta(self, delta_dict: dict) -> float:
    old_total = self.total()  # 更新前的总挫败感

    # 1. 应用 Critic 判断的变化量
    for d in DRIVES:
        if d in delta_dict:
            self.frustration[d] += delta_dict[d]
        self.frustration[d] *= (1.0 - self.decay_rate)  # 每轮额外衰减 10%

    # 2. 截断到合法范围
    for d in DRIVES:
        self.frustration[d] = max(0.0, min(5.0, self.frustration[d]))

    # 3. 返回 reward = 挫败感的减少量
    return old_total - self.total()
```

### 3.2 Reward 的含义

```
reward > 0  → 总挫败感下降 → 用户的回复让角色更满足了 → "好的对话"
reward = 0  → 总挫败感不变 → "中性的对话"
reward < 0  → 总挫败感上升 → 用户的回复让角色更挫败了 → "差的对话"
```

### 3.3 为什么用"总挫败感的减少量"？

这是**RL（强化学习）的视角**：
- Agent（角色）在每一轮选择一个行为（signals → reply）
- Environment（用户）给出反馈（frustration_delta）
- Reward 是环境反馈的标量总结
- Hebbian Learning 用这个 reward 来更新神经网络的权重

**关键洞察**：reward 不是用户输入的"好坏"，而是"角色对这次交互的满意度变化"。

---

## 四、详细执行流程

### 4.1 输入

```python
frustration_delta: dict  # 来自 Step 2 (Critic)
    {'connection': -0.3, 'novelty': 0.0, 'expression': 0.1, 'safety': -0.2, 'play': 0.5}

self.frustration: dict   # 当前状态（已更新自 Step 1 Time Metabolism）
    {'connection': 2.0, 'novelty': 0.8, 'expression': 0.5, 'safety': 0.3, 'play': 0.4}
```

### 4.2 计算

```python
# 1. 记录更新前的总挫败感
old_total = 2.0 + 0.8 + 0.5 + 0.3 + 0.4 = 4.0

# 2. 应用 delta
frustration['connection'] = 2.0 + (-0.3) = 1.7
frustration['novelty'] = 0.8 + 0.0 = 0.8
frustration['expression'] = 0.5 + 0.1 = 0.6
frustration['safety'] = 0.3 + (-0.2) = 0.1
frustration['play'] = 0.4 + 0.5 = 0.9

# 3. 每轮额外衰减（decay_rate=0.1）
frustration['connection'] = 1.7 × 0.9 = 1.53
frustration['novelty'] = 0.8 × 0.9 = 0.72
...

# 4. 截断
for d in DRIVES:
    frustration[d] = max(0.0, min(5.0, frustration[d]))

# 5. 计算新总挫败感
new_total = 1.53 + 0.72 + 0.54 + 0.09 + 0.81 = 3.69

# 6. Reward
reward = old_total - new_total = 4.0 - 3.69 = +0.31
```

### 4.3 sync_to_agent

```python
# chat_agent.py:285
self.metabolism.sync_to_agent(self.agent)

# drive_metabolism.py:138
def sync_to_agent(self, agent):
    for d in DRIVES:
        agent.drive_state[d] = min(1.0,
            agent.drive_baseline.get(d, 0.5) + self.frustration[d] * 0.15)
    agent._frustration = self.total()
```

`sync_to_agent` 将 metabolism 的 frustration 状态同步到 Agent 的 drive_state：

```
drive_state[d] = baseline[d] + frustration[d] × 0.15
```

**为什么 frustration 要乘以 0.15？**

- Frustration 范围是 [0, 5]
- Baseline 范围是 [0.2, 0.8]
- `frustration × 0.15` 范围是 [0, 0.75]
- 所以 `drive_state` 范围大约是 [0.2, 1.55]，然后 clip 到 [0, 1]

这个缩放因子确保：frustration 可以显著影响 drive_state（从基线推高到接近 1.0），但不会让 drive_state 超出合理范围。

---

## 五、数值示例

### 场景 A：用户温暖回应

```
更新前 frustration: {c:2.0, n:0.8, e:0.5, s:0.3, p:0.4}  total=4.0
Critic delta:        {c:-0.5, n:0.0, e:-0.1, s:-0.3, p:-0.2}

更新后 frustration:  {c:1.35, n:0.72, e:0.36, s:0.0, p:0.18}  total=2.61
reward = 4.0 - 2.61 = +1.39  → 非常好的对话！
```

### 场景 B：用户冷漠回应

```
更新前 frustration: {c:1.5, n:0.5, e:0.3, s:0.2, p:0.3}  total=2.8
Critic delta:        {c:0.4, n:0.0, e:0.2, s:0.1, p:0.0}

更新后 frustration:  {c:1.71, n:0.45, e:0.45, s:0.27, p:0.27}  total=3.15
reward = 2.8 - 3.15 = -0.35  → 不太好的对话
```

### 场景 C：混合变化

```
更新前 frustration: {c:1.0, n:1.0, e:1.0, s:1.0, p:1.0}  total=5.0
Critic delta:        {c:-0.8, n:0.5, e:-0.3, s:0.4, p:-0.2}

更新后 frustration:  {c:0.18, n:1.35, e:0.63, s:1.26, p:0.72}  total=4.14
reward = 5.0 - 4.14 = +0.86  → 整体不错（connection 的大幅满足抵消了其他上升的挫败）
```

---

## 六、与后续步骤的关系

```
Step 3 输出: reward (float)
    ├──→ Step 4 (crystallization): reward > 0.8 时强制结晶
    ├──→ Step 10 (Hebbian learning): learn(signals, reward, ...)
    │       W2[i][j] += lr * reward * hidden[j] * (sig_val - 0.5)
    │       正 reward → 强化当前连接
    │       负 reward → 削弱当前连接
    └──→ Step 3.5 (baseline evolution): 间接影响（通过 frustration_delta）

Step 3 副作用: updated frustration + sync_to_agent
    └──→ Step 5 (compute_signals 的 drive_state 输入已更新)
```

---

## 七、必要性论证

### 如果没有 Reward 计算：

1. **Hebbian Learning 无反馈信号**：神经网络不知道这一轮的行为是好是坏
2. **无 Crystallization 触发条件**：无法判断哪些交互值得记住
3. **无学习闭环**：引擎变成纯前馈系统，不会从交互中进化
4. **无情绪反馈**：角色的 frustration 只增不减（只有 Step 1 的冷却，没有 Step 3 的缓解）

### 为什么用"总挫败感变化"而不是其他 reward 设计？

**替代方案 1：直接求和 delta**
- `reward = sum(delta_dict.values())`
- 问题：不考虑现有挫败感的基数。一个 high-frustration 状态下的 -0.3 和一个 low-frustration 状态下的 -0.3，意义不同

**替代方案 2：固定阈值**
- `reward = 1 if sum(delta) > 0 else -1`
- 问题：丢失了变化的幅度信息

**当前方案（总挫败感变化）的优势**：
- 考虑了所有驱动的综合效果
- 保留了变化的幅度（-2.0 和 +0.1 有不同的学习强度）
- 与 Hebbian Learning 的数学形式自然匹配

---

## 八、总结

> Step 3 是连接"感知"和"学习"的翻译器。它将 Critic 的多维挫败变化降维成一个标量 reward，决定了 Hebbian Learning 是强化还是削弱本轮的神经连接。这个步骤虽然简单（几行加减法），但它是让整个引擎具有"从经验中学习"能力的核心枢纽。没有 reward，神经网络将永远是静态的随机权重；有了 reward，每一次交互都在塑造角色的行为模式。
