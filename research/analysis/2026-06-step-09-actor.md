---
date: 2026-06-05
topic: Step 9 — Actor 生成（Single-Pass LLM Actor）
scope: agent/chat_agent.py Step 9, agent/parser.py:extract_reply
status: active
related: 2026-06-lifecycle-overview.md
---

> Actor 是 Genome 引擎的"表演者"。它接收 Step 8 构建的完整舞台指令（prompt），用 LLM 生成三段输出：内心独白（角色此刻的真实想法）、最终回复（角色说出口的话）、表达方式（文字/语音/照片/静默）。这是唯一一次调用 LLM 来生成回复，也是用户最终看到的输出来源。

---

## 一、业务场景

经过前面 8 个步骤的计算，Luna 的"舞台指令"已经准备好了。现在 LLM 需要扮演 Luna，根据这些指令生成回复。

**LLM 看到的 prompt（节选）**：

```
【角色】
Luna，22岁，female。

【舞台指令：角色当前状态】
🎯 直接度: 0.72 (0委婉→1直白)
💧 坦露度: 0.35 (0封闭→1袒露)
🎪 玩闹度: 0.81 (0正经→1调皮)
...

【舞台指令：角色内在需求】
🔗 联结: 0.78 (基线: 0.75, 渴望: 1.2)
...

【潜意识切片 1 [质量=3.2/5]】
【内心独白】他又说工作累了...
【最终回复】这次想聊聊具体发生了什么，还是只想安静地待一会儿？

【指令】
你就是这个角色。你有自己的生活、工作和心事。
先写出你此刻脑海中真实浮现的念头——像正在发生一样，不是描述情绪，而是情绪本身。
然后写出你实际说出口的话，和你选择的表达方式。

【输出格式】
【内心独白】
...
【最终回复】
...
【表达方式】
...
```

**LLM 输出**：

```
【内心独白】
他今天心情好像还不错？嘿嘿，那我要不要撒个娇逗逗他... 不对不对，先正经问一下他周末的安排。要是他说有空的话，我就...

【最终回复】
嘿嘿，周末有什么安排呀？要不要考虑和我一起去那个新开的展览？听说有超可爱的猫咪插画！

【表达方式】
文字
```

---

## 二、代码位置

```python
# chat_agent.py:366-375 (非流式)
single_messages = [ChatMessage(role="system", content=single_prompt)]
single_messages.extend(self.history[-self.max_history:])
single_messages.append(ChatMessage(role="user", content=user_message))

single_response = await self.llm.chat(single_messages)
monologue, reply, modality = extract_reply(single_response.content)

# chat_agent.py:620-635 (流式)
async for chunk in self.llm.chat_stream(single_messages):
    yield chunk
# Post-stream: extract_reply(raw_text)

# agent/parser.py
def extract_reply(raw: str) -> Tuple[str, str, str]:
```

---

## 三、详细执行流程

### 3.1 构建消息列表

```python
single_messages = [
    ChatMessage(role="system", content=single_prompt),  # 舞台指令
    ...  # 最多 40 轮历史
    ChatMessage(role="user", content=user_message),     # 当前用户输入
]
```

**为什么 system prompt 放最前面？**

LLM 的注意力机制对位置敏感。System message 放在最前面确保：
- 角色的身份和状态定义不会被历史对话稀释
- 即使历史很长，LLM 仍能"记住"自己是谁

**history 的修剪**：
- `max_history = 40`（默认）
- 只保留最近 40 轮，防止超出 LLM 上下文窗口
- 超出部分由 EverMemOS 的 episode_summary 补充

### 3.2 LLM 调用

```python
single_response = await self.llm.chat(single_messages)
```

**关键参数**：
- temperature：由 api.yaml 配置（默认 0.92，较高以增加创造性）
- max_tokens：默认 1024

**为什么是单次调用？**

Single-Pass Actor 的设计哲学：内心独白、回复、表达方式必须在**同一认知过程**中生成。如果分两次调用：
- Pass 1 生成独白 → Pass 2 根据独白生成回复
- 风险：Pass 2 可能"误解"Pass 1 的意图
- 延迟翻倍

单次调用确保独白和回复的一致性——独白是角色的真实想法，回复是角色选择说出口的话，两者应该自然关联。

### 3.3 输出解析

```python
monologue, reply, modality = extract_reply(single_response.content)
```

`extract_reply()` 在 `agent/parser.py` 中实现，处理三种可能的分隔符：

**中文格式**：
```
【内心独白】
...独白内容...
【最终回复】
...回复内容...
【表达方式】
...方式...
```

**英文格式**（fallback）：
```
[Inner Monologue]
...monologue...
[Final Reply]
...reply...
[Expression Mode]
...modality...
```

**解析逻辑**：
1. 用正则表达式匹配三个标记的位置
2. 提取标记之间的文本
3. 清理空白字符和动作描述（*顿了顿*、（沉默）等）
4. 如果缺少某个部分，使用智能默认值

### 3.4 解析容错

```python
def extract_reply(raw: str) -> Tuple[str, str, str]:
    # 尝试中文标记
    mono = _extract_between(raw, "【内心独白】", "【最终回复】")
    reply = _extract_between(raw, "【最终回复】", "【表达方式】")
    modality = _extract_after(raw, "【表达方式】")

    # Fallback：如果没有找到标记，整个文本作为回复
    if not reply:
        reply = raw.strip()
        mono = ""
        modality = "文字"

    # 清理动作标记
    reply = _clean_action_markers(reply)

    return mono, reply, modality
```

**为什么需要容错？**

LLM 可能不严格遵循格式：
- 忘记写【内心独白】
- 【表达方式】拼写错误
- 标记之间没有换行

容错确保即使 LLM "不听话"，系统也不会崩溃。

---

## 四、输出详解

### 4.1 内心独白（Monologue）

**作用**：
- 展示角色的真实想法（可能与回复不同）
- 为 Crystallization 提供内容（存的是独白+回复）
- 为 Debug 面板提供可视化数据

**设计约束**：
- "像正在发生一样，不是描述情绪，而是情绪本身"
- 禁止动作描述（*顿了顿*）—— 这些在 parser 中被清理

**示例**：
```
好想知道他在想什么... 算了直接问吧。
```

### 4.2 最终回复（Reply）

**作用**：角色实际说出口的话，用户看到的内容。

**与独白的区别**：
- 独白：真实想法（可能更直接、更脆弱）
- 回复：社交过滤后的表达（可能更委婉、更得体）

**示例**：
```
独白："他根本不在乎我，算了。"
回复："嗯... 那你忙吧，我不打扰你了。"
```

这种差异正是人格深度的体现。

### 4.3 表达方式（Modality）

可选值：
- `文字`：纯文本回复
- `语音`：生成语音消息
- `照片`：生成/发送照片
- `表情`：发送表情包
- `静默`：不说话
- 组合：`文字+语音`、`文字+照片`等

**Modality 的流转**：
```
Actor 输出 modality
    ↓
ModalitySkillEngine 解析并执行
    ↓
如果是语音 → 调用 synthesize_voice
如果是照片 → 调用 generate_selfie
如果是静默 → 不发送任何内容
```

---

## 五、流式 vs 非流式

### 5.1 流式（chat_stream）

```python
async def chat_stream(self, user_message: str) -> AsyncIterator[str]:
    async with self._turn_lock:
        # Steps 1-8 先执行（Critic, Metabolism, KNN, Prompt）
        # 然后流式调用 LLM
        async for chunk in self.llm.chat_stream(single_messages):
            yield chunk
```

**流程**：
1. 先执行 Steps 1-8（约 200-2000ms）
2. 发送 `"__FEEL_DONE__"` sentinel 给前端（开始显示 typing 指示器）
3. 流式接收 LLM chunk，逐字转发给前端
4. 流结束后，解析完整输出

**前端体验**：
- 用户发送消息后，先等待"思考"（Critic + Prompt 构建）
- 看到 typing 指示器
- 看到回复逐字出现（类似 ChatGPT 的打字效果）

### 5.2 非流式（chat）

```python
async def chat(self, user_message: str) -> dict:
    async with self._turn_lock:
        result = await self._chat_inner(user_message)
        return result
```

**前端体验**：
- 用户发送消息后，等待完整回复
- 一次性显示完整内容
- 适合 REST API 调用（如 WeChat 适配器）

---

## 六、与后续步骤的关系

```
Step 9 输出: monologue, reply, modality
    ├──→ 返回给用户（reply）
    ├──→ Step 10 (Hebbian): context, reward, drive_satisfaction → learn
    ├──→ Step 4 (下一轮): self._last_action = {context, monologue, reply, ...}
    └──→ Step 11 (Async): 存储到 EverMemOS
```

---

## 七、必要性论证

### 如果没有 Actor：

1. **无回复生成**：前面的所有计算（signals、KNN、prompt）都没有出口
2. **无表达载体**：LLM 是角色与用户的唯一沟通渠道
3. **无格式约束**：没有【内心独白】/【最终回复】/【表达方式】的结构，输出混乱

### 为什么是 LLM 而不是规则引擎？

规则引擎的问题：
- 无法处理自然语言的复杂性
- 无法生成流畅、有情感的文本
- 无法根据 subtle 的信号变化调整语气

LLM 的优势：
- 理解"舞台指令"中的数值含义（0.81 玩闹度 ≈ 俏皮撒娇的语气）
- 生成人类水平的自然语言
- 在 few-shot 示例的引导下保持风格一致性

**LLM 在这里不是"智能来源"，而是"表达工具"**。真正的"智能"（状态计算、学习、记忆）在 Genome 引擎中完成，LLM 只是把这些内部状态翻译成人类语言。

---

## 八、总结

> Step 9 是角色的"登台表演"。LLM 作为演员，根据 Step 8 准备的舞台指令（身份、信号、 few-shot、记忆）生成内心独白、最终回复和表达方式。Single-Pass 设计确保独白和回复的一致性，解析器的容错处理确保即使 LLM 不严格遵循格式也能正常工作。这是整个 12 步生命周期中用户唯一直接感知的步骤——前面的 8 步都是"后台准备"，Step 9 才是"前台呈现"。
