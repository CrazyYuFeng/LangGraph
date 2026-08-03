"""rag/eval/run_eval.py —— 评估脚本入口

提供两类评估：
    1. 检索评估（--retrieval）：检查每个问题的正确答案是否出现在 top_k 检索结果中
    2. 端到端评估（--e2e）：跑完整 RAG 问答，并用 RAGAS 打分（忠实度/相关性/上下文精度）

用法：
    ../bin/python -m rag.eval.run_eval --init-template   # 生成评估集模板
    ../bin/python -m rag.eval.run_eval --retrieval       # 检索评估
    ../bin/python -m rag.eval.run_eval --e2e             # 端到端 + RAGAS 评分
    ../bin/python -m rag.eval.run_eval --retrieval --e2e # 全部
    ../bin/python -m rag.eval.run_eval --eval-set my_set.json  # 指定评估集
"""
import argparse
import os

# 必须在导入 ragas 之前注入 stub（解决兼容问题）
from rag.eval.stub_vertexai import apply_vertexai_stub
apply_vertexai_stub()

from rag.eval.dataset import load_dataset, init_template, validate_dataset
from rag.retriever import get_retriever
from rag.rag_chain import get_rag_chain
from rag.config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL


# ============================================================
# 检索评估
# ============================================================
def run_retrieval_eval(dataset: list, top_k: int = 5) -> dict:
    """检索评估：检查正确答案是否在 top_k 检索结果中。

    这里用「期望答案中的关键实体是否出现在检索结果里」作为召回判据。
    更精确的做法是人工标注每个问题的正确答案 chunk 的 ID。

    返回各指标汇总。
    """
    print("\n" + "=" * 60)
    print("检索评估（召回率检查）")
    print("=" * 60)

    retriever = get_retriever()
    total = 0
    hit = 0
    details = []

    for i, sample in enumerate(dataset):
        question = sample.get("question", "")
        expected = sample.get("expected", "")
        filter_meta = sample.get("filter_meta")
        if not question:
            continue

        total += 1
        docs = retriever.retrieve(question, k=top_k, filter_meta=filter_meta)

        # 把期望答案切分成关键词，判断是否命中检索结果
        keywords = _extract_keywords(expected)
        found = [kw for kw in keywords if any(kw in d.page_content for d in docs)]
        is_hit = len(found) >= max(1, len(keywords) // 2) if keywords else False
        if is_hit:
            hit += 1

        details.append({
            "question": question,
            "hit": is_hit,
            "matched_keywords": found,
            "top_k": len(docs),
        })
        status = "✓" if is_hit else "✗"
        print(f"[{i + 1:>2}] {status} {question[:40]}")

    recall = hit / total if total else 0
    print(f"\n召回率（top{top_k} 含正确答案）: {hit}/{total} = {recall:.2%}")
    return {"total": total, "hit": hit, "recall": recall, "details": details}


def _extract_keywords(text: str, max_kw: int = 6) -> list:
    """从期望答案中提取关键词（简单按长度过滤 + 去停用词）。

    仅用于检索评估的粗粒度判据，正式评估建议人工标注正确答案 chunk ID。
    """
    # 常见停用词
    stopwords = set("的是了和与或及在从中到对为按据等个条笔单用户订单金额时间日期状态平台来源上个月本月最近".split())
    # 提取数字和中文词组
    tokens = []
    for seg in text.replace("，", " ").replace("。", " ").split():
        seg = seg.strip()
        if len(seg) >= 2 and seg not in stopwords:
            tokens.append(seg)
    return tokens[:max_kw]


# ============================================================
# 端到端评估（RAGAS）
# ============================================================
def run_e2e_eval(dataset: list):
    """端到端评估：跑完整 RAG 问答 + RAGAS 评分。"""
    print("\n" + "=" * 60)
    print("端到端评估（RAGAS 评分）")
    print("=" * 60)

    import pandas as pd  # noqa: F401（result.to_pandas 内部使用）
    from ragas import evaluate
    from ragas.metrics import faithfulness, answer_relevancy, context_precision
    from ragas.metrics._context_recall import context_recall
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.dataset_schema import EvaluationDataset, SingleTurnSample
    from langchain_openai import ChatOpenAI
    from rag.embedder import get_embedder

    # 评估用 LLM（复用项目 DeepSeek 配置）
    eval_llm = ChatOpenAI(
        model=OPENAI_MODEL,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        temperature=0,
    )
    ragas_llm = LangchainLLMWrapper(eval_llm)
    ragas_embeddings = LangchainEmbeddingsWrapper(get_embedder())

    # 跑 RAG 问答，收集结果
    chain = get_rag_chain()
    samples = []
    for sample in dataset:
        question = sample.get("question", "")
        if not question:
            continue
        result = chain.answer(question, use_cache=False)
        samples.append(
            SingleTurnSample(
                user_input=question,
                response=result["answer"],
                retrieved_contexts=[d.page_content for d in result["sources"]],
                reference=sample.get("ground_truth", sample.get("expected", "")),
            )
        )

    if not samples:
        print("[eval] 评估集为空，无法评估")
        return

    dataset_obj = EvaluationDataset(samples=samples)
    print(f"共评估 {len(samples)} 条问题")

    # RAGAS 评分
    try:
        result = evaluate(
            dataset=dataset_obj,
            metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
            llm=ragas_llm,
            embeddings=ragas_embeddings,
        )
        print("\n" + "=" * 60)
        print("RAGAS 评分结果")
        print("=" * 60)
        print(result)
        result.to_pandas().to_csv(
            os.path.join(os.path.dirname(__file__), "eval_result.csv"),
            index=False,
            encoding="utf-8",
        )
        print("\n详细结果已保存: rag/eval/eval_result.csv")
    except Exception as e:
        import traceback
        print(f"[eval] RAGAS 评分失败: {e}")
        traceback.print_exc()
        print("（请确认 OPENAI_API_KEY 有效且网络可访问）")


# ============================================================
# 主入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="RAG 系统评估")
    parser.add_argument("--init-template", action="store_true", help="生成评估集模板")
    parser.add_argument("--retrieval", action="store_true", help="检索评估（召回率）")
    parser.add_argument("--e2e", action="store_true", help="端到端评估（RAGAS）")
    parser.add_argument("--eval-set", default=None, help="指定评估集文件路径")
    parser.add_argument("--top-k", type=int, default=5, help="检索 top_k（默认 5）")
    args = parser.parse_args()

    # 生成模板
    if args.init_template:
        init_template()
        print("评估集模板已生成，请编辑 rag/eval/eval_set.json 填入真实问题")
        return

    # 加载评估集
    dataset = load_dataset(args.eval_set) if args.eval_set else load_dataset()
    if not dataset:
        print("评估集为空。先运行: ../bin/python -m rag.eval.run_eval --init-template")
        return

    problems = validate_dataset(dataset)
    if problems:
        print("评估集格式有问题：")
        for p in problems:
            print(f"  - {p}")
        return

    print(f"已加载评估集: {len(dataset)} 条")

    # 默认全部执行
    if not args.retrieval and not args.e2e:
        args.retrieval = True
        args.e2e = True

    if args.retrieval:
        run_retrieval_eval(dataset, top_k=args.top_k)

    if args.e2e:
        run_e2e_eval(dataset)


if __name__ == "__main__":
    main()
