# EverMemOS 云端 API 审计报告

**日期**: 2026-06-01  
**审计对象**: `providers/memory/evermemos/evermemos_client.py` 云端模式  
**对照文档**: `research/EverOS-API.md`

---

## 1. 时间戳单位严重不匹配（严重）

**文档示例** (`research/EverOS-API.md:31`)：
```json
"timestamp": 1736935200000
```
这是 **13 位毫秒级** Unix 时间戳（对应 `2025-01-15 10:00:00 UTC`）。

**代码实现** (`evermemos_client.py:257-258`)：
```python
def _now_ts(self) -> int:
    return int(time.time())
```
`time.time()` 返回 **秒级浮点数**（截断后为 10 位整数）。

**影响**：服务端将所有对话时间戳解析为 `1970-01-19` 左右。记忆的时序排序、Session 时间窗口过滤、以及基于时间的去重逻辑全部失效。这是**最可能导致服务端异常或静默丢弃数据的问题**。

---

## 2. `messages` 数组缺少 `sender_name`

**文档要求**：每条 message 包含 `sender_name` 字段。

```json
{
  "role": "user",
  "sender_name": "Demo User",
  "timestamp": ...,
  "content": "..."
}
```

**代码** (`evermemos_client.py:592-595`) `_store_turn_cloud` 只构造了 `role`/`content`/`timestamp`：
```python
messages = [
    {"role": "user", "content": user_message, "timestamp": ts},
    {"role": "assistant", "content": agent_reply, "timestamp": ts + 1},
]
```

如果 EverOS 后端依赖 `sender_name` 做用户画像提取或消息归属分析，缺失会导致提取质量下降。

---

## 3. Session 初始加载用错了接口（设计不当）

**文档** 提供了两个查询端点：

- `POST /api/v1/memories/search` — 语义/向量检索，需要 `query` 参数
- `POST /api/v1/memories/get` — 直接按 `user_id` / `memory_type` / `session` 过滤拉取

**代码** (`evermemos_client.py:346-349`) `_load_session_context_cloud` 用 `search` 接口并传 **空 query**：
```python
resp = await self._client.post(
    "/api/v1/memories/search",
    json={"query": "", "filters": filters},
)
```

`search` 接口的设计是 *"根据 query text 找最相关的记忆"*。空 query 的语义未在文档中定义，服务端行为不确定：
- 可能返回空结果，导致每次 session 都误判为新用户
- 可能返回 400 Bad Request，触发 circuit breaker
- 可能全量返回但性能极差

**正确做法**：Session 初始加载应改用 `POST /api/v1/memories/get`，按 `memory_type` 分批拉取 `profile` / `episodic_memory` / `event_log`。

---

## 4. `verify_connection` 同样使用空 query

```python
resp = await self._client.post(
    "/api/v1/memories/search",
    json={"query": "", "filters": {"user_id": "__healthcheck__"}},
)
```

如果服务端对空 query 返回非 200，初始化阶段就会误判 API 不可用或打印误导性错误日志。

---

## 5. 返回数据结构假设缺乏文档支撑

`_load_session_context_cloud` (`line 356-360`) 和 `_search_cloud` (`line 818-821`) 假设返回结构为：

```python
data = resp.json().get("data", {})
profiles = data.get("profiles", [])
episodes = data.get("episodes", [])
raw_messages = data.get("raw_messages", [])
agent_memory = data.get("agent_memory", {})
```

文档只给出了请求示例，**没有给出响应 schema**。如果实际返回的字段名不同（例如 `episodes` vs `episodic_memories`，或 `raw_messages` vs `messages`），解析会全部返回空列表，表现为"记忆丢失"。

---

## 修改建议

### 立即修复（高优先级）

#### 1. 时间戳改为毫秒级

```python
def _now_ts(self) -> int:
    return int(time.time() * 1000)  # 毫秒级
```

#### 2. `_load_session_context_cloud` 改用 `memories/get` 接口

```python
async def _load_session_context_cloud(self, user_id: str, group_id: str) -> SessionContext:
    body = {
        "memory_type": "episodic_memory",  # 或分批调用多个 type
        "page": 1,
        "page_size": 20,
        "filters": {"user_id": user_id}
    }
    if group_id:
        body["filters"]["group_id"] = group_id

    resp = await self._client.post(
        "/api/v1/memories/get",
        json=body,
        timeout=_CFG["load_timeout_sec"],
    )
    # ... 解析逻辑根据实际响应 schema 调整
```

如果需要同时拉取 profile、episodes、facts，建议并发调用多个 `get`（分别带不同的 `memory_type`），比空 query 的 `search` 更精确可靠。

#### 3. `verify_connection` 改用 `memories/get`

```python
resp = await self._client.post(
    "/api/v1/memories/get",
    json={
        "memory_type": "profile",
        "page_size": 1,
        "filters": {"user_id": "__healthcheck__"}
    },
    timeout=8.0,
)
```

#### 4. `_store_turn_cloud` 补上 `sender_name`

```python
messages = [
    {"role": "user", "sender_name": user_name, "content": user_message, "timestamp": ts},
    {"role": "assistant", "sender_name": persona_name, "content": agent_reply, "timestamp": ts + 1},
]
```

---

## 诊断建议

如果日志中能复现 "fetch failed"，建议临时开启详细日志，确认失败时的具体信息：

1. **HTTP status code**：是 400/500（服务端拒绝）还是网络层超时
2. **响应 body**：服务端通常会对空 query 或格式错误给出具体原因
3. **具体接口**：定位是 `store_turn`（存储失败）、`load_session_context`（加载失败）还是 `search`（检索失败）

**经验判断**：
- 如果 `store_turn` 返回 400，极大概率是**时间戳单位问题**
- 如果 `load_session_context` 返回空或异常，极大概率是**空 query search 不被支持**
