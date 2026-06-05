---
date: 2026-06-05
topic: Step 3.5 — 驱动基线演化（Drive Baseline Evolution）
scope: agent/chat_agent.py:288-299
status: active
related: lifecycle-overview.md
---

> 驱动基线演化是 Genome 引擎的"性格漂移"机制。它让角色的长期性格不是固定不变的，而是会随着交互历史缓慢演化。但这种演化不是无限制的——弹性拉回力（elasticity）确保角色不会变成完全不同的人。

---

## 一、业务场景

假设 Luna 的初始 drive_baseline（来自 SOUL.md）：

```yaml
drive_baseline:
  connection: 0.75   # 高联结需求（ENFP 的典型特征）
  novelty: 0.65
  expression: 0.75
  safety: 0.25
  play: 0.80
```

连续 50 轮对话后，用户一直很冷淡、敷衍：
- 没有 Step 3.5：Luna 仍然是那个热情主动的 Luna，每轮都 high playfulness/high warmth
- 有 Step 3.5：Luna 的 connection baseline 从 0.75 慢慢降到 0.55，她变得不那么主动了，学会了保持一定的距离

但即使被冷落了很久，如果某天用户突然热情起来，Luna 的基线会慢慢回升——**弹性拉回力**让她保留了一些"原本的热情"。

---

## 二、代码位置

```python
# chat_agent.py:288-299
for d in DRIVES:
    shift = frustration_delta.get(d, 0.0) * self.baseline_lr
    drift = self.agent.drive_baseline[d] - self._initial_baseline.get(d, 0.5)
    pull_back = -drift * self.elasticity
    self.agent.drive_baseline[d] = max(0.1, min(0.95,
        self.agent.drive_baseline[d] + shift + pull_back
    ))
```

---

## 三、核心算法

### 3.1 三个力的叠加

基线演化由三个力共同决定：

```
new_baseline = old_baseline + shift + pull_back
```

**1. Shift（环境驱动漂移）**：`frustration_delta[d] × baseline_lr`
- frustration_delta > 0（挫败增加）→ shift > 0 → baseline 上升（更渴望）
- frustration_delta < 0（挫败减少）→ shift < 0 → baseline 下降（不那么渴望了）
- 幅度由 `baseline_lr` 控制（学习率，默认 0.01）

**2. Pull Back（弹性拉回）**：`-drift × elasticity`
- `drift = current_baseline - initial_baseline`（当前偏离初始值的程度）
- 如果 drift > 0（baseline 高于初始值）→ pull_back < 0 → 向初始值拉回
- 如果 drift < 0（baseline 低于初始值）→ pull_back > 0 → 向初始值拉回
- 幅度由 `elasticity` 控制（弹性系数，默认 0.05）

**3. Clip（边界限制）**：`max(0.1, min(0.95, ...))`
- 防止基线超出 [0.1, 0.95] 范围
- 保留 0.05 的 margin，避免触及边界

### 3.2 物理类比

想象一个弹簧系统：

```
        初始基线 (initial_baseline)
             ↑
             │  ←── 弹簧力 (elasticity)
             │
        当前基线 ───→ 环境推力 (frustration_delta × baseline_lr)
```

- 环境推力让基线偏离初始位置
- 弹簧力不断把基线拉回初始位置
- 两者的动态平衡决定了长期的性格漂移范围

---

## 四、详细执行流程

### 4.1 输入

```python
frustration_delta: dict   # 来自 Step 2 (Critic)
self.agent.drive_baseline: dict  # 当前基线
self._initial_baseline: dict     # 初始基线（snapshot from SOUL.md）
self.baseline_lr: float = 0.01   # 学习率
self.elasticity: float = 0.05    # 弹性系数
```

### 4.2 逐驱动计算

以 `connection` 为例，Luna 的初始 baseline = 0.75：

**第 10 轮**：`frustration_delta['connection'] = +0.3`（用户有点冷淡）

```python
shift = 0.3 × 0.01 = +0.003        # 轻微上升
drift = 0.75 - 0.75 = 0.0          # 还没偏离
pull_back = -0.0 × 0.05 = 0.0
new_baseline = 0.75 + 0.003 + 0.0 = 0.753
```

**第 50 轮**：baseline 已经被推到了 0.82
`frustration_delta['connection'] = +0.5`（用户很冷淡）

```python
shift = 0.5 × 0.01 = +0.005
drift = 0.82 - 0.75 = +0.07
pull_back = -0.07 × 0.05 = -0.0035
new_baseline = 0.82 + 0.005 - 0.0035 = 0.8215
```

**注意**：虽然 frustration_delta 很大（+0.5），但弹性拉回力也在增大，净变化只有 +0.0015。基线不会无限漂移。

**第 100 轮后**：baseline 稳定在约 0.85

```python
# 达到稳态时：shift + pull_back ≈ 0
# frustration_delta × baseline_lr ≈ drift × elasticity
# 假设平均每轮 delta ≈ 0.2:
# 0.2 × 0.01 ≈ drift × 0.05
# drift ≈ 0.04
# 稳态 baseline ≈ 0.75 + 0.04 = 0.79
```

实际上由于 delta 有波动，基线会在稳态附近小幅震荡。

---

## 五、不同角色的演化差异

| 角色 | baseline_lr | elasticity | 性格含义 |
|---|---|---|---|
| Luna (ENFP) | 0.015 | 0.04 | 易受影响，但允许较多漂移 |
| Kai (ISTP) | 0.008 | 0.06 | 难改变，强拉回，性格稳定 |

**Luna 的演化**：
- 高 baseline_lr → 每轮变化更大
- 低 elasticity → 弹簧力弱 → 允许更多漂移
- 结果：Luna 会被用户的行为显著影响，可能从活泼变得安静

**Kai 的演化**：
- 低 baseline_lr → 每轮变化很小
- 高 elasticity → 弹簧力强 → 快速拉回
- 结果：Kai 始终保持冷静稳重的性格，不会轻易改变

---

## 六、与后续步骤的关系

```
Step 3.5 更新: agent.drive_baseline (5D)
    ↓
Step 5 (compute_signals): drive_state 包含 drive_baseline 的影响
    │   drive_state[d] = baseline[d] + frustration[d] × 0.15
    ↓
Step 10 (Hebbian learning): 间接影响（通过 drive_state → signals）
    ↓
下一轮 Step 1 (Time Metabolism): drive_baseline 影响长期的 frustration 累积速度
```

**注意**：drive_baseline 是"长期记忆"，它不会在这一轮的 signal 计算中直接体现（因为 drive_state 是 baseline + frustration，而 frustration 在这一轮还来不及被新 baseline 显著改变）。它的影响是**跨轮次**的：

- 更高的 connection baseline → 经过 Time Metabolism 后，connection frustration 累积更快 → 角色更频繁地感到孤独 → 更频繁地产生 proactive 消息

---

## 七、必要性论证

### 如果没有 Baseline Evolution：

1. **角色永不改变**：1000 轮对话后，角色的驱动基线仍然和第一天一样
2. **无适应性**：无法适应用户的沟通风格（用户冷淡，角色仍然热情主动）
3. **不真实**：人类的性格会随着长期互动而微调，静态基线缺乏这种真实感
4. **浪费 Hebbian Learning**：Hebbian Learning 改的是 W1/W2 权重（行为模式），但不改基线（核心需求）。两者需要配合：基线定义"想要什么"，权重定义"如何表达"

### 为什么需要 Elastic Pull Back？

无限制漂移的问题：
- Luna 的 play baseline 从 0.80 漂到 0.10 → Luna 变得严肃沉闷 → 这还是 Luna 吗？
- 用户希望角色"有成长"，但不希望角色"变成另一个人"

Elastic Pull Back 的作用：
- 允许局部漂移（适应用户的沟通风格）
- 防止全局漂移（保留角色的核心性格）
- `elasticity` 就是"性格稳定性"参数

---

## 八、总结

> Step 3.5 是角色的"性格演化"机制。它用环境推力（frustration_delta × lr）让基线随交互历史漂移，用弹性拉回力（-drift × elasticity）防止角色变成完全不同的人。这是"成长"与"一致性"的权衡：角色会适应你，但不会忘记自己是谁。Luna 被冷落久了会变得安静一些，但她内心深处仍然是那个活泼的 Luna。
