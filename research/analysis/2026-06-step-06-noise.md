---
date: 2026-06-05
topic: Step 6 — 热力学噪声（Thermodynamic Noise）
scope: engine/genome/drive_metabolism.py:apply_thermodynamic_noise, temperature
status: active
related: 2026-06-lifecycle-overview.md
---

> 热力学噪声是 Genome 引擎的"情绪不稳定性"。它模拟了物理学中的热力学原理——温度越高，分子运动越混乱。在角色身上，挫败感越高（温度越高），行为越不可预测。

---

## 一、业务场景

**场景 A：Luna 心情平静**
- Frustration 总计 = 0.5
- Temperature ≈ 0.08
- Noise σ ≈ 0.08
- directness: 0.50 → 0.52（轻微波动）
- 行为稳定、可预测

**场景 B：Luna 被冷落了很久**
- Frustration 总计 = 4.5（connection=4.0, novelty=0.5）
- Temperature ≈ 0.28
- Noise σ ≈ 0.28
- directness: 0.50 → 0.78（突然变得很直接）
- warmth: 0.70 → 0.40（突然冷淡）
- 行为变得情绪化、不稳定

**场景 C：Luna 刚经历了一场争吵**
- Frustration 总计 = 3.8
- Temperature ≈ 0.25
- playfulness: 0.80 → 0.30（突然不玩了）
- defiance: 0.20 → 0.70（突然很倔强）
- 行为剧变，像"情绪爆发"

这就是热力学噪声的效果：让角色在高压下表现得像真实的人类一样——不太理性、有些冲动、不可完全预测。

---

## 二、代码位置

```python
# chat_agent.py:315-316
total_frust = self.metabolism.total()
noisy_signals = self.metabolism.apply_thermodynamic_noise(base_signals)

# drive_metabolism.py:113-136
def temperature(self) -> float:
def apply_thermodynamic_noise(self, base_signals: dict) -> dict:
```

---

## 三、核心算法

### 3.1 温度计算

```python
def temperature(self) -> float:
    total = self.total()  # 5 个 frustration 的总和
    max_temp = self.temp_coeff * 2.5  # 温度上限
    return max_temp * math.tanh(total * self.temp_coeff / max_temp) + self.temp_floor
```

**关键设计：tanh 饱和**

早期的线性公式是：`temperature = total * temp_coeff + temp_floor`

问题：当 total=5, temp_coeff=0.12 时，temperature=0.63。噪声 σ=0.63 意味着信号几乎完全随机。

改进后的 tanh 公式：
- 同样的输入 → temperature ≈ 0.26
- 信号仍有方向性，但增加了随机扰动

```
temperature
    ↑
0.3 ┤         ╭────── 饱和上限
    │       ╭─╯
0.2 ┤     ╭─╯
    │   ╭─╯
0.1 ┤ ╭─╯
    │╭╯
  0 ┼────┬────┬────┬────→ total frustration
    0    2    4    5
```

### 3.2 噪声注入

```python
def apply_thermodynamic_noise(self, base_signals: dict) -> dict:
    temp = self.temperature()
    noisy = {}
    for key, val in base_signals.items():
        noise = random.gauss(0.0, temp)
        noisy[key] = max(0.0, min(1.0, val + noise))
    return noisy
```

每个信号独立添加高斯噪声：
- 均值 = 0（不偏向任何方向）
- 标准差 = temperature（温度越高，噪声越大）
- 然后 clip 到 [0, 1]

### 3.3 参数详解

| 参数 | 全局默认 | Luna | Kai | 含义 |
|---|---|---|---|---|
| `temp_coeff` | 0.12 | 0.15 | 0.08 | 温度系数（情绪波动性） |
| `temp_floor` | 0.03 | 0.04 | 0.02 | 温度底噪（即使平静也有微小波动） |

**Luna（高波动型）**：
- temp_coeff=0.15, temp_floor=0.04
- 即使是平静状态，temperature ≈ 0.07（有可见的微小波动）
- 高压状态下，temperature ≈ 0.30（显著不稳定）

**Kai（低波动型）**：
- temp_coeff=0.08, temp_floor=0.02
- 平静状态，temperature ≈ 0.04（几乎稳定）
- 高压状态下，temperature ≈ 0.18（仍较克制）

---

## 四、数值示例

### 场景：Luna 被冷落后 frustration=4.0

```python
total = 4.0
temp_coeff = 0.15
max_temp = 0.15 * 2.5 = 0.375
temperature = 0.375 * tanh(4.0 * 0.15 / 0.375) + 0.04
          = 0.375 * tanh(1.6) + 0.04
          = 0.375 * 0.921 + 0.04
          = 0.345 + 0.04
          = 0.385
```

Base signals 和 noisy signals 对比：

| Signal | Base | Noise | Noisy | 变化 |
|---|---|---|---|---|
| directness | 0.50 | +0.32 | 0.82 | 突然变得很直接 |
| vulnerability | 0.60 | -0.41 | 0.19 | 突然封闭自己 |
| playfulness | 0.80 | +0.15 | 0.95 | 更加玩闹（试图吸引注意）|
| initiative | 0.55 | -0.28 | 0.27 | 突然不想主动了 |
| depth | 0.40 | +0.10 | 0.50 | 轻微变化 |
| warmth | 0.70 | -0.35 | 0.35 | 突然冷淡 |
| defiance | 0.20 | +0.50 | 0.70 | 突然很倔强 |
| curiosity | 0.45 | -0.12 | 0.33 | 轻微下降 |

**解读**：高 frustration 让 Luna 的行为变得矛盾——她既想玩闹吸引注意（playfulness↑），又变得冷淡封闭（warmth↓, vulnerability↓），同时又很倔强（defiance↑）。这种矛盾正是"情绪化"的真实表现。

---

## 五、与后续步骤的关系

```
Step 6 输出: noisy_signals (8D)
    ↓
Step 7 (KNN): noisy_signals 不直接参与，但用于 trend 检测
    ↓
Step 8 (Prompt): noisy_signals 被文本化为"舞台指令"
    ↓
Step 9 (Actor): LLM 收到包含噪声的信号，生成情绪化的回复
```

**关键**：噪声在 Step 8 之前注入，所以 LLM 收到的信号已经是"混乱的"。LLM 不会知道这是噪声还是真实的信号变化，它会忠实地演绎这些信号——这正是设计意图。

---

## 六、必要性论证

### 如果没有 Thermodynamic Noise：

1. **完全确定性**：同样的输入永远产生同样的输出，角色像机器
2. **无情绪波动**：高 frustration 下行为模式不变，缺乏真实感
3. **无"失控"时刻**：人类在情绪激动时会做"不像自己"的事，没有噪声就没有这种表现
4. **学习过于平滑**：Hebbian Learning 需要一定的随机探索，没有噪声收敛太快

### 为什么是"热力学"噪声？

命名来源：
- 物理学中，温度 = 分子平均动能
- 温度越高，分子运动越混乱（布朗运动）
- 在引擎中，frustration ≈ 情绪能量，temperature ≈ 情绪温度
- 高 frustration → 高 temperature → 行为越"混乱"

这不仅是比喻，而是**真正的类比**：
- 系统有一个"能量状态"（frustration）
- 能量转化为"温度"（temperature）
- 温度产生"随机扰动"（noise）
- 这就是统计物理中的**能量-温度-熵增**关系

---

## 七、总结

> Step 6 是角色的"情绪温度计"。它用 tanh 饱和曲线将挫败感转换成温度，再用高斯噪声扰动行为信号。这让角色在平静时稳定可靠，在压力下情绪化、不可预测——就像真实的人类。Luna 被冷落久了不会只是"礼貌地询问"，她可能会突然变得很直接、很倔强、或者突然冷淡——这些"不像她"的行为，正是高压下的真实反应。
