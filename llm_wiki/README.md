# llm_wiki —— LLM 编译型知识库

把 `rag/knowledge/*.md` 用 LLM 编译成结构化、互链的 Markdown wiki
（Karpathy LLM Wiki 模式：入库时沉淀知识，查询时直接基于编译产物回答，
不做每次实时向量检索）。

## 用法（项目根目录）

```bash
# 1. 摄入（增量：未变更的文件跳过）
./bin/python -m llm_wiki.main ingest

# 2. 全量重编（改了编译 prompt 或想重建时）
./bin/python -m llm_wiki.main ingest --rebuild

# 3. 列出已编译页面
./bin/python -m llm_wiki.main list

# 4. 基于 wiki 问答
./bin/python -m llm_wiki.main query "高价值订单怎么统计？"
```

## 目录结构

```
llm_wiki/
├── config.py     # 配置（复用项目根 .env；LLM 走 DeepSeek）
├── compiler.py   # LLM 编译引擎（文档 → wiki 页面，JSON 容错解析）
├── ingest.py     # 摄入管线（hash 增量 + 页面落盘 + manifest/index）
├── query.py      # 基于 wiki 页面的问答（关键词打分 + LLM 回答）
├── main.py       # CLI 入口
└── wiki/         # 编译产物（自动生成，可 gitignore）
    ├── manifest.json   # 摄入清单：源文件 hash → 页面列表（增量依据）
    ├── index.md        # wiki 总览链接图
    └── <源文档名>/     # 每个源文档一个目录，页面带 front-matter 与 [[双链]]
```

## 增量更新原理

- `manifest.json` 记录每个源文件的 **md5 hash** 与编译出的页面列表
- 再次 ingest 时对比 hash：未变更 → 跳过；变更 → 重编该文件并**先清理旧页面**
  再写新页面（保证 wiki 是源文档的完整镜像，不留孤儿页）

## 配置

在项目根 `.env` 中可选配置：

```bash
# 摄入源目录（默认 rag/knowledge）
#WIKI_KNOWLEDGE_DIR="/path/to/knowledge"
# 编译产物目录（默认 llm_wiki/wiki）
#WIKI_DIR="/path/to/wiki"
```

LLM 复用 `.env` 中的 `OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL`
（DeepSeek，OpenAI 兼容）；配置了 `LANGSMITH_API_KEY` 时，编译与问答调用
自动进入 LangSmith trace（项目名 `llm-wiki`）。

## 与 rag 模块的关系

| | rag（现有） | llm_wiki（本模块） |
|---|---|---|
| 数据源 | MySQL 订单表 + knowledge 文件 | 仅 `rag/knowledge/*.md` |
| 组织方式 | 向量库实时检索 | 编译期沉淀为互链 wiki |
| 适合场景 | 高频变更的事实查询 | 慢变文档型知识沉淀 |
