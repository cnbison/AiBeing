# EverMemOS 云端 API 审计与迁移报告

> **日期**: 2026-06-02
> **审计对象**: `providers/memory/evermemos/evermemos_client.py` 云端模式
> **状态**: 全部问题已修复（代码已基于 everos SDK v0.4.0 重写）

---

## 背景：版本升级导致的两套 API

在修复过程中发现，EverMemOS 存在**两套完全不同的 API**：

| | 旧版 | 新版 |
|---|---|---|
| **Python SDK** | `evermemos>=0.1.0` (v0.3.13) | `everos>=0.4.0` |
| **API 版本** | v0 | **v1** |
| **存储格式** | 单条 `content` + `create_time` (ISO) | 批量 `messages[]` + `timestamp` (ms) |
| **搜索方法** | `GET /api/v0/memories/search` | `POST /api/v1/memories/search` |
| **获取方法** | `GET /api/v0/memories` | `POST /api/v1/memories/get` |
| **鉴权环境变量** | `EVERMEMOS_API_KEY` | `EVEROS_API_KEY` |

我们的旧代码基于手写的 httpx 客户端，参考的是 `research/references/EverOS-API.md`（描述 v1 API），但实际安装的却是 `evermemos` 包（v0 SDK）。这种**SDK 版本与 API 文档不匹配**是导致 `fetch failed` 的根本原因。

---

## 已修复问题清单

### 1. 时间戳单位错误（已修复）

**旧代码**（v0 手写客户端）：
```python
def _now_ts(self) -> int:
    return int(time.time())  # 秒级 ❌
```

**新代码**（v1 SDK）：
```python
def _now_ms(self) -> int:
    return int(time.time() * 1000)  # 毫秒级 ✅
```

everos SDK 的 `MessageItemParam.timestamp` 明确要求 `Required[int]`（毫秒级）。

### 2. sender 标识缺失（已修复）

**旧代码**：messages 中只有 `role`/`content`/`timestamp`，没有 sender 标识。

**新代码**：每条 message 包含 `sender_id`：
```python
{"role": "user", "content": user_message, "timestamp": ts, "sender_id": user_id}
{"role": "assistant", "content": agent_reply, "timestamp": ts + 1, "sender_id": persona_id}
```

> 注：参考文档写的是 `sender_name`，但 everos SDK 源码定义为 `sender_id: Optional[str]`。以 SDK 源码为准。

### 3. Session 加载误用 search 接口（已修复）

**旧代码**：用 `POST /api/v1/memories/search` + 空 query 全量拉取。

**新代码**：用 `client.v1.memories.get(memory_type="...", filters={"user_id": uid})` 分批拉取：
- `memory_type="profile"` → 用户画像
- `memory_type="episodic_memory"` → 情节记忆
- `memory_type="agent_case"` → 案例
- `memory_type="agent_skill"` → 技能

### 4. verify_connection 误用 search（已修复）

**旧代码**：`search(query="", filters={"user_id": "__healthcheck__"})`

**新代码**：`get(memory_type="profile", filters={"user_id": "__healthcheck__"}, page_size=1)`

### 5. close_session 无实际操作（已修复）

**旧代码**：云端模式下仅打印日志，无实际操作。

**新代码**：调用 `client.v1.memories.flush(user_id=..., session_id=...)` 触发边界检测和记忆提取。

### 6. 返回数据结构不匹配风险（已消除）

**旧代码**：手写 `resp.json().get("data", {})` 解析，字段名假设缺乏保障。

**新代码**：通过 everos SDK 的类型化响应对象访问：
```python
resp = await client.v1.memories.get(...)
data = resp.data  # GetMemResponse 对象
data.episodes     # List[EpisodeItem]
data.profiles     # List[ProfileItem]
data.agent_cases  # List[AgentCaseItem]
data.agent_skills # List[AgentSkillItem]
```

---

## 架构变更：手写 httpx → 官方 SDK

### Cloud 模式（evermind.ai）

```python
from everos import AsyncEverOS

self._client = AsyncEverOS(
    api_key=self._api_key,
    base_url=self._base_url,  # e.g. https://api.evermind.ai
)

# 存储
await self._client.v1.memories.add(
    messages=[...],
    user_id=user_id,
    session_id=group_id,
)

# 获取
await self._client.v1.memories.get(
    memory_type="episodic_memory",
    filters={"user_id": user_id},
    page=1,
    page_size=20,
)

# 搜索
await self._client.v1.memories.search(
    query=query,
    filters={"user_id": user_id},
    top_k=20,
)

# 刷新
await self._client.v1.memories.flush(
    user_id=user_id,
    session_id=group_id,
)
```

### Self-hosted 模式

保留原有 httpx 客户端（v0 API），确保向后兼容。

---

## 依赖变更

```diff
# requirements.txt
- evermemos>=0.1.0
+ everos>=0.4.0
```

### 环境变量

| 用途 | 旧版 | 新版 |
|---|---|---|
| API Key | `EVERMEMOS_API_KEY` | `EVEROS_API_KEY`（优先）或 `EVERMEMOS_API_KEY`（兼容） |
| Base URL | `EVERMEMOS_BASE_URL` | `EVERMEMOS_BASE_URL`（优先）或 `EVER_OS_BASE_URL`（SDK 原生） |

代码中同时读取两套环境变量以兼容过渡：
```python
self._api_key = api_key or os.environ.get("EVERMEMOS_API_KEY") or os.environ.get("EVEROS_API_KEY")
```

---

## 遗留注意事项

1. **自托管版本兼容性**：自托管 EverMemOS 仍使用 v0 API（单条存储 + GET 搜索）。代码保留双模式分支，自托管走原有 httpx 实现。
2. **session_id vs group_id**：v1 SDK 使用 `session_id`，v0 使用 `group_id`。代码中将 `group_id` 映射为 `session_id` 传入 SDK。
3. **_load_memory_config 中的 base_url**：`memory_config.yaml` 中的 `base_url` 不应包含 `/api/v0` 或 `/api/v1` 后缀，因为 SDK 会自动拼接版本路径。

---

## 验证命令

```bash
# 检查 .venv 中是否正确安装 everos
ls .venv/lib/python3.13/site-packages/ | grep everos

# 验证导入
python -c "from everos import AsyncEverOS; print('OK')"

# 验证客户端能正常初始化（无需真实 API key，仅检查导入和初始化逻辑）
python -c "
import sys; sys.path.insert(0, '.')
from providers.memory.evermemos.evermemos_client import EverMemOSClient
print('Import OK')
"
```
