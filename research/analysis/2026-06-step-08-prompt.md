---
date: 2026-06-05
topic: Step 8 & 8.5 — Prompt 构建与记忆注入
scope: agent/prompt_builder.py:_build_single_prompt, chat_agent.py Step 8.5
status: active
related: 2026-06-lifecycle-overview.md
---

> Prompt 构建是 Genome 引擎的"舞台布景"。它将角色的身份、内心状态（信号）、潜意识回忆（few-shot）和用户特定记忆（profile/episode）组装成一个完整的"表演指令"，让 LLM 知道"此刻我是谁、我处于什么状态、我应该怎么说话"。

---

## 一、业务场景

想象 Luna 要上台表演。在登台前，导演给了她一份完整的"表演简报"：

```
【角色身份】
你是 Luna，22岁，自由插画师...

【当前状态】
🎯 直接度: 0.35 (委婉→直白)
💧 坦露度: 0.65 (封闭→袒露)
🎪 玩闹度: 0.45 (正经→调皮)
...（8D signals）

【内在需求】
🔗 联结: 0.78 (基线: 0.75, 渴望: 1.2)
...

【潜意识回忆】
--- 潜意识切片 1 [质量=3.2/5] ---
【内心独白】他又说工作累了...
【最终回复】这次想聊聊具体发生了什么...

【关于你的偏好】
用户28岁，喜欢科幻电影...

【与你过去发生的事】
上次对话中用户分享了工作压力...

【近期值得关心】
用户提到下周有面试...
```

这份简报就是 single_prompt。LLM 根据它生成 Luna 的独白、回复和表达方式。

---

## 二、代码位置

```python
# chat_agent.py:327-329
single_prompt = self._build_single_prompt(
    few_shot, noisy_signals,
    modality_skill_engine=self.modality_skill_engine,
)

# chat_agent.py:332-362 (Step 8.5)
if self._session_ctx and self._session_ctx.has_history:
    await self._collect_search_results()
    # profile/episode/foresight injection

# prompt_builder.py:17-95
def _build_single_prompt(self, few_shot: str, signals: dict, ...):
```

---

## 三、Step 8：Prompt 构建

### 3.1 身份锚定

```python
identity = f"【角色】\n{persona.name}"
if persona.age:
    identity += f"，{persona.age}岁"
if persona.gender:
    identity += f"，{persona.gender}"
```

输出：`【角色】
Luna，22岁，female。`

**设计原则**：极简身份，不注入性格描述。性格由 genome_seed 和信号决定，不是 prompt 写死的。

### 3.2 信号注入

```python
signal_injection = self.agent.to_prompt_injection_from_signals(
    signals,
    signal_overrides=self.persona.signal_overrides,
    frustration=self.metabolism.frustration,
    lang=self.persona.lang,
)
```

输出（已在上篇文档详述）：
```
【舞台指令：角色当前状态】
🎯 直接度: 0.35 (0委婉→1直白)
💧 坦露度: 0.65 (0封闭→1袒露)
...

【舞台指令：角色内在需求】
🔗 联结: 0.78 (基线: 0.75, 渴望: 1.2)
...
```

### 3.3 趋势注入

```python
if self._prev_signals:
    for sig in SIGNALS:
        delta = signals[sig] - self._prev_signals.get(sig, 0.5)
        if abs(delta) > self.trend_delta:  # 默认 0.15
            trend_lines.append(
                f"- {label}明显{direction} ({prev:.2f} → {curr:.2f})"
            )
```

如果某信号变化超过阈值，追加趋势提示：
```
【变化趋势】
- 🎪 玩闹度明显下降 (0.85 → 0.45)
- ⚡ 倔强度明显上升 (0.15 → 0.55)
```

**作用**：帮助 LLM 感知动态转变——角色"突然变了"。

### 3.4 时间戳

```python
signal_injection += f"\n\n【当前时间】{now.strftime('%Y年%m月%d日')} {now.strftime('%H:%M')}"
```

让角色感知当前时间，影响时间相关的行为（深夜更私密、清晨更活泼）。

### 3.5 Prompt 模板渲染

```python
template_name = "actor_single"
rendered = render_prompt(
    template_name,
    few_shot=few_shot,
    signal_injection=combined_injection,
)
```

模板 (`engine/prompts/actor_single.md`)：
```markdown
[角色参考]
以下是你在相似情境下的感受和说话方式：

$few_shot

$signal_injection

[指令]
你就是这个角色。你有自己的生活、工作和心事。
先写出你此刻脑海中真实浮现的念头——像正在发生一样...
...

[输出格式]
【内心独白】
...
【最终回复】
...
【表达方式】
...
```

### 3.6 Modality Skill 注入

```python
if modality_skill_engine:
    skill_prompt = modality_skill_engine.build_prompt()
    if skill_prompt:
        rendered += "\n\n" + skill_prompt
```

追加可用的表达方式技能说明（语音、照片、拆分消息等）。

---

## 四、Step 8.5：记忆注入

### 4.1 条件判断

```python
if self._session_ctx and self._session_ctx.has_history:
    await self._collect_search_results()
```

只有首轮加载了 session context 且有历史记录时，才注入记忆。

### 4.2 动态预算

```python
profile_budget, episode_budget = self._memory_injection_budget(context)

def _memory_injection_budget(self, context: dict) -> tuple:
    depth = context.get('conversation_depth', 0.0)
    intimacy = context.get('topic_intimacy', 0.0)
    t = max(depth, intimacy)
    profile_budget = int(200 + 600 * t)   # 200~800 字符
    episode_budget = int(150 + 450 * t)   # 150~600 字符
    return profile_budget, episode_budget
```

**设计逻辑**：
- 浅层闲聊：最小化记忆注入（减少干扰）
- 深度对话：最大化记忆注入（增加上下文相关性）

### 4.3 混合注入

```python
profile_text = self._blend_injection(self._relevant_facts, self._user_profile, profile_budget)
episode_text = self._blend_injection(self._relevant_episodes, self._episode_summary, episode_budget)
```

**混合策略**：
- 如果只有 relevant（无 static）：用 relevant 填满预算
- 如果只有 static（无 relevant）：用 static
- 如果都有：80% relevant + 20% static

**为什么保留 20% static？**

确保即使 relevant 搜索结果非常聚焦（如只找到一条关于"工作压力"的记忆），用户的长程 profile 仍然会被注入。防止"记忆隧道效应"——角色只记得最近搜索到的事，忘记了用户的整体画像。

### 4.4 Prompt 追加

```python
single_prompt += f"\n\n[关于{name}的偏好] {profile_text}"
single_prompt += f"\n\n[与{name}过去发生的事] {episode_text}"
single_prompt += f"\n\n[近期值得关心] {self._foresight_text}"
```

最终 single_prompt 结构：

```
[角色参考]
（few_shot 潜意识切片）

（身份 + 信号注入 + 趋势 + 时间）

[指令]
（表演指令 + 输出格式）

（Modality Skill 说明）

[关于你的偏好] ...
[与你过去发生的事] ...
[近期值得关心] ...
```

---

## 五、Prompt 大小估算

| 部分 | 典型长度 | 说明 |
|---|---|---|
| few_shot (3 slices) | 300-600 tokens | 取决于历史回复长度 |
| 信号注入 | 200-300 tokens | 固定格式 |
| 指令 + 输出格式 | 150-200 tokens | 固定模板 |
| Modality skills | 100-200 tokens | 取决于加载的技能数 |
| Profile injection | 100-400 tokens | 动态预算 |
| Episode injection | 75-300 tokens | 动态预算 |
| **总计** | **925-2000 tokens** | 主要在 system prompt |

**注意**：加上 user_message 和 history（最多 40 轮），总上下文可能达到 4k-8k tokens。

---

## 六、与后续步骤的关系

```
Step 8 输出: single_prompt (str)
    ↓
Step 9 (Actor): single_prompt 作为 system message
    messages = [system(single_prompt)] + history[-40:] + user(user_message)
    llm.chat(messages) → raw_response
```

single_prompt 是 LLM 的唯一 system message。它包含了角色表演所需的全部信息：身份、状态、记忆、风格示范、输出格式。

---

## 七、必要性论证

### 如果没有 Step 8/8.5：

1. **LLM 无状态感知**：不知道角色的当前 drive state、frustration、signals
2. **无风格一致性**：没有 few-shot 示范，每轮风格可能完全不同
3. **无长期记忆**：角色记不住用户是谁、聊过什么
4. **输出格式混乱**：没有明确的格式指令，LLM 可能不生成独白/表达方式

### 为什么是 Single-Pass？

早期版本使用 Two-Pass：
- Pass 1: 生成独白
- Pass 2: 根据独白生成回复

问题：两次 LLM 调用 = 2x 延迟 + 2x 成本。

Single-Pass 的设计：
- 一次调用生成独白 + 回复 + 表达方式
- 通过输出格式指令约束 LLM 的结构化输出
- 延迟减半，一致性更好（独白和回复由同一上下文生成）

---

## 八、总结

> Step 8 和 8.5 是角色的"登台准备"。Step 8 组装核心表演指令（身份 + 信号 + few-shot + 格式），Step 8.5 追加用户特定的背景知识（画像 + 历史 + 前瞻）。最终的 single_prompt 是 LLM Actor 的全部舞台指导——它告诉 LLM "此刻你是谁、你处于什么状态、你应该怎么说话、你过去是怎么回应的"。这是连接 Genome 引擎（内部状态计算）和 LLM（外部表达生成）的桥梁。
