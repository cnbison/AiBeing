# AiBeing 对话接入方式完全参考

> 日期: 2026-06-02
> 版本: Genome v10 Hybrid
> 后端地址: `http://localhost:8000`

---

## 一、内置对话方式概览

AiBeing 后端 (`main.py`) 暴露了多种接入方式，任何支持 HTTP/WebSocket 的客户端都可以连接。

| 方式 | 协议 | 端点 | 位置/说明 |
|------|------|------|----------|
| **微信** | WebSocket via Adapter | `ws://localhost:8000/ws/chat` | `wechat_adapter.py` 桥接微信 |
| **macOS 桌面** | WebSocket 直连 | `ws://localhost:8000/ws/chat` | `desktop/AiBeing/` SwiftUI |
| **Web SPA** | HTTP (静态文件) | `http://localhost:8000/` | `static/index.html` (需构建) |
| **任意 HTTP 工具** | REST API | `POST /api/chat` | curl / Postman / 脚本 |
| **任意 WS 工具** | WebSocket | `ws://localhost:8000/ws/chat` | wscat / 浏览器 JS |

### 当前项目中的客户端实现

| 客户端 | 接入方式 | 代码位置 |
|--------|---------|---------|
| 微信 adapter | WebSocket via adapter | `wechat_adapter.py` |
| macOS 桌面 | WebSocket 直连 | `desktop/AiBeing/` |

> **Web SPA 状态**: `static/index.html` 不存在，访问 `http://localhost:8000/` 返回 503。如需 Web 前端，需另行构建 React SPA 并放到 `static/` 目录。

---

## 二、REST API 详解

### 2.1 端点

```
POST http://localhost:8000/api/chat
```

### 2.2 请求参数 (ChatRequest)

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `message` | string | ✓ | 用户说的话 |
| `persona_id` | string | ✓ | 角色 ID，如 `luna` |
| `session_id` | string | — | 会话 ID，不传则新建；传了则继续同一对话 |
| `user_name` | string | — | 用户昵称 |
| `client_id` | string | — | 客户端标识，用于聊天记录归档 |

### 2.3 响应结构

```json
{
  "session_id": "abc123...",
  "response": "AI 的回复内容",
  "modality": "文字",
  "image_url": null,
  // + status 中的其他字段（驱力状态、信号等）
}
```

### 2.4 curl 调用示例

#### 基础调用（新建会话）

```bash
curl -s -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "你好，今天过得怎么样？",
    "persona_id": "luna",
    "user_name": "用户",
    "client_id": "curl-test"
  }'
```

响应示例：
```json
{
  "session_id": "abc123...",
  "response": "今天还不错呢，你呢？",
  "modality": "文字",
  "image_url": null
}
```

#### 持续对话（复用 session_id）

拿到上一步的 `session_id`，在后续请求中带上它，AI 就会记住上下文：

```bash
curl -s -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "我刚喝了一杯黑咖啡",
    "persona_id": "luna",
    "session_id": "abc123...",
    "client_id": "curl-test"
  }'
```

#### 查看可用角色列表

```bash
curl -s http://localhost:8000/api/personas
```

#### prettier 输出（可选）

加上 `| jq` 让 JSON 格式化：
```bash
curl -s -X POST http://localhost:8000/api/chat ... | jq
```

如果没有安装 jq，用 `python -m json.tool` 代替：
```bash
curl -s -X POST http://localhost:8000/api/chat ... | python -m json.tool
```

---

## 三、REST API vs WebSocket 对比

| 维度 | REST API | WebSocket |
|------|----------|-----------|
| 连接方式 | 每次独立 HTTP 请求 | 一次连接，持续收发 |
| 实时性 | 等待完整响应 | 可接收流式 chunk / 主动消息 |
| 代码复杂度 | 低（单次请求） | 高（需管理连接状态） |
| 适用场景 | 快速测试、脚本自动化 | 桌面客户端、实时聊天 |
| 主动消息 | 不支持 | 支持（proactive 心跳推送） |

**结论**: REST API 适合**快速验证后端是否正常**或**写脚本自动化测试**。真正的实时聊天体验（含主动消息、流式响应）应走 WebSocket。

---

## 四、其他可用端点

| 方法 | 端点 | 用途 |
|------|------|------|
| GET | `/api/status` | 服务状态 |
| GET | `/api/personas` | 角色列表 |
| GET | `/api/session/{id}/status` | 会话状态 |
| GET | `/api/chat/history/{persona_id}` | 聊天历史 |
| GET | `/api/tts` | TTS 合成 |
| POST | `/api/image` | 图片生成 |
| GET | `/api/avatar/{persona_id}` | 角色头像 |
| GET | `/api/selfie/{filename}` | 自拍图片 |
| WS | `/ws/chat` | WebSocket 实时聊天 |

---

## 五、验证后端是否启动

```bash
# 检查服务是否存活
curl -s http://localhost:8000/api/status

# 快速测试单轮对话
curl -s -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"你好","persona_id":"luna","client_id":"test"}' | jq
```
