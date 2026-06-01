# AiBeing 开发者指南

> 版本: Genome v10 Hybrid | 更新日期: 2026-06-01
>
> 本文档面向**在 AiBeing 上开发/魔改的工程师**。它回答：如何搭建环境？如何调试？如何新增功能？
>
> 与 README 的区别：README 是"快速启动"，本文档是"深度开发手册"。

---

## 一、环境搭建

### 1.1 基础环境

```bash
# Python 3.11+ 必须
python3 --version

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 复制环境变量模板
cp .env.example .env
# 编辑 .env，填入你的 API keys
```

### 1.2 最小可运行配置

`.env` 中**最少**需要配置：

```bash
# 选择一个 LLM provider（至少填一个）
DEFAULT_PROVIDER=dashscope
DEFAULT_MODEL=qwen3-max
DASHSCOPE_API_KEY=sk-xxx

# 本地数据目录会自动创建，无需配置
```

**可选配置**（不影响核心功能）：

```bash
# TTS（需要语音输出时）
# OPENAI_API_KEY=sk-xxx

# EverMemOS 长期记忆（需要跨会话记忆时）
# EVERMEMOS_BASE_URL=https://api.evermind.ai
# EVERMEMOS_API_KEY=xxx
```

### 1.3 启动服务

```bash
# 方式 A：直接启动（开发推荐）
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 方式 B：使用脚本
chmod +x run.sh
./run.sh

# 方式 C：生产环境（无热重载）
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
```

**注意**：由于 Agent 状态存储在 SQLite（单文件），**不支持多 worker**（`--workers > 1` 会导致状态写入冲突）。水平扩展需要迁移到 PostgreSQL + Redis。

### 1.4 验证安装

```bash
# 1. 人格引擎测试
python tests/test_persona_engine.py

# 2. WebSocket E2E 测试（需先启动后端）
python tests/test_single_pass_e2e.py

# 3. 完整测试套件
pytest tests/ -v
```

---

## 二、项目结构速查

```
AiBeing/
├── main.py                    # FastAPI 入口 + 全局服务初始化
├── agent/
│   ├── chat_agent.py          # 核心：12 步生命周期 orchestrator
│   ├── prompt_builder.py      # Single-pass prompt 组装
│   ├── evermemos_mixin.py     # 长期记忆集成
│   ├── proactive.py           # 主动消息
│   ├── skills/                # 技能引擎实现
│   │   ├── task_skill_engine.py
│   │   ├── modality_skill_engine.py
│   │   └── tools/             # 具体工具实现
├── engine/
│   ├── genome/                # 人格引擎核心
│   │   ├── genome_engine.py   # Agent (NN + Hebbian)
│   │   ├── drive_metabolism.py
│   │   ├── critic.py
│   │   └── style_memory.py
│   ├── prompt_registry.py     # Prompt 模板管理
│   ├── state_store.py         # 状态持久化 (SQLite)
│   └── chat_log_store.py      # 聊天历史
├── persona/                   # 角色系统
│   ├── loader.py              # SOUL.md / SHELL.md 解析
│   ├── personas/              # 角色目录
│   └── generator.py           # 角色生成工具
├── providers/                 # Provider 适配器层
│   ├── llm/                   # LLM 客户端（8 家）
│   ├── media/tts_engine.py    # TTS 调度
│   ├── image/                 # 图像生成
│   └── memory/evermemos/      # 长期记忆客户端
├── memory/                    # 本地记忆层
│   ├── memory_store.py        # SQLite FTS5
│   └── soulmemory.py
├── skills/                    # 技能定义（SKILL.md）
│   ├── task/                  # 任务技能
│   ├── modality/              # 模态技能
│   └── manage/                # 管理技能
├── tests/                     # 测试套件
├── research/                  # 项目开发文档
│   ├── ROADMAP.md             # 路线图
│   ├── ARCHITECTURE.md        # 架构设计契约
│   ├── PRD.md                 # 产品需求
│   ├── DEVELOP.md             # 开发者指南
│   ├── CHANGELOG.md           # 变更日志
│   ├── guides/                # 操作指南（角色创建、技能引擎、TTS）
│   ├── analysis/              # 代码分析、审计（持续新增）
│   ├── benchmarks/            # 基准测试报告
│   ├── references/            # 外部参考、备忘
│   └── archive/               # 归档（过时的分析文档）
└── wechat_adapter.py          # 微信桥接器
```

---

## 三、开发工作流

### 3.1 分支策略

```
main          # 主分支，始终可部署
  ↓
feature/xxx   # 功能分支
  ↓
fix/xxx       # Bug 修复分支
  ↓
research/xxx  # 实验/研究分支（可选）
```

**规范**：
- 从 `main` 切出功能分支：`git checkout -b feature/calendar-skill`
- 提交信息遵循约定式提交（见下）
- 功能完成后直接合并到 `main`（当前项目规模小，无需 PR review 流程）
- **每次修改后立即推送**（`CLAUDE.md` 工作流约定）

### 3.2 提交信息规范

```
类型(范围): 简短描述

详细说明（可选）

Co-Authored-By: ...
```

**类型**：
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `refactor`: 重构（无行为变更）
- `test`: 测试相关
- `perf`: 性能优化
- `chore`: 构建/工具/依赖

**范围**：`agent`, `engine`, `persona`, `providers`, `skills`, `tests`, `docs`, `research`

**示例**：
```
feat(skills): add calendar-aware proactive skill

- Integrate with iCloud Calendar API
- Add proactive trigger for upcoming events
- Update ROADMAP.md

fix(evermemos): use millisecond timestamps for cloud API

Refs: analysis/everos-cloud-api-audit.md
```

### 3.3 调试配置（VS Code 示例）

`.vscode/launch.json`：

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "AiBeing Server",
      "type": "debugpy",
      "request": "launch",
      "module": "uvicorn",
      "args": ["main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
      "jinja": true,
      "env": { "PYTHONPATH": "${workspaceFolder}" }
    },
    {
      "name": "Test Persona Engine",
      "type": "debugpy",
      "request": "launch",
      "program": "${workspaceFolder}/tests/test_persona_engine.py",
      "console": "integratedTerminal"
    }
  ]
}
```

---

## 四、模块独立调试

### 4.1 只跑人格引擎（不启动 FastAPI）

```python
# debug_genome.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from persona import PersonaLoader
from engine.genome.genome_engine import Agent, SCENARIOS
from engine.genome.drive_metabolism import DriveMetabolism

loader = PersonaLoader("persona/personas")
personas = loader.load_all()
p = personas["luna"]

agent = Agent(seed=p.genome_seed, engine_params=p.engine_params)
metabolism = DriveMetabolism(engine_params=p.engine_params)

# 模拟 3 个场景预热
from engine.genome.genome_engine import simulate_conversation
simulate_conversation(agent, ["日常闲聊", "深夜心事", "分享喜悦"])

# 测试信号计算
ctx = {"user_emotion": 0.5, "topic_intimacy": 0.3, ...}  # 8D context
signals = agent.compute_signals(ctx)
print(signals)
```

### 4.2 只测试 Critic（感知器）

```python
# debug_critic.py
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from providers.llm import LLMClient
from engine.genome.critic import critic_sense

async def main():
    llm = LLMClient(provider="dashscope", model="qwen3-max")
    context, frust_delta, rel_delta, sat = await critic_sense(
        user_message="我今天好累",
        llm=llm,
        frustration_dict={"connection": 0.2, "novelty": 0.1, ...},
    )
    print("Context:", context)
    print("Frustration delta:", frust_delta)

asyncio.run(main())
```

### 4.3 只测试 Prompt Builder

```python
# debug_prompt.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from persona import PersonaLoader
from engine.genome.genome_engine import Agent
from agent.prompt_builder import PromptBuilderMixin

class MockAgent(PromptBuilderMixin):
    def __init__(self):
        loader = PersonaLoader("persona/personas")
        self.persona = loader.load_all()["luna"]
        self.agent = Agent(seed=self.persona.genome_seed)
        self.metabolism = None  # mock
        self._prev_signals = None
        self.trend_delta = 0.05

mock = MockAgent()
signals = {s: 0.5 for s in ["directness", "vulnerability", ...]}  # 8D
prompt = mock._build_single_prompt(few_shot="", signals=signals)
print(prompt)
```

### 4.4 只测试 Skill（不跑完整生命周期）

```python
# debug_skill.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.skills import TaskSkillEngine
from agent.skills.tool_registry import ToolRegistry
from agent.skills.tools.photo_tools import register_photo_tools

tool_registry = ToolRegistry()
register_photo_tools(tool_registry)

engine = TaskSkillEngine("skills/task", tool_registry=tool_registry)
engine.load_all()

# 直接调用 ReAct 循环
import asyncio
from providers.llm import LLMClient

async def main():
    llm = LLMClient(provider="dashscope", model="qwen3-max")
    result = await engine.react_loop("北京今天天气怎么样？", llm)
    print(result)

asyncio.run(main())
```

### 4.5 只测试 EverMemOS 客户端

```python
# debug_evermemos.py
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from providers.memory.evermemos.evermemos_client import EverMemOSClient

async def main():
    client = EverMemOSClient()
    print(f"Available: {client.available}")
    print(f"Is cloud: {client._is_cloud}")

    # 测试连接
    ok = await client.verify_connection()
    print(f"Connection OK: {ok}")

    # 测试存储（用假数据）
    await client.store_turn(
        user_id="test_user",
        persona_id="luna",
        persona_name="Luna",
        user_name="Test",
        group_id="",
        user_message="Hello",
        agent_reply="Hi there!",
    )

asyncio.run(main())
```

---

## 五、测试策略

### 5.1 测试金字塔

```
        ┌─────────┐
        │  E2E    │  test_single_pass_e2e.py (WebSocket 全链路)
        │  (慢)   │
       ┌┴─────────┴┐
       │ Integration│  test_skill_engine.py, test_chat_history.py
       │   (中)     │
      ┌┴────────────┴┐
      │    Unit       │  test_persona_engine.py (Genome 纯计算)
      │    (快)       │
      └───────────────┘
```

### 5.2 现有测试说明

| 测试文件 | 类型 | 测试内容 | 运行时间 |
|---------|------|---------|---------|
| `test_persona_engine.py` | Unit | PersonaLoader + Agent + DriveMetabolism | ~2s |
| `test_skill_engine.py` | Integration | TaskSkillEngine ReAct 循环 | ~5s |
| `test_single_pass_e2e.py` | E2E | WebSocket 全链路（需启动后端） | ~30s |
| `test_chat_history.py` | Integration | 聊天历史管理 | ~1s |
| `test_websocket.py` | Integration | WebSocket 协议 | ~5s |
| `test_recall_accuracy.py` | Integration | 记忆召回准确性 | ~10s |
| `test_genesis_migration.py` | Integration | 状态迁移 | ~3s |
| `test_bilingual_parser.py` | Unit | 双语解析器 | ~1s |

### 5.3 新增测试规范

**单元测试**（引擎逻辑、工具函数）：
```python
def test_crystallization_gate():
    agent = Agent(seed=42)
    # 设置已知状态
    agent.drive_state["connection"] = 0.9
    # 验证结晶条件
    assert should_crystallize(reward=0.8, context={"conflict_level": 0.0})
```

**集成测试**（需 mock LLM）：
```python
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_chat_agent_lifecycle():
    mock_llm = AsyncMock()
    mock_llm.chat.return_value = ChatMessage(role="assistant", content="monologue|reply|文字")

    agent = ChatAgent(persona=..., llm=mock_llm, ...)
    result = await agent.chat("Hello")
    assert result["reply"]
    assert agent._turn_count == 1
```

**E2E 测试**（需真实服务）：
```python
# 在 test_single_pass_e2e.py 模式上扩展
# 1. 启动后端
# 2. WebSocket 连接
# 3. 发送消息
# 4. 验证回复格式和事件顺序
```

**Mock 外部 API**：
```python
# 测试时绝不调用真实 LLM/EverMemOS
# 使用 unittest.mock 或 pytest-mock
```

### 5.4 测试缺口（待补充）

- [ ] `test_chat_agent.py` — ChatAgent 12 步生命周期端到端（mock LLM）
- [ ] `test_evermemos_client.py` — 云端/自托管双模式（mock httpx）
- [ ] `test_critic.py` — Critic 感知器输出格式验证
- [ ] `test_proactive.py` — 驱力阈值触发逻辑
- [ ] `test_style_memory.py` — KNN 检索和 Crystallization

---

## 六、性能分析

### 6.1 单轮延迟分解

典型单轮对话的延迟分布（以 Qwen3-Max 为例）：

| 阶段 | 耗时 | 占比 | 优化方向 |
|------|------|------|---------|
| Task Skill ReAct | 0-2s | 0-30% | 减少 tool call 次数 |
| Critic (LLM) | 0.5-1.5s | 15-25% | 使用更快的模型（如 qwen3-32b） |
| Single-Pass Actor (LLM) | 1-3s | 40-60% | 主瓶颈，模型选择最关键 |
| Modality Skill | 0-5s | 0-50% | TTS 并行化、图片生成异步化 |
| 本地计算 (Genome + Memory) | <10ms | <1% | 无需优化 |

**结论**：延迟几乎完全由 LLM 调用决定。优化单轮延迟 = 优化模型选择 + 减少不必要调用。

### 6.2 性能分析工具

```bash
# 1. 使用 cProfile 分析 Python 热点
python -m cProfile -o profile.stats main.py

# 2. 使用 py-spy 实时火焰图（不重启进程）
pip install py-spy
py-spy top --pid $(pgrep -f "uvicorn main:app")

# 3. 使用 austin（C 扩展采样，更精确）
brew install austin
austin -p $(pgrep -f "uvicorn main:app") | flamegraph.pl > flame.svg
```

### 6.3 常见性能问题

**问题 1: 首轮延迟高**
- 原因：角色预热（`simulate_conversation` 60 步）+ LLM 冷启动
- 解决：预热在 `startup()` 中完成，首轮用户无感知；如仍慢，减少预热步数

**问题 2: 内存泄漏**
- 原因：`ChatAgent` 实例长期持有，`_chat_history` / `signal_history` 无限增长
- 解决：`history` 已限制 `max_history=40`，`signal_history` 限制 200→100。检查新增列表是否有限制。

**问题 3: SQLite 写入瓶颈**
- 原因：高并发下 `StateStore.save_state()` 竞争
- 解决：当前设计是单用户，不应出现此问题。如扩展多用户，迁移到 PostgreSQL。

---

## 七、新增功能开发流程

以"新增一个天气感知的 proactive skill"为例：

### Step 1: 定义 SKILL.md

```yaml
---
name: weather_proactive
trigger: cron
schedule: "0 8 * * *"  # 每天早上 8 点
description: 根据天气主动提醒用户带伞或穿衣
parameters:
  location: string
---

当检测到下雨时，主动提醒用户带伞。
```

文件位置：`skills/task/weather_proactive/SKILL.md`

### Step 2: 实现工具函数

```python
# agent/skills/tools/weather_tools.py
async def get_weather_forecast(location: str) -> str:
    # 调用天气 API
    ...

def register_weather_tools(registry):
    registry.register("get_weather_forecast", get_weather_forecast)
```

### Step 3: 注册到引擎

```python
# main.py startup()
from agent.skills.tools.weather_tools import register_weather_tools
register_weather_tools(tool_registry)
```

### Step 4: 测试

```python
# tests/test_weather_proactive.py
@pytest.mark.asyncio
async def test_weather_proactive_trigger():
    mock_llm = AsyncMock()
    # ... 验证 proactive 在雨天触发
```

### Step 5: 更新文档

- `research/ROADMAP.md`：标记完成功能
- `research/CHANGELOG.md`：记录变更

---

## 八、常见问题

### Q: 修改了代码但热重载没生效？

`--reload` 只监视 `.py` 文件。如果修改了 `SOUL.md` 或 `SKILL.md`，需要手动重启。

### Q: 如何清空所有状态重新开始？

```bash
# 删除 SQLite 数据库
rm -rf .data/
# 重启服务
```

### Q: 为什么两个角色的回复风格差不多？

检查：
1. `genome_seed` 是否不同？（`persona.personas/{id}/SOUL.md`）
2. 是否经过了预热（`simulate_conversation`）？
3. `drive_baseline` 差异是否足够大？

### Q: 如何添加一个新的 LLM provider？

见 `ARCHITECTURE.md` 6.1 节。参考 `providers/llm/dashscope.py` 的实现模式。

### Q: 微信桥连接不上？

1. 确认 AiBeing 后端已启动（`http://localhost:8000`）
2. 确认微信桥已启动（`python wechat_adapter.py`）
3. 检查 `BRIDGE_API` 环境变量（默认 `http://localhost:9099`）
4. 查看 `wechat_adapter.py` 日志中的 `[ws]` 前缀消息
