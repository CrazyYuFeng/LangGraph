"""llm_wiki —— LLM 编译型知识库（Karpathy LLM Wiki 模式）

把 rag/knowledge/*.md 用 LLM 编译成结构化、互链的 Markdown wiki，
查询时直接基于编译产物回答，而非每次实时向量检索。

模块组成：
    config.py    配置（复用项目根 .env）
    compiler.py  LLM 编译引擎（文档 → wiki 页面）
    ingest.py    摄入管线（扫描 + 增量编译 + 索引）
    query.py     基于 wiki 页面的问答
    main.py      CLI 入口
"""

__version__ = "0.1.0"
