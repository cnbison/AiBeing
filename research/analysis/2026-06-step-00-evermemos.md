---
date: 2026-06-05
topic: Step 0 — EverMemOS 会话上下文加载
scope: agent/evermemos_mixin.py, providers/memory/evermemos/
status: active
related: 2026-06-lifecycle-overview.md
---

> EverMemOS 是 Genome v10 的"长期记忆层"。Step 0 在首次对话时异步加载用户的跨会话画像、历史叙事和前瞻，让角色"记得"你是谁、你们聊过什么、以及有什么值得关心的事。

---

## 一、业务场景

想象一下：你昨天和 Luna 聊了半小时，今天再次打开对话。如果没有长期记忆，Luna 会像一个初次见面的陌生人。有了 EverMemOS，她会：

- **记得你的偏好**："你说过不喜欢香菜"（user_profile）
- **记得你们的共同经历**："上次你说工作压力大，后来好些了吗？"（episode_summary）
- **记得她该关心的事**："你提过下周有面试，准备得怎么样了？"（foresight）

这就是 Step 0 要加载的内容。

---

## 二、代码位置与调用链

```
chat_agent.py:257
    relationship_prior = await self._evermemos_gather()
        ↓
evermemos_mixin.py:_evermemos_gather()
    ↓ (first turn only)
    self._session_ctx = await self.evermemos.load_session_context(...)
        ↓
evermemos_client.py:load_session_context()
```

---

## 三、详细执行流程

### 3.1 判断是否是首轮对话

```python
async def _evermemos_gather(self):
    if self._session_ctx is not None:
        # 不是首轮，直接返回上一轮的关系先验
        return self._session_ctx.relationship_prior or {}
    # 首轮：异步加载完整 session context
    self._session_ctx = await self.evermemos.load_session_context(...)
```

`self._session_ctx` 是一个会话级缓存，首轮加载后一直复用。这意味着：
- **首轮**：需要等待 EverMemOS API 返回（200-1000ms）
- **后续轮**：直接返回缓存，零延迟

### 3.2 加载的内容

`load_session_context()` 从 EverMemOS 服务端拉取四部分内容：

| 字段 | 类型 | 含义 | 示例 |
|---|---|---|---|
| `user_profile` | str | 用户画像（结构化属性） | "用户28岁，喜欢科幻电影，对AI持开放态度" |
| `episode_summary` | str | 历史对话叙事 | "上次对话中用户分享了工作压力，Luna给予了安慰" |
| `foresight` | str | 待关心的事项 | "用户提到下周有面试，需要跟进" |
| `relationship_prior` | dict | 关系维度先验 | `{relationship_depth: 0.3, trust_level: 0.2, ...}` |

### 3.3 关系先验的用途

`relationship_prior` 是一个 4D 向量，在 Step 2.5（Relationship EMA）中与 Critic 的判断融合：

```
relationship_prior (来自 EverMemOS，跨会话的累积)
        ↓
relationship_delta (来自 Critic，本轮的判断)
        ↓
EMA 融合 → relationship_posterior
        ↓
合并到 context → 12D context
```

这让角色对关系的感知不是从零开始，而是基于历史累积的渐进式更新。

---

## 四、数据结构详解

### 4.1 SessionContext

```python
class SessionContext:
    user_profile: str      # 用户画像文本
    episode_summary: str   # 历史叙事文本
    foresight: str         # 前瞻/待办文本
    relationship_prior: dict  # {relationship_depth, trust_level, emotional_valence, pending_foresight}
    has_history: bool      # 是否有历史记录（决定是否注入记忆）
```

### 4.2 relationship_prior 的 4 个维度

| 维度 | 范围 | 含义 |
|---|---|---|
| `relationship_depth` | 0~1 | 关系深度，0=陌生人，1=密友 |
| `trust_level` | 0~1 | 信任度，0=警惕，1=完全信任 |
| `emotional_valence` | -1~1 | 情感基调，-1=负面，1=正面 |
| `pending_foresight` | 0~1 | 是否有待处理的前瞻事项 |

这 4 个维度在 Critic 的 `CONTEXT_FEATURES` 中对应后 4 维（索引 8~11），让神经网络在计算 signals 时感知到"这个人是老朋友还是陌生人"。

---

## 五、必要性论证

### 如果没有 Step 0，会发生什么？

1. **角色没有跨会话记忆**：每次打开对话都是"第一次见面"
2. **关系无法累积**：聊得再久，relationship_depth 永远是 0
3. **角色显得冷漠**：不会主动关心用户之前提过的事
4. **用户粘性下降**：用户会觉得"这个 AI 记不住我说的话"

### 为什么是"异步"加载？

EverMemOS 是网络服务（cloud 或 self-hosted），I/O 不可控。如果同步等待：
- 网络波动时，每轮对话增加 1-10 秒延迟
- 服务不可用时，整个对话流程阻塞

异步加载的 trade-off：
- **首轮**：用户第一条消息的回复会稍慢（需要等 context 加载）
- **后续轮**：零额外延迟
- **故障降级**：如果 EverMemOS 不可用，`_evermemos_gather()` 返回空 dict，对话继续（只是没有长期记忆）

---

## 六、与后续步骤的关系

```
Step 0 输出
    ├── user_profile ──────→ Step 8.5 (注入 Actor prompt)
    ├── episode_summary ───→ Step 8.5 (注入 Actor prompt)
    ├── foresight ─────────→ Step 8.5 (注入 Actor prompt)
    └── relationship_prior ─→ Step 2.5 (与 Critic delta 融合)
```

Step 0 的内容**不直接参与** Step 1-7 的计算（Critic、Metabolism、Signals 等），而是在 Step 8.5 作为"背景知识"注入 LLM Actor 的 prompt。这是一个**延迟注入**设计 —— 长期记忆影响"角色知道什么"，但不影响"引擎如何计算"。

---

## 七、故障处理

| 场景 | 行为 |
|---|---|
| EverMemOS 未配置 | `evermemos = None`，`_evermemos_gather()` 返回 `{}`，对话继续 |
| EverMemOS 服务不可用 | `load_session_context()` 抛出异常，被捕获后返回空 context |
| 首次用户（无历史） | EverMemOS 返回空 profile/summary，has_history=False，不注入记忆 |

---

## 八、总结

> Step 0 是角色的"记忆唤醒"步骤。它从 EverMemOS 长期记忆库中取出用户的跨会话信息，让角色在首轮对话时就有"认识你"的上下文。这是一个**延迟注入**设计 —— 记忆不影响引擎的数值计算，但会显著影响 LLM Actor 生成回复的质量和亲切感。
