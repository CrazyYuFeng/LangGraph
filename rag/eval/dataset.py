"""rag/eval/dataset.py —— 评估集模板

评估集是 RAG 优化的基础：没有评估集，就无法量化验证优化效果。

每条评估样本结构：
    {
        "question":  真实业务问题，
        "expected":  期望答案（用于人工/规则校验），
        "ground_truth": 期望答案（用于 RAGAS 端到端评分，可复用 expected），
        "filter_meta":  可选的检索过滤条件，如 {"source": "db"}，
    }
"""
import json
import os

# 默认评估集文件路径
DEFAULT_DATASET_PATH = os.path.join(os.path.dirname(__file__), "eval_set.json")


# ============================================================
# 评估集模板（示例样本）
# ============================================================
# 根据实际业务数据（ORDER_INFO 表）填充真实问题。
# 建议收集 50-100 条真实用户问题 + 期望答案，覆盖：
#   - 金额/数量查询（CREDIT）
#   - 用户/订单维度
#   - 时间范围
#   - 状态/平台/来源过滤
TEMPLATE_SAMPLES = [
    {
        "question": "上个月 CREDIT 大于 100 的订单有哪些？",
        "expected": "（请根据实际数据填写期望答案，如：订单ID xxx、xxx，金额分别为...）",
        "ground_truth": "（同上，用于 RAGAS 端到端评分）",
        "filter_meta": {"source": "db"},
    },
    {
        "question": "用户 12345 最近一笔订单的支付类型是什么？",
        "expected": "（请填写期望答案）",
        "ground_truth": "（同上）",
        "filter_meta": {"source": "db", "user_id": "12345"},
    },
    {
        "question": "本月各支付平台的订单数量统计？",
        "expected": "（请填写期望答案）",
        "ground_truth": "（同上）",
        "filter_meta": {"source": "db"},
    },
]


# ============================================================
# 加载 / 保存 / 校验
# ============================================================
def load_dataset(path: str = DEFAULT_DATASET_PATH) -> list:
    """加载评估集。文件不存在时返回空列表。"""
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_dataset(dataset: list, path: str = DEFAULT_DATASET_PATH):
    """保存评估集（覆盖写）。"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)
    print(f"[eval] 评估集已保存: {path} ({len(dataset)} 条)")


def init_template(path: str = DEFAULT_DATASET_PATH):
    """生成评估集模板文件（若不存在）。"""
    if os.path.isfile(path):
        print(f"[eval] 评估集已存在，跳过模板生成: {path}")
        return
    save_dataset(TEMPLATE_SAMPLES, path)


def validate_dataset(dataset: list) -> list:
    """校验评估集，返回格式不合法的问题列表。"""
    problems = []
    for i, sample in enumerate(dataset):
        if not isinstance(sample, dict):
            problems.append(f"第 {i} 条不是对象")
            continue
        if "question" not in sample or not sample["question"]:
            problems.append(f"第 {i} 条缺少 question")
    return problems


if __name__ == "__main__":
    init_template()
