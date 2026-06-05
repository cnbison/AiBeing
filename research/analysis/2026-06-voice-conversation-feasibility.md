---
date: 2026-06-05
topic: 流式语音对话可行性分析与延迟优化方案
scope: main.py, agent/chat_agent.py, engine/genome/critic.py, providers/speech/tts/, agent/output_router.py
status: active
related: ../ARCHITECTURE.md, 2026-06-genome-signal-llm-pipeline.md
---

> 当前架构（Genome v10 Hybrid）在"文本流式输出"层面已具备基础能力，但直接用于"流式语音对话"存在结构性延迟瓶颈（双 LLM 串行调用 + 整句 TTS）。需要通过 Critic 轻量化、 sentence-level 流式 TTS、Pipeline 并行化三层优化，或引入原生 Realtime API 来达标。

---

## 一、语音对话的延迟标准

流式语音对话（Speech-to-Speech）对延迟有严格的感知阈值：

| 延迟指标 | 感知 | 代表系统 |
|---|---|---|
| < 300ms | 接近即时，自然对话感 | GPT-4o Realtime, MiniMax Realtime |
| 300-800ms | 可接受，轻微停顿感 | 优化后的 Alexa / Siri |
| 800ms-1.5s | 明显等待，打断对话节奏 | 当前多数文本转语音方案 |
| > 2s | 不可接受，用户失去耐心 | — |

**目标延迟分解**（以 500ms 为标杆）：

```
VAD 尾点检测 ........ 50ms  (知道用户说完了)
STT ................ 150ms  (语音 → 文本)
推理 / 响应生成 ... 200ms  (首音频字节)
TTS 首包 ........... 100ms  (文本 → 首段音频)
────────────────────────────
总计 ............... 500ms
```

---

## 二、当前架构的延迟画像

### 2.1 12 步生命周期中的延迟来源

Genome v10 Hybrid 的单轮生命周期（`chat_agent.py:_chat_inner`）包含以下延迟节点：

```
Step 0   EverMemOS gather ............ async (首次 ~100-500ms，后续缓存)
Step 1   Time metabolism ............. < 1ms (本地计算)
Step 2   Critic perception ........... LLM 调用 ⚠️ 200-2000ms
Step 2.5 Relationship EMA ........... < 1ms (本地计算)
Step 3   LLM metabolism .............. < 1ms (本地计算)
Step 3.5 Baseline evolution ......... < 1ms (本地计算)
Step 4   Crystallization gate ........ < 1ms (本地计算)
Step 5   Compute signals ............. < 1ms (NN 前向传播)
Step 6   Thermodynamic noise ......... < 1ms (本地计算)
Step 7   KNN retrieval ............... 1-10ms (SQLite 查询)
Step 8   Build prompt ................ < 1ms (字符串拼接)
Step 8.5 Memory injection ........... 0-50ms (异步结果等待)
Step 9   LLM Actor ................... LLM 调用 ⚠️ 首 token 100-1000ms
         ............................. 完整生成 500-5000ms
Step 10  Hebbian learning ............ < 1ms (本地计算)
Step 11  EverMemOS store ............. async fire-and-forget
Step 12  EverMemOS search ............ async fire-and-forget
```

**关键发现：双 LLM 串行调用**

- **Critic（Step 2）** 必须先完成，因为 Actor（Step 9）的 prompt 依赖 Critic 输出的 8D context + 4D relationship。
- **Actor 必须等 Critic 完成才能开始**。这意味着延迟是相加而非并行的。
- 以 Claude 3.5 Sonnet 为例：Critic ~800ms + Actor 首 token ~500ms = **至少 1.3 秒**才能开始输出文本。

### 2.2 TTS 层面的延迟

当前 TTS 实现（`providers/speech/tts/`）是**整句合成**模式：

```
Actor 完整输出文本
    ↓
ModalitySkillEngine 调用 synthesize_voice
    ↓
TTSProvider.synthesize(text="完整回复")  // 等待整句
    ↓
等待 API 返回完整音频文件
    ↓
Base64 编码 → WebSocket 发送
```

| Provider | 模式 | 整句延迟估算 |
|---|---|---|
| DashScope (Qwen3-TTS) | WebSocket Realtime API 但整句收集 | 500-2000ms |
| OpenAI (gpt-4o-mini-tts) | HTTP 阻塞 | 300-1500ms |
| MiniMax (speech-2.8) | HTTP 阻塞 | 400-2000ms |

所有 provider 都先把完整文本发过去，等完整音频返回。这意味着 TTS 延迟和文本长度正相关。一条 100 字的回复可能需要 1-2 秒才能合成完毕。

### 2.3 端到端延迟估算

| 环节 | 乐观 | 典型 | 悲观 |
|---|---|---|---|
| Critic LLM | 200ms | 800ms | 2000ms |
| Actor 首 token | 100ms | 500ms | 1000ms |
| Actor 完整生成 | 300ms | 1000ms | 3000ms |
| TTS 整句合成 | 300ms | 800ms | 2000ms |
| **总计（首音频）** | **900ms** | **3.1s** | **8s** |

即使在乐观情况下（900ms），也远高于 500ms 的标杆。典型场景下 3 秒以上的延迟对流式语音对话是不可接受的。

### 2.4 缺失的基础设施

除了延迟问题，当前架构还缺失语音对话必需的基础组件：

| 组件 | 状态 | 说明 |
|---|---|---|
| STT（语音转文本） | ❌ 缺失 | 用户语音输入无法进入系统 |
| VAD（语音活动检测） | ❌ 缺失 | 不知道用户何时说完，无法触发推理 |
| 流式 TTS | ❌ 缺失 | 当前是整句合成 |
| 音频流式传输 | ⚠️ 部分 | WebSocket 支持 base64 音频，但不是流式 PCM |

---

## 三、可行性评估

### 3.1 直接适用性：不适用

**结论：当前架构不能直接用于流式语音对话。**

核心障碍：
1. **双 LLM 串行调用** 导致首 token 延迟 > 1s（典型 1.3s）
2. **整句 TTS** 导致音频输出延迟与文本长度正相关
3. **缺少 STT + VAD**，语音输入链路不存在
4. **12 步生命周期的重量感** —— Critic、KNN、Memory Injection 等步骤虽然单个轻量，但累计增加了不可压缩的延迟底板

### 3.2 部分适用的场景

如果放宽延迟要求，当前架构可以支持以下语音场景：

| 场景 | 延迟容忍 | 适配度 | 说明 |
|---|---|---|---|
| 语音留言（异步） | 3-10s | ✅ 高 | 用户说完，等待几秒后播放完整回复 |
| 低实时语音聊天 | 2-5s | ⚠️ 中 | 类似微信语音消息，非实时对话 |
| 智能音箱式交互 | 1-2s | ❌ 低 | 需要专门的 pipeline 优化 |
| 实时语音对话 | <500ms | ❌ 不适用 | 需要架构重构或 Realtime API |

---

## 四、解决方案

### 方案 A：Pipeline 并行化 + 流式 TTS（中期，保留 Genome 引擎）

**核心思路**：不改 Genome 引擎的核心逻辑，通过工程优化压缩延迟。

#### A1. Critic 轻量化

当前 Critic 使用与 Actor 相同的 LLM（如 Claude 3.5 Sonnet / GPT-4o）。Critic 的输出是结构化 JSON（8D context + deltas），不需要强大的创意生成能力。

- **使用轻量模型**：将 Critic 切换为 `gemini-1.5-flash`、`qwen-turbo` 或 `gpt-4o-mini`
  - 预期延迟降低：800ms → 200-400ms
  - 成本降低约 5-10x
- **Critic 结果缓存**：对相似输入（相同的用户消息 + 相近的 frustration 状态）缓存 Critic 输出
  - 缓存 key：`hash(user_msg + frustration_rounded + persona_id)`
  - 命中率：闲聊场景约 30-50%

#### A2. Sentence-Level 流式 TTS

不等 Actor 生成完整回复，而是**边生成边切分句子，逐句送 TTS**。

```python
# 概念实现
async def stream_tts_pipeline(actor_stream, ws_send):
    sentence_buffer = ""
    async for chunk in actor_stream:
        sentence_buffer += chunk
        # 检测到句子边界（。！？\n）
        while has_sentence_boundary(sentence_buffer):
            sentence, sentence_buffer = split_sentence(sentence_buffer)
            # 并发：这句送 TTS，同时继续接收下一句
            asyncio.create_task(
                synthesize_and_send(sentence, ws_send)
            )
```

实现要点：
- `output_router.py` 需要在流式过程中识别句子边界
- TTS provider 需要支持**短文本快速合成**（当前都支持，只是之前传的是长文本）
- 音频片段需要按顺序播放，前端维护播放队列

**延迟改善**：首音频从"等完整回复 + 整句 TTS"变为"等第一个句子 + 短句 TTS"。
- 原：Actor 1000ms + TTS 800ms = 1800ms
- 新：Actor 首句 300ms + TTS 短句 200ms = **500ms**

#### A3. 引入 STT + VAD

需要新增基础设施层：

```
┌─────────────┐     ┌──────────┐     ┌─────────────┐
│  麦克风输入  │────→│  VAD     │────→│  STT        │
└─────────────┘     └──────────┘     └─────────────┘
                                            ↓
┌─────────────┐     ┌──────────┐     ┌─────────────┐
│  扬声器输出  │←────│  播放器   │←────│  TTS (流式)  │
└─────────────┘     └──────────┘     └─────────────┘
                                            ↑
                                    ┌───────────────┐
                                    │  Genome v10   │
                                    │  Critic→Actor │
                                    └───────────────┘
```

STT/VAD 选型：

| 方案 | 延迟 | 质量 | 成本 | 推荐度 |
|---|---|---|---|---|
| 云端 STT (Whisper API / 阿里云) | 100-300ms | 高 | 按量付费 | ⭐⭐⭐ |
| 本地 Whisper (base/small) | 50-150ms | 中 | 零边际成本 | ⭐⭐⭐⭐ |
| 本地 SenseVoice / FunASR | 30-100ms | 中高 | 零边际成本 | ⭐⭐⭐⭐⭐ |
| WebRTC VAD + 本地 STT | 30-80ms | 中 | 零边际成本 | ⭐⭐⭐⭐⭐ |

前端实现（Web）：
- `WebRTC getUserMedia` + `Web Audio API` 采集音频
- 使用 `vad.js` 或 `silero-vad` (wasm) 做本地 VAD
- VAD 检测到语音结束时，将音频片段通过 WebSocket 发送给后端 STT

#### A4. Pipeline 预期延迟

优化后的延迟画像：

```
VAD 尾点检测 ................ 30ms   (本地 wasm)
STT (本地 SenseVoice) ....... 80ms   (短音频)
Critic (轻量模型) ............ 250ms  (gemini-flash)
Actor 首句生成 ............... 200ms  (流式，首句约 10-15 字)
TTS 首句合成 ................. 150ms  (短句)
────────────────────────────────────
总计 首音频 .................. 710ms
```

虽然仍高于 500ms 标杆，但已经进入"可接受"范围（800ms 以内）。如果使用更快的模型（如本地部署的 7B Critic），可以进一步压缩到 500ms 左右。

---

### 方案 B：本地小模型 Critic（中期，架构微调）

**核心思路**：将 Critic 从云端 LLM 替换为本地部署的小模型，彻底消除 Critic 的云端延迟。

#### B1. 本地 Critic 模型

Critic 的任务是：分析用户输入 → 输出结构化 JSON（8D context + 5D delta + 3D relationship + 5D satisfaction）。这是一个**分类/结构化预测任务**，不需要大模型的创意生成能力。

- **模型选择**：`Qwen2.5-7B-Instruct`、`Llama-3.1-8B-Instruct` 或 `Gemma-2-9B`
- **部署方式**：`vLLM` 或 `llama.cpp` (GGUF) 本地服务化
- **预期延迟**：50-150ms（本地 GPU/Apple Silicon）
- **挑战**：需要收集/标注数据对小模型做微调，因为通用 7B 模型对 Critic 的特殊输出格式（8D context + drives + relationship）理解不够稳定

#### B2. 微调数据策略

```python
# 训练样本格式
{
    "instruction": "分析用户输入，输出 JSON...",
    "input": "用户消息: '今天工作好累啊'\nfrustration: {...}",
    "output": json.dumps({
        "context": {...},
        "frustration_delta": {...},
        "drive_satisfaction": {...},
        "relationship_delta": 0.1, ...
    })
}
```

数据来源：
1. 当前系统运行日志中的 Critic 输出（云端大模型生成，作为 teacher）
2. 人工审核修正
3. 合成数据：基于 SCENARIOS 模板 + 随机 perturbation 批量生成

#### B3. 与 Genome 引擎的集成

```python
# chat_agent.py 中的条件切换
if self._local_critic_available:
    context, delta, rel, sat = await local_critic_sense(stimulus, ...)
else:
    context, delta, rel, sat = await critic_sense(stimulus, self.llm, ...)
```

---

### 方案 C：Realtime API 桥接（长期，架构重构）

**核心思路**：放弃自研的语音 pipeline，使用 OpenAI GPT-4o Realtime API 或 MiniMax Realtime API 作为底层语音对话引擎，在其之上叠加 Genome 的 personality 层。

#### C1. Realtime API 的优势

OpenAI GPT-4o Realtime API 内部实现了：
- 原生音频输入 → 音频输出
- 内部 VAD（自动检测语音起止）
- 内部 STT + LLM + TTS（端到端优化）
- 首音频延迟 **~250-400ms**
- 支持打断（用户说话时 AI 自动停止输出）

#### C2. Genome 引擎如何叠加

挑战：Realtime API 是黑盒端到端模型，不接受外部的 system prompt 实时修改（不像当前架构每轮都重新组装 prompt）。

可能的集成方式：

**方式 C2a：Session-level Personality Injection**
- 在 Realtime API session 初始化时，将 persona 身份 + genome_seed 的 drive_baseline 编码为自然语言描述
- 例如："你是一个 22 岁的 ENFP 女孩，非常活泼爱玩，联结需求很高..."
- **缺点**：丢失了 Genome v10 的**动态状态**（每轮变化的 signals、frustration、thermodynamic noise）

**方式 C2b：Realtime API + 旁路 Genome 引擎（推荐）**
- 用户语音 → Realtime API → 文本回复（低延迟）
- 同时，旁路运行 Genome 引擎：Critic 分析用户输入 → 更新 drive state → 生成 signals
- 将 signals 通过 Realtime API 的 `conversation.item.create` 注入为隐式上下文
- **复杂度极高**，Realtime API 不原生支持外部状态注入

**方式 C2c：仅用于语音层，保留 Genome 文本层**
- 语音输入 → STT → Genome 文本引擎 → 文本输出 → TTS → 语音输出
- 这就是**方案 A** 的完整形态
- 延迟不如原生 Realtime API，但保留了完整的 Genome personality

#### C3. 决策矩阵

| 维度 | 方案 A (Pipeline 优化) | 方案 B (本地 Critic) | 方案 C (Realtime API) |
|---|---|---|---|
| 首音频延迟 | 700-1000ms | 400-700ms | 250-400ms |
| Genome 完整性 | ✅ 完整保留 | ✅ 完整保留 | ⚠️ 部分丢失 |
| 实现复杂度 | 中 | 中高 | 高 |
| 运维成本 | 中 | 低（一次性 GPU） | 高（按秒付费） |
| 打断支持 | ❌ 需自建 | ❌ 需自建 | ✅ 原生支持 |
| 推荐优先级 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |

---

## 五、推荐的实施路径

### Phase 1：基础设施补齐（1-2 周）

1. **前端音频采集**
   - WebRTC `getUserMedia` 采集麦克风
   - `silero-vad` (wasm) 本地 VAD，检测语音起止
   - 语音片段通过 WebSocket `binary` 帧发送给后端

2. **后端 STT 接入**
   - 新增 `providers/speech/stt/` 模块
   - 支持本地 SenseVoice / 云端 Whisper API 双模式
   - STT 输出文本进入现有的 `ChatAgent.chat_stream()` 流程

3. **文本流式输出已就绪**
   - 当前 `chat_stream()` + `output_router.py` 已经可以流式返回文本
   - 前端只需将流式文本改为音频播放

### Phase 2：Sentence-Level 流式 TTS（1-2 周）

1. **修改 `output_router.py`**
   - 在流式输出中检测句子边界（。！？\n）
   - 每检测到一个完整句子，立即触发 `synthesize_voice`（异步）

2. **前端音频队列**
   - 维护一个音频片段播放队列
   - 按顺序播放，片段间无缝衔接（overlap-add 或简单预缓冲）

3. **验证延迟**
   - 测量"用户说完 → 首音频播放"的端到端延迟
   - 目标：< 1.5s（Phase 2 结束）

### Phase 3：Critic 轻量化（2-3 周）

1. **双 Critic 策略**
   - 新增轻量 Critic（gemini-flash / gpt-4o-mini）作为默认
   - 保留原 Critic 作为 fallback（轻量模型输出异常时回退）

2. **Critic 缓存**
   - SQLite / Redis 缓存 Critic 输出
   - 缓存 key：`hash(stimulus + frustration_snapshot + persona_id)`

3. **延迟验证**
   - 目标：< 1s（Phase 3 结束）

### Phase 4：本地 Critic（可选，4-6 周）

1. **数据收集**：运行 Phase 3 的轻量 Critic，收集 10k+ 条输出日志
2. **微调 7B 模型**：使用 QLoRA 在本地 GPU 上微调
3. **A/B 测试**：对比本地 Critic 和云端 Critic 的输出质量
4. **延迟验证**：目标 < 700ms

---

## 六、风险与注意事项

### 风险 1：流式 TTS 的语义断裂

按句子切分 TTS 可能导致语气不连贯（前一句开心，后一句突然严肃）。

**缓解**：在 sentence buffer 中保留前一句的最后一个词，作为下一句 TTS 的上下文（如果 provider 支持 emotion_instruction，可以传递上一句的情绪状态）。

### 风险 2：Critic 轻量化的质量下降

轻量模型（flash/mini）对 nuanced 情感的理解可能不如大模型。

**缓解**：
- A/B 测试驱动：收集用户满意度数据，量化质量差异
- 混合策略：简单输入用轻量 Critic，复杂/长输入用完整 Critic
- 定期用轻量 Critic 的输出和完整 Critic 做一致性校验

### 风险 3：音频播放的并发管理

如果用户打断 AI 说话，需要正确停止播放队列。

**缓解**：
- 前端维护 `AbortController` 或播放状态机
- 用户开始新说话时，清空播放队列，发送 `stop_audio` 信号给后端

---

## 七、总结

| 问题 | 结论 |
|---|---|
| 当前架构是否适用于流式语音对话？ | **不适用**。双 LLM 串行 + 整句 TTS 导致典型延迟 3s+ |
| 是否可以通过优化达标？ | **可以**。通过 Critic 轻量化 + sentence-level 流式 TTS，可将延迟压缩到 700ms-1s |
| 是否有更快路径？ | **Realtime API**（GPT-4o Realtime）可达 300ms，但会丢失 Genome 的动态 personality |
| 推荐方案 | **方案 A + B 的渐进式实施**：先补齐 STT/VAD + 流式 TTS，再逐步替换 Critic 为轻量模型 |

最终判断：**AiBeing 的 Genome v10 引擎设计上是"单用户深度对话"优先的，其 12 步生命周期的 richness（Critic → Genome → Actor → Hebbian）与"低延迟语音对话"存在天然的张力。最优策略不是完全放弃架构，而是通过"关键路径瘦身"（Critic 轻量化）+"流式管道改造"（sentence-level TTS）在保留 personality 深度的同时压缩延迟。**
