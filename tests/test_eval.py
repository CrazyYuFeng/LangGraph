"""tests/test_eval.py —— 评估模块测试

覆盖不依赖 LLM 的纯逻辑：
    - dataset 模板生成
    - dataset 加载/保存
    - dataset 校验（格式检查）
"""
import sys
import json
from pathlib import Path

# 确保能导入 rag 包（项目根目录）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pytest

from rag.eval.dataset import (
    TEMPLATE_SAMPLES,
    load_dataset,
    save_dataset,
    init_template,
    validate_dataset,
)


# ============================================================
# 模板
# ============================================================
class TestTemplate:
    def test_template_has_required_fields(self):
        """模板样本应包含 question/expected/ground_truth。"""
        for sample in TEMPLATE_SAMPLES:
            assert "question" in sample
            assert "expected" in sample
            assert "ground_truth" in sample

    def test_template_not_empty(self):
        assert len(TEMPLATE_SAMPLES) > 0


# ============================================================
# 保存 / 加载
# ============================================================
class TestSaveLoad:
    def test_save_and_load_roundtrip(self, tmp_path):
        """保存后再加载应得到相同数据。"""
        path = tmp_path / "eval_set.json"
        data = [{"question": "q1", "expected": "e1"}]
        save_dataset(data, str(path))
        loaded = load_dataset(str(path))
        assert loaded == data

    def test_load_missing_file_returns_empty(self, tmp_path):
        path = tmp_path / "nonexistent.json"
        assert load_dataset(str(path)) == []


# ============================================================
# 模板初始化
# ============================================================
class TestInitTemplate:
    def test_init_creates_file(self, tmp_path):
        path = tmp_path / "eval_set.json"
        init_template(str(path))
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert len(data) == len(TEMPLATE_SAMPLES)

    def test_init_does_not_overwrite_existing(self, tmp_path):
        """已存在的评估集不应被覆盖。"""
        path = tmp_path / "eval_set.json"
        path.write_text(json.dumps([{"question": "自定义"}]), encoding="utf-8")
        init_template(str(path))
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data == [{"question": "自定义"}]


# ============================================================
# 校验
# ============================================================
class TestValidate:
    def test_valid_dataset(self):
        dataset = [{"question": "q1"}, {"question": "q2"}]
        assert validate_dataset(dataset) == []

    def test_missing_question(self):
        dataset = [{"question": "q1"}, {"expected": "e2"}]
        problems = validate_dataset(dataset)
        assert len(problems) == 1
        assert "question" in problems[0]

    def test_empty_question(self):
        dataset = [{"question": ""}]
        problems = validate_dataset(dataset)
        assert len(problems) == 1

    def test_non_dict_sample(self):
        dataset = ["not a dict"]
        problems = validate_dataset(dataset)
        assert len(problems) == 1
