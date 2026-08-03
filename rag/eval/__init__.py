"""rag/eval —— RAG 系统评估框架

用于量化评估 RAG 的检索与生成质量，建立基线并做回归测试。

模块结构：
    stub_vertexai.py   # 兼容 stub（解决 ragas 与新版 langchain-community 的兼容问题）
    dataset.py         # 评估集模板：加载 / 保存 / 校验
    run_eval.py        # 评估脚本入口：检索评估 + 端到端评估 + RAGAS 评分

用法：
    ../bin/python -m rag.eval.run_eval --help
    ../bin/python -m rag.eval.run_eval --retrieval   # 只做检索评估
    ../bin/python -m rag.eval.run_eval --e2e         # 端到端 + RAGAS 评分
"""
