
## 关于EverMemOS的作用和必要性
本地已有的（不受影响）：
  - 人格涌现、情绪热力学、Hebbian 学习 → 全在本地 SQLite
  - 风格记忆（KNN 检索相似情境下的说话方式）→ 本地
  - 当前会话的对话历史（40 轮）→ 内存
  - 所有技能（天气/自拍/语音/主动消息）→ 正常运作
  
  EverMemOS 独有的（关闭后缺失）：
  - 跨会话记忆——今天聊完，明天重新打开，她完全不记得昨天说了什么
  - 用户画像——不会记得你的名字、生日、喜好、养了什么宠物
  - 关系深度——永远是"刚认识"的状态，不会随时间越来越懂你
  - 叙事摘要——不记得你们之间发生过什么故事
  - 预感——不会在你累的时候主动关心
  
  一句话总结：不用
  EverMemOS，她是一个有血有肉但失忆的人——性格、情绪、说话风格都在，但
  每次对话都是"第一次见面"。想要"越聊越懂你"的陪伴感，EverMemOS
  是关键。


## 基础设施（Docker）：
  - MongoDB + Elasticsearch + Milvus（向量数据库，含 etcd + minio）+
  Redis
  
  主应用（本地 uv 启动）：
  - 需要 Embedding 服务（vLLM 自部署 或 DeepInfra API）
  - 需要 Rerank 服务（vLLM 自部署 或 DeepInfra API）
  - 需要 LLM（OpenRouter 等）
  - API 端口 1995
  
  docker-compose.yaml 只启动数据库层，主应用要单独 uv run python 
  run.py 启动。

  这意味着你要：
  1. 有 Docker 运行 MongoDB/ES/Milvus/Redis
  2. 另外准备 Embedding + Rerank 模型服务（或买 DeepInfra API）
  3. 配置 LLM API key
  4. 本地启动 Python 服务
  
  这个栈很重。你确定要自部署吗？如果确定，我可以一步步帮你启动。如果嫌
  重，可以考虑先禁用 EverMemOS，等它出更轻量的方案。

自部署的话是否意味着还要下载和运行本地模型？                        

⏺ 不一定，有两种方案：
  
  方案 A：纯 API（不需要本地模型）
  - Embedding 和 Rerank 都用 DeepInfra API（付费，按量计费）
  - 只需要改 EverMemOS 的 .env 配置，不需要下载任何模型
  
  方案 B：本地模型（需要下载运行）
  - Embedding 和 Rerank 都用 vLLM 自部署
  - 需要下载运行 Qwen3-Embedding-4B 和 Qwen3-Reranker-4B 模型
  - 需要 GPU 或高性能 CPU
  
  env.template 里默认是 方案 B（vLLM），但你可以改成方案 A。

  如果你选 方案 A，总资源消耗是：
  - Docker 跑数据库层（MongoDB + ES + Milvus + Redis）→ 内存约 4-6GB
  - 本地 Python 跑 EverMemOS 主服务 → 很轻
  - Embedding/Rerank 走 DeepInfra API → 不需要本地模型