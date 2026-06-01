# AiBeing 变更日志

> 格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，版本号采用 `主版本.次版本.修订号`。
>
> 主版本：架构级重构或产品方向变更
> 次版本：功能里程碑（对应 ROADMAP 阶段）
> 修订号：Bug 修复和文档更新

---

## [Unreleased]

### Added
- 建立项目级文档体系：`ROADMAP.md`、`ARCHITECTURE.md`、`DEVELOP.md`、`PRD.md`、`CHANGELOG.md`

### Fixed
- **文档**: 修正 README/ README_EN 中 EverMemOS 云端 `EVERMEMOS_BASE_URL` 配置（去掉 `/v1` 后缀，避免与客户端自动拼接冲突）

### Known Issues
- EverMemOS 云端 API 时间戳单位为秒级，服务端期望毫秒级（见 `analysis/everos-cloud-api-audit.md`）
- EverMemOS 云端 `sender_name` 字段缺失
- Session 初始加载误用 `search` 接口（空 query），应改用 `memories/get`

---

## [0.5.0] - 2026-05-27

### 初始版本（Fork 自 OpenHer）

AiBeing 从 OpenHer  fork，基于 **Genome v10 Hybrid** 引擎。

### 已包含的核心功能

- **人格涌现引擎**: 25D→24D→8D 随机神经网络，Hebbian 学习，frustration 相变
- **情绪热力学**: 5 维驱力系统（connection/novelty/expression/safety/play），时间感知代谢
- **12 步对话生命周期**: Task Skill → Critic → Metabolism → Crystallization → Single-Pass Actor → Hebbian Learning → Memory Storage
- **三层记忆架构**:
  - 风格记忆：SQLite KNN 检索
  - 本地事实：SQLite FTS5 全文搜索
  - 长期记忆：EverMemOS HTTP API（云端/自托管双模式）
- **技能双引擎**:
  - Task Skill：ReAct 循环（天气、搜索等）
  - Modality Skill：人格内敛行为（自拍、语音、沉默、拆分消息）
- **主动消息**：驱力驱动的自主消息，5 分钟心跳检测
- **多 LLM 支持**：Gemini、Claude、Qwen3、GPT、MiniMax、Moonshot、StepFun、Ollama
- **多 TTS 支持**：DashScope、OpenAI、MiniMax
- **图像生成**：Gemini Imagen
- **角色系统**：10+ 内置角色（luna, iris, vivian, kai, kelly, ember, sora, mia, rex, nova），SOUL.md + SHELL.md 配置
- **状态持久化**：SQLite CAS + 神经权重/驱力状态自动保存
- **微信接入**：`wechat_adapter.py` 持久 WebSocket 适配
- **网关层**：FastAPI + WebSocket `/ws/chat` + REST API

### 技术债务（从 fork 继承）

- 测试覆盖不完整（缺少 `test_chat_agent.py`、`test_evermemos_client.py`）
- 内部 API 无集中文档
- 部署文档薄弱（仅开发启动说明）
- `persona/generator.py:260` 图像生成 API 待对接

---

## 版本规划

| 版本 | 目标 | 预计时间 |
|------|------|---------|
| 0.5.1 | EverMemOS 修复 + 文档体系完善 | 2026-06 |
| 0.6.0 | 微信上下文增强 + 日历感知（实验性） | 2026-07 |
| 0.7.0 | 图片理解 + 语音输入 + 阶段 II 核心功能 | 2026-08 |
| 0.8.0 | 多设备同步 + 实时语音通话（实验性） | 2026-Q4 |

---

## 如何维护本日志

1. **每次提交前**：在 `[Unreleased]` 下添加对应条目
2. **发布新版本时**：
   - 将 `[Unreleased]` 内容移动到新版本号下
   - 添加发布日期
   - 更新版本规划表
3. **条目分类**：
   - `Added`：新功能
   - `Changed`：现有功能变更
   - `Deprecated`：即将移除的功能
   - `Removed`：已移除的功能
   - `Fixed`：Bug 修复
   - `Security`：安全相关修复
