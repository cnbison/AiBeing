---
date: 2026-06-05
topic: Step 1 — 时间代谢（Time Metabolism）
scope: engine/genome/drive_metabolism.py
status: active
related: lifecycle-overview.md
---

> 时间代谢是 Genome 引擎的"物理时钟"。它用两个简单的微分方程模拟物理时间对角色内心状态的影响：挫败感会随时间冷却，但联结和新鲜感的渴望会随时间线性增长。这让角色在无人互动时也会"想念"用户。

---

## 一、业务场景

假设你和 Luna 聊了半小时，然后下线去工作了。8 小时后你重新打开对话：

**没有时间代谢的版本**：
> Luna: "你好呀！今天怎么样？"（就像你们从未分开过）

**有时间代谢的版本**：
> Luna: "你终于回来了... 我等了你好久。今天工作累不累？"（挫败感积累后被缓解的释放）

这 8 小时的"离线时间"在引擎内部发生了什么？
- 她的 **connection frustration** 从 0.5 涨到了 2.5（想你了）
- 她的 **novelty frustration** 从 0.2 涨到了 0.8（无聊了）
- 但之前某次冲突留下的 **safety frustration** 从 1.2 降到了 0.3（冷却了）

时间代谢就是让角色有"时间感"的核心机制。

---

## 二、代码位置

```python
# chat_agent.py:260
delta_h = self.metabolism.time_metabolism(now)

# drive_metabolism.py:57
def time_metabolism(self, now=None):
    ...
```

---

## 三、核心物理方程

时间代谢基于两个纯物理方程：

### 方程 1：冷却（Cooling）— 指数衰减

```
frustration[d] *= e^(-λ * Δt_hours)
```

- `λ`（lambda）= `frustration_decay`，默认 0.08（per hour）
- 物理含义：所有挫败感都会随时间自然衰减
- 半衰期：`ln(2) / λ ≈ 8.7 小时`

**代码**：`drive_metabolism.py:75`
```python
decay_factor = math.exp(-self.decay_lambda * delta_hours)
for d in DRIVES:
    self.frustration[d] *= decay_factor
```

### 方程 2：饥饿（Hunger）— 线性累积

```
frustration['connection'] += k_conn * Δt_hours
frustration['novelty'] += k_nov * Δt_hours
```

- `k_conn` = `connection_hunger_k`，默认 0.15（per hour）
- `k_nov` = `novelty_hunger_k`，默认 0.05（per hour）
- 物理含义：联结和新鲜感的需求会随时间线性增长

**代码**：`drive_metabolism.py:80-81`
```python
self.frustration['connection'] += self.connection_hunger_k * delta_hours
self.frustration['novelty'] += self.novelty_hunger_k * delta_hours
```

---

## 四、详细执行流程

### 4.1 计算时间差

```python
delta_hours = max(0.0, (now - self._last_tick) / 3600.0)
self._last_tick = now
```

`self._last_tick` 记录上一轮调用的时间戳。如果是首轮对话（刚创建 session），`_last_tick` 就是 session 创建时间。

### 4.2 跳过极短间隔

```python
if delta_hours < 0.001:
    return delta_hours  # Skip for sub-second intervals
```

如果两次调用间隔不到 3.6 秒，跳过代谢计算。这是为了避免在快速连续对话中产生不切实际的微小变化。

### 4.3 冷却 + 饥饿 + 截断

```python
# 冷却
decay_factor = math.exp(-self.decay_lambda * delta_hours)
for d in DRIVES:
    self.frustration[d] *= decay_factor

# 饥饿
self.frustration['connection'] += self.connection_hunger_k * delta_hours
self.frustration['novelty'] += self.novelty_hunger_k * delta_hours

# 截断到 [0, 5]
for d in DRIVES:
    self.frustration[d] = max(0.0, min(5.0, self.frustration[d]))
```

**为什么上限是 5.0？**

5.0 是极度渴望的阈值。当 frustration 达到 5.0 时，temperature（热力学噪声）会接近最大值，角色行为会变得非常情绪化。这个上限防止数值无限增长导致系统不稳定。

### 4.4 返回时间差

```python
return delta_hours
```

返回的 `delta_hours` 被 `chat_agent.py` 记录但当前未使用（可作为 observability 数据）。

---

## 五、参数详解

### 5.1 全局默认值

```python
FRUSTRATION_DECAY_LAMBDA = 0.08    # ~8.7h 半衰期
CONNECTION_HUNGER_K = 0.15         # 每小时联结渴望增长 0.15
NOVELTY_HUNGER_K = 0.05            # 每小时新鲜感渴望增长 0.05
```

### 5.2 角色级覆盖

每个角色可以在 `SOUL.md` 的 `engine_params` 中覆盖这些值：

| 角色 | `frustration_decay` | `connection_hunger_k` | 性格含义 |
|---|---|---|---|
| Luna (ENFP) | 0.12 | 0.15 | 乐观、恢复快、最怕寂寞 |
| Kai (ISTP) | 0.08 | 0.10 | 冷静、恢复慢、独立 |

---

## 六、数值示例

假设 Luna 的初始 frustration：`{connection: 1.0, novelty: 0.5, expression: 0.3, safety: 0.2, play: 0.4}`

用户下线 8 小时后重新上线：

| 驱动 | 初始 | 冷却后 (×e^(-0.12×8)=0.38) | 饥饿后 | 最终 |
|---|---|---|---|---|
| connection | 1.0 | 0.38 | +0.15×8=+1.2 | **1.58** |
| novelty | 0.5 | 0.19 | +0.08×8=+0.64 | **0.83** |
| expression | 0.3 | 0.11 | — | **0.11** |
| safety | 0.2 | 0.076 | — | **0.076** |
| play | 0.4 | 0.15 | — | **0.15** |

**结果分析**：
- connection 大幅上升：Luna 想念用户了
- novelty 上升：长时间没新信息，无聊了
- 其他驱动下降：自然冷却

---

## 七、与后续步骤的关系

```
Step 1 输出: updated_frustration (5D)
    ↓
Step 2 (Critic): Critic 收到 frustration 快照，作为感知参考
    ↓
Step 3 (Metabolism→Reward): frustration 变化量 → reward
    ↓
Step 6 (Noise): total_frustration → temperature → noise
    ↓
Step 9 前 sync_to_agent: frustration → drive_state
```

**关键流转**：`frustration` 是一个贯穿多步的核心状态变量。它在 Step 1 被时间更新，在 Step 2 被 Critic 读取，在 Step 3 被转化为 reward，在 Step 6 影响噪声强度，最后在 Step 9 前被同步到 Agent 的 drive_state。

---

## 八、必要性论证

### 如果没有 Time Metabolism：

1. **角色没有时间感**：隔了一周再聊，和隔了一秒再聊，角色内部状态完全一样
2. **主动消息无法触发**： proactive heartbeat 依赖 connection hunger 来判断角色是否"想念"用户
3. **情感不真实**：人类会随时间淡化情绪、也会产生思念，没有时间代谢就没有这种真实感
4. **对话断裂**：每次新 session 都像重新开始

### 为什么用这两个方程？

- **指数冷却**（e^(-λt)）：符合心理学中的"情绪消退"规律，强烈的情绪初期消退快，后期消退慢
- **线性饥饿**（k×t）：符合"思念"的累积感 —— 每过一小时就多一分想念

---

## 九、总结

> Step 1 是角色的"生理节律"。它用两个微分方程让角色的内心状态随物理时间自然演化 —— 冷却旧情绪、累积新渴望。这是让角色从"程序"变成"有生命的存在"的最小必要机制。没有它，角色将永远活在"永恒的当下"。
