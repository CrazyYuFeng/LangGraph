"""rag/embedder.py —— embedding 封装

使用本地开源模型 BAAI/bge-small-zh-v1.5，免费离线，中文效果好。

解决网络问题：
    - 配置国内 HuggingFace 镜像（hf-mirror.com），避免访问 huggingface.co 不稳定
    - 模型已缓存时优先本地加载，减少联网
"""
import os

from langchain_huggingface import HuggingFaceEmbeddings

from rag.config import EMBEDDING_MODEL

# 配置国内 HuggingFace 镜像（解决网络访问 huggingface.co 不稳定问题）
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")


def get_embedder():
    """返回 bge embedding 模型实例。"""
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},  # 用 CPU 即可，bge-small 很小
        encode_kwargs={"normalize_embeddings": True},  # 归一化，便于余弦相似度
    )
