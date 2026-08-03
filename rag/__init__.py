"""rag 包 —— RAG 系统模块

包含：
    - config.py      配置
    - embedder.py    embedding 封装（bge-small-zh）
    - ingest.py      数据入库（数据库 + 本地文件）
    - retriever.py   检索（阈值过滤）
    - rag_chain.py   RAG 问答链（强约束 prompt）
    - main.py        入口
"""
