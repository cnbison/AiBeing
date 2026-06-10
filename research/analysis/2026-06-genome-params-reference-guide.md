---
date: 2026-06-10
topic: genome_seed 参数体系详解 — drive_baseline、engine_params 的设定方法与参考指南
scope: persona/loader.py, engine/genome/*.py, agent/chat_agent.py, skills/manage/persona_gen/SKILL.md
status: active
related: ARCHITECTURE.md, research/guides/persona-creation.md, 2026-06-genome-signal-llm-pipeline.md
---

> 完整梳理 AiBeing Genome 引擎中 `genome_seed` 包含的两类参数（`drive_baseline` 5D + `engine_params` 11D）的设定逻辑、推导规则、参考范围，以及与运行时随机种子 `seed` 的区别。

## 背景

用户在使用 AiBeing 创建 persona 时，需要填写 SOUL.md 中的 `genome_seed` 块。该块包含两类数值参数：
1. `drive_baseline`（5D 驱动基线）— 决定人格类型
2. `engine_params`（11 个物理常量）— 决定性格动力学

用户的核心疑问：
- 这些值是怎么来的？有参考指南吗？
- 需要人工逐一设定吗？
- 运行时还有一个 `seed` 整数参数，这和 SOUL.md 中的 `genome_seed` 是什么关系？

## 核心结论

| 问题 | 答案 |
|------|------|
| `engine_params` 有参考指南吗？ | **有**，完整的推导规则和参考值表位于 `skills/manage/persona_gen/SKILL.md` |
| 需要人工设定吗？ | **是**，但有系统化的推导方法（MBTI + bio 关键词 → 参数），不是拍脑袋 |
| 同一个 MBTI 可以差异化吗？ | **可以**，`engine_params` + `drive_baseline` 的组合 + 运行时 `seed` 共同决定唯一性格 |
| SOUL.md `genome_seed` vs 运行时 `seed` | **两个东西**。SOUL.md 中的 `genome_seed` 是一个配置块名；运行时 `seed` 是整数随机种子，决定神经网络初始权重 |

---

## 一、架构位置：这些参数在引擎中扮演什么角色？

```
SOUL.md (YAML frontmatter)
  └── genome_seed:
        ├── drive_baseline: {connection, novelty, expression, safety, play}
        └── engine_params: {baseline_lr, elasticity, hebbian_lr, ...}

PersonaLoader._load_one() ──→ Persona.drive_baseline / Persona.engine_params
                                    │
                                    ▼
ChatAgent.__init__(genome_seed=seed_int) ──→ Agent(seed=seed_int, engine_params=...)
                                    │           │
                                    │           └── 生成随机神经网络权重 W1/W2/b1/b2
                                    │
                                    └── self.agent.drive_baseline 被 persona.drive_baseline 覆盖
```

### 代码锚点

- `persona/loader.py:192-218` — 解析 SOUL.md `genome_seed` 块
- `agent/chat_agent.py:96-111` — 将 persona 参数注入 Agent 和 DriveMetabolism
- `engine/genome/genome_engine.py:197-221` — Agent 初始化，用 `seed` 生成随机权重
- `engine/genome/drive_metabolism.py:44-55` — DriveMetabolism 加载 `engine_params`

---

## 二、drive_baseline（5D）— 人格类型锚定

### 2.1 五个维度的含义

| Drive | 高值 | 低值 | MBTI 映射 | 语义 |
|-------|------|------|-----------|------|
| `connection` | 渴望联结 | 独来独往 | E↑ I↓ | 社交需求强度 |
| `novelty` | 追新求异 | 守旧务实 | N↑ S↓ | 好奇心 |
| `expression` | 表达情感 | 理性克制 | F↑ T↓ | 沟通冲动 |
| `safety` | 需要控制 | 随性而为 | J↑ P↓ | 安全感/秩序需求 |
| `play` | 爱玩爱闹 | 严肃认真 | P↑ J↓ | 玩闹/自发冲动 |

### 2.2 设定方法

**规则**：MBTI 提供大致方向，bio 提供微调依据。

**参考值**（来自 `SKILL.md:52-57`）：

| 角色 | MBTI | connection | novelty | expression | safety | play |
|------|------|-----------|---------|------------|--------|------|
| Luna | ENFP | 0.75 | 0.65 | 0.75 | 0.25 | 0.80 |
| Iris | INFP | 0.45 | 0.55 | 0.60 | 0.65 | 0.40 |
| Vivian | INTJ | — | — | 0.40 | — | 0.30 |
| Kai | ISTP | — | 0.40 | — | — | — |

**关键原则**（`SKILL.md:58`）：
> "不是机械映射，要结合 bio 微调。例如同为 ENFP，一个活泼女孩 play=0.80，一个成熟创业者 play=0.60。"

---

## 三、engine_params（11D）— 性格动力学物理常量

### 3.1 参数完整表

| 参数 | 范围 | 默认值 | 作用对象 | 含义 | MBTI 影响方向 |
|------|------|--------|---------|------|---------------|
| `baseline_lr` | 0.006–0.015 | 0.01 | ChatAgent | 驱动基线适应速度 | P↑快，J↓慢 |
| `elasticity` | 0.03–0.08 | 0.05 | ChatAgent | 基线回弹强度（弹性系数） | J↑强回弹，P↓弱 |
| `hebbian_lr` | 0.012–0.025 | 0.02 | Agent | 神经网络可塑性 | 外向/开放↑ |
| `phase_threshold` | 1.5–3.5 | 2.0 | Agent | 相变触发阈值（多大挫败才性格突变） | J↑高稳定，P↓易爆发 |
| `connection_hunger_k` | 0.06–0.15 | 0.15 | DriveMetabolism | 孤独积累速度/小时 | E↑更快孤独 |
| `novelty_hunger_k` | 0.05–0.15 | 0.05 | DriveMetabolism | 无聊积累速度/小时 | N↑更快无聊 |
| `frustration_decay` | 0.05–0.12 | 0.08 | DriveMetabolism | 挫败消退速度/小时 | 乐观↑快消退 |
| `hawking_gamma` | 0.0005–0.002 | 0.001 | StyleMemory | 记忆衰减率 | 感性↓记得久 |
| `crystal_threshold` | 0.40–0.55 | 0.45 | PromptBuilder | 结晶门槛（多好的体验才固化记忆） | 细腻↓更多结晶 |
| `temp_coeff` | 0.05–0.15 | 0.12 | DriveMetabolism | 情绪波动系数 | F↑高波动，T↓冷 |
| `temp_floor` | 0.01–0.05 | 0.03 | DriveMetabolism | 最低噪声底板 | 活力↑总有波动 |

### 3.2 六个角色的参考值对比

```
              Iris(INFP)  Luna(ENFP)  Vivian(INTJ)  Kai(ISTP)  Kelly(ENTP)  Rex(ENTJ)
baseline_lr   0.01        0.015       0.008         0.008      0.015        0.006
elasticity    0.05        0.04        0.07          0.06       0.03         0.08
hebbian_lr    0.02        0.025       0.018         0.015      0.020        0.012
phase_thresh  2.5         1.5         3.0           3.0        2.0          3.5
conn_hunger   0.10        0.15        0.08          0.10       0.08         0.06
nov_hunger    0.08        0.08        0.07          0.05       0.15         0.06
frust_decay   0.10        0.12        0.06          0.08       0.10         0.05
hawking_g     0.0008      0.0012      0.0006        0.001      0.002        0.0005
crystal_th    0.45        0.40        0.55          0.50       0.40         0.55
temp_coeff    0.10        0.15        0.06          0.08       0.12         0.05
temp_floor    0.02        0.04        0.015         0.02       0.05         0.01
```

### 3.3 参数设定方法

**Step 1：MBTI 定方向**

从 MBTI 类型确定每个参数的大致区间。例如 ENFP → 高 play、高 temp_coeff、低 safety。

**Step 2：Bio 关键词微调**

| Bio 关键词 | 参数倾向 |
|-----------|---------|
| 安静、内敛、害羞 | `temp_coeff↓`, `temp_floor↓` |
| 热情、话多、社牛 | `connection_hunger_k↑`, `temp_coeff↑` |
| 记仇、敏感、细腻 | `hawking_gamma↓`, `crystal_threshold↓` |
| 大大咧咧、没心没肺 | `hawking_gamma↑`, `crystal_threshold↑` |
| 固执、有原则 | `elasticity↑`, `phase_threshold↑` |
| 随性、容易被影响 | `elasticity↓`, `baseline_lr↑` |

**Step 3：参数协同校验**

`SKILL.md:105-113` 提供了四组常见协同模式，用于校验参数组合是否合理：

- **孤独感 ↔ 联结基线**：`connection_hunger_k` 高 → 通常 `drive_baseline.connection` 也高
- **稳定性组**：`phase_threshold` 高 + `elasticity` 高 + `baseline_lr` 低 = 极稳定人格（如 Rex/ENTJ）
- **敏感组**：`crystal_threshold` 低 + `temp_coeff` 高 + `hawking_gamma` 低 = 细腻敏感（如 Iris/INFP）
- **自由组**：`baseline_lr` 高 + `elasticity` 低 + `phase_threshold` 低 = 容易改变、容易爆发（如 Luna/ENFP）

> 注意：这些不是硬约束。有意制造矛盾也是人格特征的一部分（如"表面冷静内心剧烈波动"）。

**Step 4：差异化检查**

> "至少让 3 个以上参数与'典型值'拉开 ≥20% 的距离。不要所有 ENFP 长得一样。"

示例 — 两个 ENFP：
- **Luna**（甜美少女）→ `play=0.80`, `temp_coeff=0.15`, `crystal_threshold=0.40` — 高波动、低门槛、像只蝴蝶
- **某创业者**（热情但务实）→ `play=0.55`, `temp_coeff=0.09`, `crystal_threshold=0.50` — 收着的热情、经历过社会的 ENFP

---

## 四、运行时 seed — 随机神经网络的"基因"

### 4.1 SOUL.md `genome_seed` vs 运行时 `seed`

这是最容易混淆的一点。**它们是不同层次的东西**：

| | SOUL.md `genome_seed` 块 | 运行时 `genome_seed`（整数） |
|---|--------------------------|------------------------------|
| **层级** | 配置层 | 引擎层 |
| **含义** | 一个 YAML 字典的**块名** | Agent 的**随机种子** |
| **内容** | `drive_baseline` + `engine_params` | 整数，如 42 |
| **决定什么** | 人格类型 + 动力学参数 | 神经网络初始权重矩阵 W1/W2/b1/b2 |
| **相同值 →** | 相同的人格类型和动力学 | **不同的性格**（因为随机性） |

### 4.2 代码中的实际关系

```python
# persona/loader.py:192-218
# 从 SOUL.md 解析出 drive_baseline 和 engine_params
genome_seed = meta.get("genome_seed", {})
drive_baseline = genome_seed.get("drive_baseline", {})
engine_params = genome_seed.get("engine_params", {})

# agent/chat_agent.py:96-111
# 运行时 seed 初始化 Agent 的随机权重
self.agent = Agent(seed=genome_seed, engine_params=engine_params)
# 然后用 SOUL.md 中的 drive_baseline 覆盖默认值
for d, v in persona.drive_baseline.items():
    self.agent.drive_baseline[d] = float(v)
    self.agent.drive_state[d] = float(v)
```

### 4.3 seed 的作用

`genome_engine.py:197-221` 中，`seed` 决定：
- `drive_baseline` 的默认值（如果 SOUL.md 没提供）
- `drive_accumulation_rate` 和 `drive_decay_rate`（每个 drive 不同）
- 神经网络权重 `W1`（24×25）、`b1`（24）、`W2`（8×24）、`b2`（8）
- 循环状态 `recurrent_state`（8D）的初始值

**两个 persona 可以有完全相同的 SOUL.md `genome_seed` 配置，但只要运行时 `seed` 不同，它们的神经网络结构就完全不同，聊出来的性格也完全不同。**

这就是为什么系统设计了 `pre_warm()` 机制（`genome_engine.py:155-182`）：

> "This is the key bootstrap that creates cross-seed personality diversity — without it, all agents start from the same neutral state and the LLM's default prior dominates."

---

## 五、总结：从"类型"到"个体"的三层构建

```
Layer 1: 人格类型（Type）
  └── drive_baseline 5D + MBTI 标签
      → "这是什么类型的人"（ENFP/INFP/INTJ...）

Layer 2: 性格动力学（Dynamics）
  └── engine_params 11D
      → "这个人的物理定律是什么"（多快孤独、多易爆发、多深记忆...）

Layer 3: 个体独特性（Individuality）
  └── 运行时 seed 生成的随机神经网络 + Hebbian 学习 + 用户隔离的记忆结晶
      → "这个具体的人是什么样的"（聊过的人才知道）
```

**同一 MBTI → 不同 engine_params → 不同的性格。**
**同一 MBTI + 同一 engine_params → 不同 seed → 不同的个体。**
**同一 persona + 不同用户 → 不同的学习轨迹 → 不同的关系。**

这就是 Genome 引擎的设计意图：不是用 prompt 描述"她是温柔的"，而是用一组物理参数让性格从计算中**涌现**出来。

---

## 参考文档

| 文档 | 路径 | 内容 |
|------|------|------|
| 人格生成完整指南 | `skills/manage/persona_gen/SKILL.md` | drive_baseline + engine_params 推导规则、参考值表、参数协同 |
| 人格创建实操指南 | `research/guides/persona-creation.md` | SOUL.md 格式、genesis seeds 校准、验证清单 |
| 架构约束 | `research/ARCHITECTURE.md` | engine_params 是唯一合法的调参入口，禁止直接修改引擎代码 |
| 基因组引擎 | `engine/genome/genome_engine.py` | Agent 类、随机网络、Hebbian 学习、DRIVES/SIGNALS 常量 |
| 驱动代谢 | `engine/genome/drive_metabolism.py` | 时间代谢方程、热力学噪声、物理常量默认值 |
| 风格记忆 | `engine/genome/style_memory.py` | KNN 检索、结晶化、霍金辐射记忆衰减 |
