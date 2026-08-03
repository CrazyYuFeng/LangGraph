# LangGraph RAG 业务数据问答系统

基于 **LangChain + Chroma + DeepSeek** 的业务数据 RAG 系统，含多智能体编排（LangGraph）和定时周报。

## 快速上手

```bash
# 1. 安装依赖
./bin/pip install -r requirements.txt

# 2. 配置密钥（复制模板并填写）
cp env.example .env

# 3. 构建索引（首次运行）
./bin/python -m rag.update --rebuild

# 4. 问答
./bin/python main.py "订单902238334的金额是多少"
```

## 命令速查

### RAG 问答
```bash
./bin/python main.py "你的问题"            # 问答
./bin/python main.py "问题" --show-source  # 问答并显示引用来源
```

### 索引管理
```bash
./bin/python -m rag.update            # 增量更新（日常）
./bin/python -m rag.update --rebuild  # 全量重建
./run_rag_update.sh                   # 定时更新脚本（cron 用）
./run_cdc.sh                          # CDC 实时增量更新（需开启 binlog）
```

### 评估
```bash
./bin/python -m rag.eval.run_eval --init-template  # 生成评估集模板
./bin/python -m rag.eval.run_eval --retrieval       # 检索评估
./bin/python -m rag.eval.run_eval --e2e             # 端到端 RAGAS 评分
```

### 测试
```bash
./bin/python -m pytest tests/ -v
```

## 项目结构

```
├── rag/                    # RAG 核心
│   ├── rag_chain.py        # 问答链（检索+生成）
│   ├── retriever.py        # 检索器（混合检索+Rerank+阈值）
│   ├── hybrid_retriever.py # 混合检索（向量+BM25+RRF）
│   ├── vectorstore.py      # 向量库统一接口（chroma/pgvector/milvus）
│   ├── ingest.py           # 数据入库（增量更新）
│   ├── cdc.py              # CDC 实时增量更新（binlog）
│   ├── query_rewriter.py   # 查询改写/多查询
│   ├── cache.py            # 分层缓存
│   ├── tracing.py          # Langfuse 可观测性
│   ├── logging_setup.py    # 统一日志
│   ├── eval/               # 评估框架（RAGAS）
│   ├── knowledge/          # 本地知识库文件
│   └── chroma_db/          # 向量数据（gitignore）
├── hybrid_agent/           # LangGraph 多智能体
├── weekly_report/          # 定时周报
├── tests/                  # 单元测试
├── requirements.txt        # 依赖锁定
├── env.example             # 配置模板
└── .env                    # 真实密钥（gitignore）
```

## 文档导航

| 文档 | 内容 |
|------|------|
| `RAG_OPTIMIZATION.md` | RAG 优化速查手册（Chunk/幻觉/污染/召回/缓存/生命周期/工程化） |
| `HYBRID_AGENT.md` | 多智能体编排方案（Supervisor + Worker） |
| `rag/eval/README.md` | 评估框架使用说明 |

## 配置（.env）

所有密钥和参数统一在 `.env` 配置，见 `env.example` 模板。关键项：

| 配置 | 说明 | 默认 |
|------|------|------|
| `OPENAI_API_KEY` | DeepSeek 密钥 | 空 |
| `VECTOR_STORE_TYPE` | 向量库类型：chroma/pgvector/milvus | chroma |
| `DB_URL` | MySQL 连接 | 本地 VIP_USER |
| `LANGFUSE_*` | Langfuse 可观测性（可选） | 空（禁用） |
| `LOG_LEVEL` | 日志级别 | INFO |
