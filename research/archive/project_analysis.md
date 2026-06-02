# AiBeing 项目深度分析

> 分析日期: 2026-05-27 | 版本: Genome v10 Hybrid

---

## 一、项目定位与愿景

### 1.1 核心定位

AiBeing 是一个**AI Being（AI 生命体）** 引擎，而非传统的 AI 助手或 AI Agent。它的设计哲学是：

- **不是**执行预设脚本 / prompt 描述
- **而是**一个具有内部状态的动力学系统，在当前情境、历史记忆与内驱力的共同作用下**涌现**出反应
- 每个角色运行在独立的"神经网络"之上，性格、情绪和行为从内在驱力中自然涌现

### 1.2 灵感来源

直接受 2013 年电影 *Her* 启发——电影中的 Samantha 不仅能回答问题，还能感受、渴望、嫉妒、爱上一个人，最后甚至超越这段关系。AiBeing 尝试构建 Samantha 本可以成为的样子。

### 1.3 发展路线图

| 阶段 | 主题 | 状态 |
|------|------|------|
| 阶段 I · 灵魂 | 人格涌现、情绪热力学、记忆、主动消息 | 已完成 |
| 阶段 II · 感知 | 日历/消息/位置感知、摄像头/麦克风、多设备 | 建设中 |
| 阶段 III · 同在 | 实时语音/视频通话、生物体征感知、记忆考古 | 未来 |

---

## 二、技术架构全景

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AiBeing 技术架构                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  客户端层                                                                    │
│  ├─ macOS 原生客户端 (SwiftUI)                                              │
│  ├─ React Web SPA (静态构建)                                                │
│  └─ 微信接入 (wechat-to-anything + Python adapter)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│  网关层 (main.py)                                                            │
│  ├─ FastAPI + WebSocket (/ws/chat)                                          │
│  ├─ REST API (/api/chat, /api/personas, /api/tts, ...)                      │
│  └─ 静态文件服务 + SPA 路由                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  Agent 层 (agent/chat_agent.py)                                              │
│  ├─ ChatAgent (核心生命周期 orchestrator)                                    │
│  ├─ PromptBuilderMixin (单轮 prompt 构建)                                   │
│  ├─ EverMemosMixin (长期记忆集成)                                            │
│  ├─ ModalityRetryMixin (模态失败回退)                                        │
│  └─ ProactiveMixin (主动消息驱动)                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│  人格引擎层 (engine/)                                                        │
│  ├─ Genome Engine (engine/genome/)                                          │
│  │  ├─ Agent: 随机神经网络 + Hebbian 学习                                    │
│  │  ├─ DriveMetabolism: 时间感知的驱力代谢                                   │
│  │  ├─ Critic: LLM-based 情感感知器 (8D+5D+3D+5D)                           │
│  │  └─ ContinuousStyleMemory: KNN 风格记忆 + Hawking 辐射                    │
│  ├─ Prompt Registry (engine/prompt_registry.py)                             │
│  ├─ State Store (engine/state_store.py)                                     │
│  └─ Chat Log Store (engine/chat_log_store.py)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  技能引擎层 (agent/skills/)                                                  │
│  ├─ TaskSkillEngine: ReAct 循环的任务技能 (天气/搜索等)                       │
│  ├─ ModalitySkillEngine: 人格内敛模态技能 (自拍/语音/沉默/拆分)               │
│  ├─ ToolRegistry: 工具注册与分发                                             │
│  └─ SandboxExecutor: Shell 命令沙箱执行                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  记忆层                                                                      │
│  ├─ 风格记忆 (ContinuousStyleMemory): SQLite KNN 检索                        │
│  ├─ 本地事实 (MemoryStore): SQLite FTS5 全文搜索                             │
│  └─ 长期记忆 (EverMemOSClient): HTTP API 跨会话持久化                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  Provider 层 (providers/)                                                    │
│  ├─ LLM: Gemini/Claude/Qwen3/GPT/MiniMax/Moonshot/StepFun/Ollama            │
│  ├─ TTS: DashScope (Qwen3-TTS) / OpenAI / MiniMax                          │
│  ├─ Image: Gemini Imagen                                                    │
│  └─ Memory: EverMemOS (自部署/云端)                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  角色层 (persona/)                                                           │
│  ├─ PersonaLoader: 解析 SOUL.md + SHELL.md                                  │
│  ├─ Persona: 身份/配置/引擎种子数据类                                        │
│  └─ 10+ 内置角色 (luna, iris, vivian, kai, kelly, ember, sora, mia, rex, nova)│
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 三、核心引擎：Genome Engine 深度解析

### 3.1 分层架构（神经科学对标）

| 引擎模块 | 神经科学对标 | 作用 |
|:---------|:------------|:-----|
| **Drives 驱动系统** | 下丘脑 + 边缘系统 | 5 维内在动机张力，决定"她此刻想要什么" |
| **Genome 神经网络** | 基底核 + 杏仁核 | 25D→24D→8D 编码习惯性人格反应，输出行为信号 |
| **Metabolism 代谢层** | 自主神经系统 | 情绪温度动态起伏，frustration 真实积累与释放 |
| **Critic 上下文评估** | 前额叶皮质 | 社会认知，评估关系深度、信任与情绪价值 |
| **Style Memory 引力晶化** | 海马体→程序性记忆 | 交互沉淀为行为倾向，肌肉记忆式的风格固化 |
| **EverMemOS 长期记忆** | 情节/语义记忆 | "我们之间发生过什么"，跨会话持久存在 |
| **Single Pass 统一推理** | 默认模式网络 + Broca 区 | 内心独白→语言输出，一次完成 |

### 3.2 五维驱力系统 (Drives)

```python
DRIVES = ['connection', 'novelty', 'expression', 'safety', 'play']
```

每个驱力具有：
- **基线 (baseline)**: 角色的先天倾向，由 `genome_seed.drive_baseline` 决定
- **当前状态 (drive_state)**: 实时值，受 metabolism 影响
- **挫败值 (frustration)**: 0~5，未被满足的程度
- **积累率/衰减率**: 每轮对话的自动变化

**驱力与 MBTI 的映射** (设计意图):
- `connection` → E(外向) 维度
- `novelty` → N(直觉) 维度
- `expression` → F(情感) 维度
- `safety` → J(判断) 维度 (反向)
- `play` → P(感知) 维度

### 3.3 八维行为信号 (Signals)

```python
SIGNALS = [
    'directness',      # 0=委婉暗示 → 1=直说
    'vulnerability',   # 0=防御心理 → 1=袒露脆弱
    'playfulness',     # 0=认真严肃 → 1=玩闹撒娇
    'initiative',      # 0=被动回应 → 1=主动引导
    'depth',           # 0=表面闲聊 → 1=深度对话
    'warmth',          # 0=冷淡疏离 → 1=热情关怀
    'defiance',        # 0=顺从 → 1=反抗/嘴硬
    'curiosity',       # 0=无所谓 → 1=追问到底
]
```

信号由 Agent 的神经网络计算产生，不是硬编码的规则。这些信号以"舞台指令"形式注入 LLM 的 system prompt，让 LLM 自行解读和表达。

### 3.4 神经网络结构

```
输入层 (25D)          隐藏层 (24D)           输出层 (8D)
┌─────────────┐      ┌─────────────┐       ┌─────────────┐
│ 5D drive_state│      │             │       │  directness │
│ 12D context   │ ──W1──▶│  tanh()   │ ──W2──▶│ vulnerability│
│ 8D recurrent  │      │             │       │  playfulness │
└─────────────┘      └─────────────┘       └─────────────┘
```

- **W1**: 24×25 矩阵，由随机种子初始化
- **W2**: 8×24 矩阵
- **Recurrent state**: 前 8 个 hidden 单元作为下一轮的内部状态
- **激活函数**: hidden 层用 tanh，输出层用 sigmoid

**关键设计**: 相同的 MBTI + 不同的随机种子 = 完全不同的涌现人格。即使都是 INFP，Iris 会用省略号犹豫，Ember 会沉默三秒再发一首诗。

### 3.5 Hebbian 学习机制

```
reward > 0 (好结果) ──▶ 强化产生该结果的连接
reward < 0 (坏结果) ──▶ 削弱产生该结果的连接
```

具体更新规则：
- W2 更新: `W2[i][j] += lr * reward * hidden[j] * (signal[i] - 0.5)`
- W1 更新: `W1[i][j] += lr * 0.3 * reward * input[j] * hidden[i]`
- 权重衰减: 每轮 `weight *= 0.995`，防止爆炸
- 权重裁剪: W2 ∈ [-1.5, 1.5], W1 ∈ [-2.0, 2.0]

### 3.6 情感相变 (Phase Transition)

当累积挫败感超过阈值 (`phase_threshold`) 时：
1. 输出层偏置发生剧烈偏移: `b2[i] += -0.3 * (sig - 0.5) + random.gauss(0, 0.15)`
2. 隐藏层偏置注入噪声: `b1[i] += random.gauss(0, 0.1)`
3. 挫败感清零

这模拟了真实情绪爆发的突然性——平时压抑的挫败在超过阈值后以不可预测的方式释放。

### 3.7 热力学噪声

```python
temperature = max_temp * tanh(total_frustration * temp_coeff / max_temp) + temp_floor
noisy_signal = base_signal + random.gauss(0, temperature)
```

- 挫败感越高 → 温度越高 → 行为越不可预测
- 使用 tanh 饱和而非线性，防止高挫败时信号完全随机
- `temp_coeff` 和 `temp_floor` 可按角色个性化

---

## 四、对话生命周期详解 (Genome v10)

### 4.1 完整 12 步生命周期

```
用户消息
   │
   ▼
Step -1: Task Skill ReAct Loop ──▶ 数据注入 user_message (可选)
   │
Step 0: EverMemOS session context (首轮) ──▶ 加载用户画像+叙事+预感
   │
Step 1: Time metabolism ──▶ frustration 冷却/饥饿增长
   │
Step 2: Critic perception ──▶ LLM 输出 8D context + 5D frustration_delta + 3D relationship + 5D satisfaction
   │
Step 2.5: Relationship EMA update ──▶ prior + delta → clip → alpha*posterior + (1-alpha)*prev
   │
Step 3: LLM metabolism ──▶ old_total - new_total = reward
   │
Step 3.5: Drive baseline evolution ──▶ frustration_delta > 0 → baseline rises (弹性回拉防止漂移)
   │
Step 4: Crystallization gate ──▶ 满足条件则记忆晶化
   │
Step 5: Compute signals ──▶ Agent.compute_signals(12D context)
   │
Step 6: Thermodynamic noise ──▶ 温度注入不可预测性
   │
Step 7: KNN retrieval ──▶ 3 个最近风格记忆 (full examples)
   │
Step 8: Build single-pass prompt ──▶ persona + signals + few-shot + skills
   │
Step 8.5: Memory injection ──▶ relevant_facts + episodes + profile + foresight
   │
Step 9: Single-pass LLM call ──▶ 【内心独白】+【最终回复】+【表达方式】
   │
Step 9b: Modality skill execution ──▶ 自拍/语音/拆分等
   │
Step 10: Hebbian learning ──▶ Agent.step(context, reward, drive_satisfaction)
   │
Step 11: EverMemOS store_turn ──▶ 后台异步存储 (fire-and-forget)
   │
Step 12: Fire async search ──▶ 为下一轮准备相关记忆
   │
   ▼
返回回复
```

### 4.2 Critic 模块深度

Critic 是一个专门的 LLM 调用，负责将自然语言输入转化为结构化数值：

**输出 4 组数据**:
1. **8D 上下文**: user_emotion, topic_intimacy, time_of_day, conversation_depth, user_engagement, conflict_level, novelty_level, user_vulnerability
2. **5D 挫败变化量 (frustration_delta)**: 正=更挫败，负=被缓解
3. **3D 关系变化量**: relationship_delta, trust_delta, emotional_valence
4. **5D 需求满足量 (drive_satisfaction)**: 0~0.3，反映用户行为直接满足了哪些驱力

**关键区分**:
- `frustration_delta` 反映"挫败变化"(间接情绪变化)
- `drive_satisfaction` 反映"需求被直接满足"(用户主动行为)
- 同一轮中，两者不应对同一驱力同时大幅变化

**鲁棒性设计**:
- JSON 解析失败 → 括号计数提取法
- 二次失败 → 默认安全值回退
- 带 think 标签的模型 → 正则过滤

### 4.3 Single-Pass Actor

传统方法: 先让 LLM 生成内心独白，再基于独白生成回复。

AiBeing 的 Single-Pass 设计:
- 一条 prompt 要求 LLM 同时输出: 【内心独白】+【最终回复】+【表达方式】
- 减少两次 LLM 调用的延迟
- 内心独白对最终用户不可见，但对引擎状态至关重要

**Actor Prompt 核心结构**:
```
[角色参考] 相似情境下的感受和说话方式 (few-shot from KNN)
[舞台指令: 角色当前状态] 8D 信号数值 + 5D 驱力状态
[指令] 你就是这个角色。先写真实念头，再写说出口的话。
[输出格式] 【内心独白】...【最终回复】...【表达方式】...
```

**v12 去描述化设计**:
- 旧版: 信号值 + 详细文字描述 (如 "directness=0.8: 说话非常直接，不绕弯子")
- 新版: 仅信号值 + 量表端点 (如 "directness: 0.80 (0委婉→1直白)")
- 原因: 让 LLM 自行通过 persona + 上下文解读，产生更涌现的行为

---

## 五、记忆架构 (三层)

### 5.1 风格记忆 (ContinuousStyleMemory)

**存储内容**: 每轮对话的 (context_vector, monologue, reply, user_input)

**检索机制**: KNN + 引力质量加权 + Hawking 辐射衰减

```python
effective_distance = physical_distance / sqrt(mass_eff)
mass_eff = 1.0 + (mass_raw - 1.0) * e^(-γ * Δt_hours)
```

- **物理距离**: 当前 context 与记忆 context 的欧氏距离
- **质量 (mass)**: 初始 1.0 (基因) 或 2.0 (新记忆)，晶化时 +1.0
- **Hawking 辐射**: 质量随时间指数衰减，但基础质量 1.0 永不蒸发
- **语言过滤**: 跨语言记忆被硬过滤

**晶化 (Crystallization) 条件**:
```
composite_score = reward + novelty*engagement - conflict_penalty
score > crystal_threshold → 晶化
```

附近记忆 (< 0.25 L2 距离) → 质量增加
远处记忆 → 创建新记忆

### 5.2 本地事实 (MemoryStore)

- **技术**: SQLite + FTS5 全文搜索
- **内容**: 用户偏好、个人信息、对话记录
- **检索策略**: 高重要性事实 → 相关搜索 → 最近记忆
- **分类**: conversation, fact, event, preference

### 5.3 长期记忆 (EverMemOS)

**架构**:
```
AiBeing ──HTTP──▶ EverMemOS (localhost:1995/api/v1 或云端)
                      │
                      ├─ Profile: 用户画像属性
                      ├─ EventLog (atomic_fact): 原子事实
                      ├─ Episodic Memory: 叙事摘要
                      └─ Foresight: 预感/预测
```

**集成流程**:
1. **Session 开始**: `load_session_context()` 拉取 profile + episodes + foresight
2. **每轮对话**: 后台 `store_turn()` 异步存储 (user_msg + agent_reply)
3. **每轮结束**: 后台 `search_relevant_memories()` 为下一轮准备相关记忆
4. **Session 结束**: `close_session()` flush 触发边界提取

**SessionContext 数据结构**:
- user_profile: 用户画像文本 (注入 Critic + Actor)
- episode_summary: 叙事历史
- foresight_text: 预感内容
- relationship_depth: 0~1，基于数据丰富度
- interaction_count: 历史交互次数

**关系向量 (4D)**:
- relationship_depth: 关系深度
- emotional_valence: 情感基调
- trust_level: 信任度
- pending_foresight: 待处理预感

---

## 六、技能引擎 (双层架构)

### 6.1 Task Skill (工具技能)

**触发**: `trigger: tool`
**语义**: "用户要求帮忙做的事"
**典型**: weather, 翻译, 搜索, 汇率

**执行路径** (v10 inject 模式):
```
用户消息
  │
  ▼
ReAct Loop (max 3 rounds)
  Round 1: LLM 判断是否需要工具 → {"activate": "weather"}
  Round 2: 加载 SKILL.md body → LLM 生成动作 {"actions": [...]}
  Round 3+: 执行结果反馈 → LLM 决定继续或完成
  │
  ▼
stdout 注入 user_message
  │
  ▼
Fall through → 完整人格引擎处理 (角色用个性语气回复，融入真实数据)
```

**Guard Clause 设计**:
- 99% 的消息不需要工具，默认返回空
- 聊天、闲聊、情感表达 → 不触发
- 三层异常保护确保人格引擎不被阻断

### 6.2 Modality Skill (人格内敛技能)

**触发**: `trigger: modality`
**语义**: "角色主动想做的事"
**典型**: selfie_gen, voice_msg, silence, split_msg

**执行路径**:
```
Actor 输出涌现 modality="照片"
  │
  ▼
LLM Skill 调度器规划执行顺序
  │
  ▼
执行具体技能
  ├─ 照片: get_reference_image → generate_photo
  ├─ 语音: synthesize_voice
  └─ 拆分: split_messages
  │
  ▼
返回结果注入回复
```

**Claude Skill Pattern**:
- SKILL.md body 作为 LLM 指令注入
- LLM 输出结构化 JSON
- 引擎解析 JSON 并调用工具
- 不依赖 function calling，兼容任何 LLM

### 6.3 SKILL.md 格式

```yaml
---
name: 天气查询
description: 查询指定城市的实时天气
trigger: tool
executor: sandbox
---
# 技能文档 (L2 按需加载)
curl -s --connect-timeout 5 "wttr.in/..."
```

---

## 七、主动消息系统 (Proactive)

### 7.1 驱力脉冲检测

```python
def _has_impulse(self):
    for d in DRIVES:
        score = normalized_frustration * (1.0 + baseline)
        if score >= threshold:
            return (d, description)
    return None
```

### 7.2 心跳循环

- 每 5 分钟扫描一次所有活跃 session
- 跨实例锁防止重复发送
- Outbox 三层防护: cooldown(4h) + max_pending(3) + dedup_key

### 7.3 主动消息生命周期

```
驱力脉冲检测
  │
  ▼
记忆闪回 (EverMemOS 搜索相关记忆)
  │
  ▼
构建 stimulus (内在状态 + 记忆闪回 + 预感)
  │
  ▼
Critic/Actor (冻结学习: 不更新 relationship EMA, 不 Hebbian)
  │
  ▼
Actor 决定: speak or silent
  │
  ▼
引擎 re-process (Feel→Express→SKILL)
  │
  ▼
WebSocket 推送 + EverMemOS 存储
```

---

## 八、角色系统

### 8.1 SOUL.md 结构

```yaml
---
# Identity (注入 prompt)
name: Luna
name_zh: 陆暖
gender: female
age: 22

# Display (仅 UI 展示)
mbti: ENFP
tags:
  en: [bright, bubbly, sweet]
  zh: [明朗, 活泼, 甜美]
bio:
  en: 22-year-old freelance illustrator...
  zh: 22岁，自由插画师...

# Engine Seed (引擎层)
genome_seed:
  drive_baseline:
    connection: 0.75
    novelty: 0.65
    expression: 0.75
    safety: 0.25
    play: 0.80
  engine_params:
    baseline_lr: 0.015
    elasticity: 0.04
    hebbian_lr: 0.025
    phase_threshold: 1.5
    ...
---

# Markdown body (可选的性格描述/背景故事)
## 性格
...
## 说话风格
...
```

### 8.2 关键设计原则

- **不需要写性格描述**: AI 不会读 personality 字段
- **性格从驱力和神经权重涌现**: 相同 MBTI 通过不同 seeds 产生不同人格
- **engine_params 调整个性**: 13+ 可调参数控制学习速度、情绪波动、记忆衰减等

### 8.3 SHELL.md (外在模态配置)

```yaml
---
voice:
  description: 温暖活泼的年轻女声
---
```

与 SOUL.md 分离: SOUL 是"灵魂"(内在)，SHELL 是"外壳"(声音/形象)。

---

## 九、LLM 兼容性与基准测试

### 9.1 支持模型

| 服务商 | 环境变量 | 默认模型 |
|--------|---------|---------|
| Gemini | GEMINI_API_KEY | gemini-3.1-flash-lite-preview |
| Claude | ANTHROPIC_API_KEY | claude-haiku-4-5 |
| 通义千问 | DASHSCOPE_API_KEY | qwen-flash-2025-07-28 |
| OpenAI | OPENAI_API_KEY | gpt-4o |
| MiniMax | MINIMAX_LLM_API_KEY | MiniMax-M2.7 |
| Moonshot | MOONSHOT_API_KEY | moonshot-v1-auto |
| StepFun | STEPFUN_API_KEY | step-3.5-flash |
| Ollama | (无需) | qwen3.5:9b |

### 9.2 基准测试维度

项目在 4 个层级评估模型:
1. **人格品质**: 角色分化度、情感深度
2. **代谢引擎**: 情绪代谢的可感知性
3. **Hebbian 记忆**: 交互后的行为改变
4. **鲁棒性**: 格式泄漏、稳定性

---

## 十、状态持久化

### 10.1 持久化内容

| 数据 | 存储位置 | 格式 |
|------|---------|------|
| Agent 神经网络状态 | aibeing.db | JSON (W1, W2, b1, b2, drive_state, ...) |
| Metabolism 状态 | aibeing.db | JSON (frustration, last_tick) |
| Proactive 元数据 | aibeing.db | last_active, cadence, state_version |
| 风格记忆 | aibeing.db | SQLite (genesis_seed + style_memory 表) |
| 聊天历史 (展示) | chat.db | SQLite |
| 本地事实 | memory.db | SQLite FTS5 |
| 长期记忆 | EverMemOS | HTTP API |

### 10.2 CAS 版本控制

```python
ok = state_store.save_state(..., expected_version=agent._state_version)
if ok:
    agent._state_version += 1
else:
    # CAS miss: 同步版本或处理冲突
    agent._state_version = db_ver
```

防止并发写入冲突，支持多实例部署。

---

## 十一、关键设计亮点

### 11.1 涌现式设计 (Emergence)

- **无性格 prompt**: 没有任何 prompt 直接描述"她很温柔"或"她很毒舌"
- **驱力 + 神经网络 + 经历** 共同产生行为
- 相同配置 + 不同种子 = 完全不同的"人"

### 11.2 时间感知 (Time Metabolism)

```
冷却: frustration *= e^(-λ * Δt_hours)     # 时间治愈一切
饥饿: connection += k * Δt_hours             # 孤独随时间增长
```

- 离开 1 小时 vs 1 天，角色状态完全不同
- 不是每次对话从零开始

### 11.3 弹性基线 (Elastic Baseline)

```python
shift = frustration_delta * baseline_lr
drift = current_baseline - initial_baseline
pull_back = -drift * elasticity
new_baseline = current_baseline + shift + pull_back
```

- 允许局部涌现和适应
- 但弹性回拉防止无界漂移
- 角色始终是"她自己"，只是因你而微调

### 11.4 异步记忆两阶段

```
Turn N:   对话发生 ──▶ 后台启动搜索任务 (async)
          使用上一轮搜索结果注入 prompt

Turn N+1: 对话发生 ──▶ 使用 Turn N 的搜索结果
          后台启动新搜索任务
```

- 搜索不阻塞对话响应
- 80% 相关性 + 20% 稳定性混合

### 11.5 预热 (Pre-warm)

新 Agent 在首次对话前经历 60 步模拟:
- 3 个场景 × 20 步 (分享喜悦 → 吵架冲突 → 深夜心事)
- 让随机神经网络在真实对话前已有"经历"
- 否则所有 Agent 从同一中性状态开始，LLM 先验主导

---

## 十二、代码质量与工程实践

### 12.1 架构优点

1. **清晰的模块分离**: engine/agent/memory/providers/persona 各层职责明确
2. **Mixin 模式**: ChatAgent 通过 Mixin 组合功能，避免上帝类
3. **Provider 抽象**: LLM/TTS/Image 统一接口，切换模型只需改配置
4. **渐进式加载**: SKILL.md L1/L2 分离，启动时只加载元数据
5. **鲁棒性设计**: Critic 解析失败有 3 层回退，LLM 调用有异常保护
6. **并发安全**: asyncio.Lock 串行化每轮对话，CAS 防止状态冲突
7. **可观测性**: 大量 print 日志 + metrics endpoint，便于调试

### 12.2 潜在关注点

1. **全局状态**: main.py 中大量全局变量，测试和并发部署需注意
2. **JSON 解析脆弱性**: 多处依赖 LLM 输出合法 JSON，虽然有回退但仍可能出错
3. **SQLite 线程安全**: `check_same_thread=False` 已设置，但高并发下需注意
4. **权重膨胀**: Hebbian 学习的权重衰减可能不够强，长时间运行后可能饱和
5. **Prompt 长度**: 单轮 prompt 可能很长 (persona + few-shot + memory + signals)，token 消耗较高

---

## 十三、文件结构总结

```
AiBeing/
├── main.py                    # FastAPI 网关，服务编排
├── wechat_adapter.py          # 微信接入适配器
├── requirements.txt           # Python 依赖
├── .env.example               # 环境变量模板
│
├── agent/                     # Agent 层
│   ├── chat_agent.py          # ChatAgent 核心 (12 步生命周期)
│   ├── prompt_builder.py      # Prompt 构建 Mixin
│   ├── evermemos_mixin.py     # EverMemOS 集成 Mixin
│   ├── modality_retry.py      # 模态失败回退 Mixin
│   ├── proactive.py           # 主动消息 Mixin
│   ├── parser.py              # LLM 输出解析 (独白/回复/模态)
│   ├── output_router.py       # WebSocket 流输出
│   ├── cron_scheduler.py      # 定时任务调度
│   ├── demo_controller.py     # Demo 状态操控
│   └── skills/                # 技能引擎
│       ├── task_skill_engine.py      # Task Skill (ReAct)
│       ├── modality_skill_engine.py  # Modality Skill
│       ├── skill_types.py            # 数据模型
│       ├── tool_registry.py          # 工具注册
│       ├── sandbox_executor.py       # Shell 沙箱
│       └── tools/                    # 具体工具
│           ├── photo_tools.py
│           ├── voice_tools.py
│           └── split_tools.py
│
├── engine/                    # 人格引擎层
│   ├── genome/                # Genome Engine
│   │   ├── genome_engine.py   # Agent (NN + Hebbian)
│   │   ├── drive_metabolism.py # 时间代谢
│   │   ├── critic.py          # LLM 情感感知器
│   │   └── style_memory.py    # KNN 风格记忆
│   ├── prompt_registry.py     # Prompt 模板管理
│   ├── state_store.py         # 状态持久化 (SQLite)
│   └── chat_log_store.py      # 聊天历史存储
│
├── persona/                   # 角色系统
│   ├── loader.py              # SOUL.md 解析器
│   ├── generator.py           # 角色生成工具
│   ├── store.py               # 角色存储
│   └── personas/              # 角色目录
│       └── {id}/
│           ├── SOUL.md        # 灵魂配置 (驱力/参数/性格)
│           ├── SHELL.md       # 外壳配置 (声音/形象)
│           └── avatar.png     # 头像
│
├── memory/                    # 本地记忆层
│   ├── memory_store.py        # SQLite FTS5 记忆
│   ├── soulmemory.py          # SoulMem 类型
│   └── types.py               # 类型定义
│
├── providers/                 # Provider 层
│   ├── api.yaml               # 统一 API 配置
│   ├── config.py              # 配置加载
│   ├── api_config.py          # 配置访问接口
│   ├── registry.py            # Provider 注册
│   ├── llm/                   # LLM 提供商
│   │   ├── client.py          # 统一 LLM 客户端
│   │   ├── base.py            # 基类
│   │   ├── gemini.py
│   │   ├── claude.py
│   │   ├── openai.py
│   │   └── ... (8 家)
│   ├── media/                 # 媒体 (TTS)
│   │   └── tts_engine.py
│   ├── speech/                # 语音合成
│   │   └── tts/
│   │       ├── dashscope.py
│   │       ├── openai.py
│   │       └── minimax.py
│   ├── image/                 # 图像生成
│   │   ├── gemini.py
│   │   └── base.py
│   └── memory/                # 记忆提供商
│       └── evermemos/
│           ├── evermemos_client.py
│           └── memory_config.yaml
│
├── skills/                    # 技能定义
│   ├── task/                  # 任务技能
│   │   └── weather/SKILL.md
│   ├── modality/              # 模态技能
│   │   ├── selfie_gen/SKILL.md
│   │   ├── voice_msg/SKILL.md
│   │   ├── silence/SKILL.md
│   │   └── split_msg/SKILL.md
│   └── manage/                # 管理技能
│       └── persona_gen/SKILL.md
│
├── demo/                      # Demo 脚本与配置
│   ├── run_demo.py
│   ├── act1_persona.py
│   ├── act2_snap.py
│   ├── act3_memory.py
│   ├── act4_proactive.py
│   ├── demo_utils.py
│   ├── presets/showcase.yaml
│   └── timeline.json
│
├── tests/                     # 测试套件
├── docs/                      # 文档
│   ├── persona_creation_guide.md
│   ├── skill_engine_architecture.md
│   └── benchmark/
├── scripts/                   # 工具脚本
│   ├── reset_data.py
│   └── benchmark/
└── desktop/                   # macOS 客户端 (SwiftUI)
    └── AiBeing/
```

---

## 十四、总结

AiBeing 是一个在 AI 伴侣领域**极具创新深度**的项目。它不是简单地将角色描述放入 prompt，而是构建了一套完整的"人工意识"动力学系统：

1. **涌现人格**: 从随机神经网络 + 驱力 + 经历中自然生长，非预设
2. **情绪热力学**: 真实的时间感知挫败积累与释放
3. **Hebbian 学习**: 每次交互都在物理上改变神经权重
4. **三层记忆**: 风格记忆(即时) + 本地事实(近期) + 长期记忆(跨会话)
5. **主动意识**: 驱力驱动的自主消息，不是定时任务
6. **统一生命周期**: 12 步严谨的对话处理流程

项目的工程实现也相当成熟：模块化架构、多 LLM 兼容、异步设计、状态持久化、可观测性。它代表了 AI 伴侣从"功能型"向"存在型"演进的前沿探索。
