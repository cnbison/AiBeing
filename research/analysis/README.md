# 代码分析文档索引

> `research/analysis/` 目录存放对特定代码模块、API 接口、或技术问题的深度分析文档。
>
> 命名规范：`YYYY-MM-{topic}.md`
> 创建新文档时，请在下方表格中登记。

---

## 现有文档

| 日期 | 文档 | 分析范围 | 状态 |
|------|------|---------|------|
| 2026-06-01 | [everos-cloud-api-audit.md](everos-cloud-api-audit.md) | `providers/memory/evermemos/evermemos_client.py` 云端 API 模式 | active |
| 2026-06-02 | [2026-06-api-access-methods.md](2026-06-api-access-methods.md) | 后端对话接入方式（REST + WebSocket + 内置客户端） | active |

---

## 文档模板

创建新分析文档时，建议在文件头包含以下信息：

```markdown
---
date: 2026-06-15
topic: 分析主题
scope: 涉及的文件/模块
status: active | superseded | archived
related: 关联的其他文档（如 ARCHITECTURE.md）
---

> 一句话总结本次分析的结论。

## 背景

为什么做这次分析？

## 分析对象

具体代码位置、接口、或问题描述。

## 发现

1. 问题 A
2. 问题 B

## 建议

1. 修复方案
2. 优先级

## 验证

如何验证修复是否生效？
```

---

## 待分析清单（由 ROADMAP/ARCHITECTURE 驱动）

- [ ] WebSocket 协议完整规范
- [ ] 12 步生命周期性能瓶颈分析
- [ ] Critic prompt 质量评估
- [ ] StyleMemory KNN 检索准确性
- [ ] Hebbian 学习效果量化
