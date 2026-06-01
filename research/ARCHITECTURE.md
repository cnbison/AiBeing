# AiBeing 架构设计契约

> 版本: Genome v10 Hybrid | 更新日期: 2026-06-01
>
> 本文档是改代码时的**设计宪法**。它回答：模块边界在哪里？什么能改、什么不能改？关键决策为什么这样定？
>
> 与 `research/project_analysis.md` 的区别：那是"现状分析"，这是"设计契约"。

---

## 一、架构概述

AiBeing 采用**分层洋葱架构**，核心人格引擎在内层，外层依次是记忆层、技能层、Agent 编排层、网关层。

```
┌─────────────────────────────────────────────────────────────────┐
│  客户端层                                                        │
│  Web / macOS / 微信适配器                                         │
├─────────────────────────────────────────────────────────────────┤
│  网关层 (main.py)                                                │
│  FastAPI + WebSocket + REST + 静态文件                            │
├─────────────────────────────────────────────────────────────────┤
│  Agent 编排层 (agent/)                                           │
│  ChatAgent ── 12 步生命周期 orchestrator                          │
│  ├─ PromptBuilderMixin                                          │
│  ├─ EverMemosMixin                                              │
│  ├─ ModalityRetryMixin                                          │
│  └─ ProactiveMixin                                              │
├─────────────────────────────────────────────────────────────────┤
│  技能引擎层 (agent/skills/ + skills/)                             │
│  TaskSkillEngine (ReAct 循环) ── 天气/搜索等用户请求               │
│  ModalitySkillEngine ── 自拍/语音/沉默等人格内敛行为               │
├─────────────────────────────────────────────────────────────────┤
│  人格引擎层 (engine/genome/)                                     │
│  ├─ Agent: 随机神经网络 (25D→24D→8D) + Hebbian 学习               │
│  ├─ DriveMetabolism: 时间感知的驱力代谢                           │
│  ├─ Critic: LLM-based 情感感知器 (8D+5D+3D+5D)                   │
│  └─ StyleMemory: KNN 风格记忆 + Hawking 辐射                      │
├─────────────────────────────────────────────────────────────────┤
│  记忆层                                                          │
│  ├─ 风格记忆 (SQLite KNN) ── Session 内行为模式                    │
│  ├─ 本地事实 (SQLite FTS5) ── 用户偏好/近期历史                    │
│  └─ 长期记忆 (EverMemOS HTTP API) ── 跨会话持久化                  │
├─────────────────────────────────────────────────────────────────┤
│  Provider 层 (providers/)                                        │
│  LLM / TTS / Image / Memory 适配器                                │
└─────────────────────────────────────────────────────────────────┘
```

**核心设计原则**: 人格不是 prompt 描述的，而是从 **驱力 × 神经网络 × 经历** 的相互作用中涌现的。

---

## 二、不可变约束（红线）

以下约束在**任何魔改中都必须遵守**。违反它们会破坏引擎的核心正确性。

### 2.1 人格涌现约束

- **[C-1] 人格不写在 prompt 里**: `single_prompt` 中只能有身份锚点（名字/年龄/性别）和行为信号注入。不能把"她很温柔""她喜欢猫"写进 system prompt。这些应该通过 `genome_seed.drive_baseline` 和 `SOUL.md` 的 personality sections 影响神经网络权重。
- **[C-2] Critic 是唯一的 LLM 人格感知入口**: 用户输入的语义解析（情绪、亲密度、冲突度等）只能由 `critic_sense()` 完成，不能在其他地方偷偷做情感判断。
- **[C-3] Drive baseline 漂移必须有弹性回弹**: `elasticity` 参数确保 baseline 不会无限漂移远离角色原型。修改此机制时需保持 `spring force` 的存在。

### 2.2 并发安全约束

- **[C-4] `_turn_lock` 不可绕过**: `chat()`、`chat_stream()`、`proactive_tick()` 必须由同一个 `asyncio.Lock` 串行化。这是防止并发修改 Agent 状态（神经权重、驱力、metabolism）的唯一保障。
- **[C-5] CAS 状态保存**: `StateStore.save_state()` 使用 version-guarded 写入。任何新增的状态持久化字段都必须参与 version 校验。

### 2.3 生命周期约束

- **[C-6] 12 步顺序不可随意增删**: 步骤之间存在数据依赖（如 Step 2 Critic 输出 → Step 2.5 EMA → Step 3 metabolism reward）。增删步骤必须重新验证全链路数据流。
- **[C-7] Single-pass Actor 不可拆分**: monologue、reply、modality 必须在一次 LLM 调用中生成。拆成多轮会破坏"内心独白影响语言表达"的涌现机制。
- **[C-8] 记忆存储必须是 fire-and-forget**: EverMemOS `store_turn()` 和 `search_relevant_memories()` 必须通过 `asyncio.create_task()` 启动，不可 `await` 阻塞对话流。

### 2.4 扩展约束

- **[C-9] 功能逻辑不进引擎**: 新功能必须通过 Skill Engine 实现，不可直接修改 `genome_engine.py` 或 `drive_metabolism.py`。
- **[C-10] Provider 遵循适配器模式**: 新增 LLM/TTS 提供商时，必须继承基类（`LLMProviderBase` / `TTSProviderBase`），实现统一接口，注册到 `providers/registry.py`。

---

## 三、模块边界与职责

### 3.1 engine/genome/ — 人格内核（改动需最谨慎）

| 文件 | 职责 | 扩展方式 |
|------|------|---------|
| `genome_engine.py` | Agent 类：随机 NN 初始化、信号计算、Hebbian 学习、phase transition | **冻结**。参数调优通过 `engine_params`，不直接改代码。 |
| `drive_metabolism.py` | DriveMetabolism：时间代谢、frustration 冷却/饥饿、热力学噪声 | **冻结**。参数通过 `SOUL.md` `engine_params` 覆盖。 |
| `critic.py` | `critic_sense()`: 用户输入 → 8D context + 5D frustration delta + 3D relationship delta + 5D drive satisfaction | 可扩展：新增感知维度需同步修改 `CONTEXT_FEATURES` 和 prompt 模板。 |
| `style_memory.py` | ContinuousStyleMemory：KNN 检索、gravitational mass、Hawking 辐射、Crystallization | 可调参：`top_k`、decay rate、mass threshold。 |

### 3.2 agent/ — 编排层（改动最频繁）

| 文件 | 职责 | 扩展方式 |
|------|------|---------|
| `chat_agent.py` | ChatAgent 类：12 步生命周期 orchestrator，`_turn_lock` 持有者 | 可扩展：新增生命周期步骤需在 `_chat_inner()` 中插入，并验证数据依赖。 |
| `prompt_builder.py` | PromptBuilderMixin：single-pass prompt 组装（identity + signals + trend + time + memory injection） | 可扩展：新增 prompt 注入段需保持单轮结构。 |
| `evermemos_mixin.py` | EverMemOSMixin：session 上下文加载、关系 EMA、异步存储/搜索 | 可扩展：新增记忆源需遵循 fire-and-forget 模式。 |
| `proactive.py` | ProactiveMixin：驱力 impulse 检测、自主消息生成 | 可扩展：新增 drive 触发条件需与 `DRIVES` 列表对齐。 |
| `modality_retry.py` | ModalityRetryMixin：模态执行失败时的回退逻辑 | 可扩展：新增 modality 需注册回退策略。 |

### 3.3 providers/ — 适配器层（最自由的扩展区域）

| 目录 | 职责 | 扩展方式 |
|------|------|---------|
| `llm/` | 8 家 LLM 提供商的统一适配 | **自由扩展**。新增 provider 继承 `base.py`，注册到 `client.py` 和 `api.yaml`。 |
| `media/tts_engine.py` | TTS 引擎调度 | **自由扩展**。新增 TTS provider 继承 `speech/tts/base.py`。 |
| `image/` | 图像生成 | **自由扩展**。当前仅 Gemini Imagen。 |
| `memory/evermemos/` | 长期记忆客户端 | 可扩展：新增记忆后端需实现相同接口（`store_turn`, `search`, `load_session_context`）。 |

### 3.4 skills/ — 技能定义（最自由的扩展区域）

| 目录 | 职责 | 扩展方式 |
|------|------|---------|
| `task/` | 用户请求的技能（天气、搜索等） | **自由扩展**。每个 skill 一个目录，包含 `SKILL.md`（YAML frontmatter + 实现）。 |
| `modality/` | 人格内敛的模态行为（自拍、语音、沉默、拆分消息） | **自由扩展**。新增 modality 需注册到 `agent/skills/modality_skill_engine.py`。 |
| `manage/` | 管理类技能（角色生成等） | **自由扩展**。 |

---

## 四、数据流总图

### 4.1 单轮对话完整数据流

```
用户输入
  │
  ▼
Step -1: Task Skill ReAct Loop ─────────────────────┐
  │  (user_message 可能被 enrich)                     │
  ▼                                                  │
Step 0: 全局状态更新                                  │
  │  _turn_count++, interaction_cadence EMA           │
  ▼                                                  │
Step 0: EverMemOS Session Context ──────────────────┤
  │  relationship_prior (4D)                          │ 首次加载
  ▼                                                  │
Step 1: Time Metabolism ────────────────────────────┤
  │  delta_hours → frustration cooling / hunger       │
  ▼                                                  │
Step 2: Critic Perception ──────────────────────────┤
  │  LLM → 8D context + 5D frustration_delta          │
  │         + 3D relationship_delta + 5D satisfaction │
  ▼                                                  │
Step 2.5: Relationship EMA ─────────────────────────┤
  │  posterior = clip(prior + delta)                  │
  │  ema = alpha * posterior + (1-alpha) * prior      │
  ▼                                                  │
Step 3: LLM Metabolism → Reward ────────────────────┤
  │  reward = apply_llm_delta(frustration_delta)      │
  ▼                                                  │
Step 3.5: Drive Baseline Evolution ─────────────────┤
  │  elastic baseline shift + pull_back               │
  ▼                                                  │
Step 4: Crystallization Gate ───────────────────────┤
  │  if should_crystallize(reward, context):          │
  │      style_memory.crystallize(last_action)        │
  ▼                                                  │
Step 5: Compute Signals ────────────────────────────┤
  │  agent.compute_signals(context) → 8D base_signals │
  ▼                                                  │
Step 6: Thermodynamic Noise ────────────────────────┤
  │  noisy_signals = base_signals + noise(total_frust)│
  ▼                                                  │
Step 7: KNN Retrieval ──────────────────────────────┤
  │  style_memory.build_few_shot_prompt(context)      │
  ▼                                                  │
Step 8: Build Single-Pass Prompt ───────────────────┤
  │  identity + signals + trend + time                │
  ▼                                                  │
Step 8.5: Memory Injection ─────────────────────────┤
  │  EverMemOS search results + user_profile          │
  │  + episode_summary + foresight_text               │
  ▼                                                  │
Step 9: Single-Pass LLM Call ───────────────────────┘
  │  system prompt + history + user_message
  │  → monologue + reply + modality
  ▼
Step 9b: Modality Skill Execution
  │  selfie / voice / silence / split
  ▼
Step 10: Hebbian Learning
  │  agent.step(context, reward) → weight update
  ▼
Step 11: EverMemOS Store Turn (async fire-and-forget)
  │  asyncio.create_task(store_turn(...))
  ▼
Step 12: Fire Async Search (for NEXT turn)
  │  asyncio.create_task(search_relevant_memories(...))
  ▼
返回 reply 给用户
```

### 4.2 关键数据结构

#### Agent State（每轮可变）
```python
{
    "drive_state":       {d: float for d in DRIVES},          # 5D 当前驱力
    "drive_baseline":    {d: float for d in DRIVES},          # 5D 基线（可漂移）
    "frustration":       {d: float for d in DRIVES},          # 5D 挫败值
    "recurrent_state":   [float] * 8,                         # 8D 内部"心情"
    "W1":                [[float]] * 24 * 13,                  # 24D hidden × 13D input
    "W2":                [[float]] * 8 * 24,                   # 8D signal × 24D hidden
    "interaction_count": int,
    "signal_history":    [{signal: float}],                   # 最近 100-200 轮信号
}
```

#### Critic Output（每轮新生成）
```python
{
    "context": {           # 8D + 4D = 12D
        "user_emotion": float,       # -1 ~ 1
        "topic_intimacy": float,     #  0 ~ 1
        "time_of_day": float,        #  0 ~ 1
        "conversation_depth": float, #  0 ~ 1
        "user_engagement": float,    #  0 ~ 1
        "conflict_level": float,     #  0 ~ 1
        "novelty_level": float,      #  0 ~ 1
        "user_vulnerability": float, #  0 ~ 1
        # + EverMemOS relationship 4D
        "relationship_depth": float,
        "emotional_valence": float,
        "trust_level": float,
        "pending_foresight": float,
    },
    "frustration_delta": {d: float for d in DRIVES},  # 5D 变化量
    "relationship_delta": {
        "relationship_delta": float,
        "emotional_valence": float,
        "trust_delta": float,
    },
    "drive_satisfaction": {d: float for d in DRIVES}, # 5D 满足度
}
```

#### Single-Pass Actor Output
```python
{
    "monologue": str,   # 内心独白（不返回给用户，用于 Crystallization）
    "reply": str,       # 对用户的回复
    "modality": str,    # 文字 / 自拍 / 语音 / 沉默 / 拆分
}
```

---

## 五、架构决策记录（ADR）

### ADR-1: 随机神经网络 + Hebbian 学习，而非 RLHF 或 Prompt 工程

**问题**: 如何让每个角色有独特的、稳定的人格？

**考虑的方案**:
- A. Prompt 工程：在 system prompt 中描述性格（"她很温柔"）。简单但静态、无法演化。
- B. RLHF：收集对话数据训练模型。需要大量数据和算力，且角色间难以隔离。
- C. 随机神经网络 + Hebbian：每个角色有独立的随机种子，神经网络权重从随机初始化开始，通过 Hebbian 规则根据交互更新。

**决策**: 选择 C。

**理由**:
- 每个角色的 `genome_seed` 产生独特的神经网络权重，天然隔离。
- Hebbian 学习（"一起激活的神经元连在一起"）不需要标注数据，实时学习。
- 人格从交互中涌现，而非预设，更符合"生命体"的设计哲学。
- 计算开销极低（矩阵乘法），可在 CPU 上实时运行。

**代价**:
- 不可解释性：无法直接说"她为什么温柔"，只能看权重分布。
- 调试困难：需要模拟场景预热（`simulate_conversation` 60 步）才能看出个性差异。

### ADR-2: Single-Pass Actor，而非 Chain-of-Thought 或多轮

**问题**: 如何让 AI 有"内心独白"同时保持低延迟？

**考虑的方案**:
- A. 多轮 CoT：先调用 LLM 生成内心独白，再调用生成回复。延迟翻倍。
- B. 隐式 CoT：在 prompt 中要求"先想后说"，但只输出回复。丢失独白数据。
- C. Single-Pass：一次调用要求输出 `monologue | reply | modality` 三段式。

**决策**: 选择 C。

**理由**:
- 延迟最优：一次 LLM 调用完成所有工作。
- 独白数据可用于 Crystallization（沉淀风格记忆）。
- 三段式输出可通过 `extract_reply()` 可靠解析。

**代价**:
- 对 LLM 的 instruction following 能力要求较高。
- prompt 模板需要精心设计以确保三段式格式稳定。

### ADR-3: SQLite 作为本地存储，而非 PostgreSQL 或 Redis

**问题**: 本地状态、记忆、日志用什么存储？

**决策**: SQLite（aiosqlite 异步访问）。

**理由**:
- 零运维：单文件，备份就是一个 `cp`。
- Python 原生支持，无需额外服务。
- 并发量极低（单用户单会话），SQLite 的写锁不是瓶颈。
- FTS5 支持全文搜索，KNN 通过向量缓存实现。

**代价**:
- 不适合高并发多用户场景（当前设计目标不是 SaaS）。
- 向量检索性能不如专用向量数据库（通过 style_memory 的缓存和 KNN 缓解）。

### ADR-4: asyncio.Lock 串行化对话，而非队列或状态机

**问题**: 如何处理同一用户的并发消息？

**决策**: 每个 ChatAgent 实例持有一个 `asyncio.Lock`，`chat()`/`chat_stream()`/`proactive_tick()` 竞争同一把锁。

**理由**:
- Agent 状态（神经权重、驱力、metabolism）不是线程安全的，串行是最简单的正确方案。
- 单用户场景下，并发消息本身就是异常状态（用户不可能同时发两条消息）。
- 比队列更简单：不需要状态机管理"排队中""处理中""已完成"。

**代价**:
- 如果用户消息到达频率超过处理速度，后续消息会阻塞等待（但这种情况在正常交互中不会发生）。

### ADR-5: Skill 双引擎分离（Task vs Modality）

**问题**: 用户请求的技能（查天气）和人格内敛的行为（发自拍）如何统一管理？

**决策**: 分离为两个引擎：
- TaskSkillEngine：ReAct 循环，在 Step -1 执行，输出观测数据 enrich 用户输入。
- ModalitySkillEngine：在 Step 9b 执行，根据 Actor 输出的 modality 触发具体行为。

**理由**:
- 职责清晰：Task 是"工具调用"，Modality 是"表达方式"。
- 执行时机不同：Task 在人格引擎之前，Modality 在人格引擎之后。
- 失败处理不同：Task 失败可降级为纯人格回复，Modality 失败有 retry 机制。

---

## 六、扩展点

### 6.1 新增 LLM Provider

1. 在 `providers/llm/` 创建 `{provider}.py`，继承 `LLMProviderBase`
2. 实现 `async def chat(messages, **kwargs) -> ChatMessage`
3. 在 `providers/llm/client.py` 中注册映射
4. 在 `providers/api.yaml` 中添加配置模板

### 6.2 新增 Skill

**Task Skill**:
1. 在 `skills/task/{skill_name}/` 创建目录
2. 编写 `SKILL.md`（YAML frontmatter：`trigger: tool`，`description`，`parameters`）
3. 在 `agent/skills/tools/` 中实现工具函数，注册到 `ToolRegistry`

**Modality Skill**:
1. 在 `skills/modality/{skill_name}/` 创建目录
2. 编写 `SKILL.md`（YAML frontmatter：`trigger: modality`）
3. 在 `agent/skills/modality_skill_engine.py` 中注册 handler

### 6.3 新增感知维度（Critic）

1. 在 `engine/genome/genome_engine.py` 的 `CONTEXT_FEATURES` 列表末尾新增维度名
2. 修改 `engine/genome/critic.py` 的 prompt 模板，让 LLM 输出新增维度
3. 在 `agent/chat_agent.py` 中确认新增维度被正确传入 `agent.compute_signals(context)`
4. **注意**: `INPUT_SIZE` = `N_DRIVES + N_CONTEXT + RECURRENT_SIZE` 会自动增长，`Agent.__init__` 中的 `W1` 维度需兼容（`N_CONTEXT` 增加 → `INPUT_SIZE` 增加 → `W1` 列数增加）。但由于随机初始化，旧状态的 `W1` 加载时需要处理维度变化。

### 6.4 新增长期记忆后端

1. 创建 `providers/memory/{backend}/` 目录
2. 实现与 `EverMemOSClient` 相同的公共接口：
   - `async def store_turn(...)`
   - `async def search_relevant_memories(...) -> tuple[str, str, str]`
   - `async def load_session_context(...) -> SessionContext`
   - `def relationship_vector(ctx) -> dict`
   - `@property def available -> bool`
3. 在 `main.py` 的 `startup()` 中根据配置实例化对应后端

---

## 七、调试与可观测性

### 7.1 关键日志前缀

代码中已预埋了结构化日志前缀，grep 这些可快速定位问题：

| 前缀 | 含义 | 位置 |
|------|------|------|
| `[emergence]` | 关系 EMA 更新 | `evermemos_mixin.py` |
| `[evermemos]` | 长期记忆操作 | `evermemos_client.py` / `evermemos_mixin.py` |
| `[skill]` | 技能执行 | `chat_agent.py` / `task_skill_engine.py` |
| `[genome]` | 人格引擎核心 | `genome_engine.py` |
| `[metabolism]` | 驱力代谢 | `drive_metabolism.py` |
| `[crystallization]` | 风格记忆晶化 | `style_memory.py` |
| `[proactive]` | 主动消息 | `proactive.py` |

### 7.2 状态检查命令

```bash
# 查看某用户的神经权重和驱力状态
sqlite3 .data/openher.db "SELECT agent_data FROM genome_state WHERE user_id='xxx' AND persona_id='luna';"

# 查看风格记忆的最近晶化记录
sqlite3 .data/openher.db "SELECT * FROM style_memory ORDER BY created_at DESC LIMIT 5;"

# 查看 EverMemOS circuit breaker 状态
# （目前只有日志输出，无 HTTP 端点暴露）
```

---

## 八、修改审查清单

在提交任何影响核心引擎的 PR 前，确认以下检查项：

- [ ] 未在 system prompt 中硬编码人格特征（遵守 C-1）
- [ ] `_turn_lock` 仍覆盖所有 Agent 状态修改路径（遵守 C-4）
- [ ] 新增步骤插入生命周期时，验证了上下游数据依赖（遵守 C-6）
- [ ] 未将 Single-Pass Actor 拆分为多轮调用（遵守 C-7）
- [ ] 异步 I/O 操作未阻塞 `_chat_inner()` 主流程（遵守 C-8）
- [ ] 新增功能通过 Skill Engine 实现，未直接修改 engine/（遵守 C-9）
- [ ] 新增 provider 继承基类并注册到 registry（遵守 C-10）
- [ ] 测试通过：`pytest tests/ -v`
