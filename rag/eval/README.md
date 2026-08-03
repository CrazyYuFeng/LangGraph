# RAG 评估框架（rag/eval/）

量化评估 RAG 系统的检索与生成质量，建立基线并做回归测试。

## 依赖

```bash
./bin/pip install ragas   # 评估框架（已含在 requirements.txt）
```

## 模块结构

| 文件 | 作用 |
|------|------|
| `stub_vertexai.py` | 兼容 stub（解决 ragas 与新版 langchain-community 的兼容问题） |
| `dataset.py` | 评估集模板：加载 / 保存 / 校验 |
| `run_eval.py` | 评估脚本入口：检索评估 + 端到端 RAGAS 评分 |
| `eval_set.json` | 评估集（真实业务问题 + 期望答案） |
| `eval_result.csv` | 评估结果输出 |

## 用法

```bash
# 1. 生成评估集模板（首次运行）
../bin/python -m rag.eval.run_eval --init-template
# 编辑 rag/eval/eval_set.json，填入 50-100 条真实业务问题 + 期望答案

# 2. 检索评估（召回率检查，不调用 LLM 评分，快）
../bin/python -m rag.eval.run_eval --retrieval

# 3. 端到端评估（跑完整问答 + RAGAS 评分，慢，需 LLM）
../bin/python -m rag.eval.run_eval --e2e

# 4. 全部评估
../bin/python -m rag.eval.run_eval

# 5. 指定评估集文件
../bin/python -m rag.eval.run_eval --eval-set my_set.json
```

## 评估指标（RAGAS）

| 指标 | 含义 | 说明 |
|------|------|------|
| faithfulness | 忠实度 | 答案是否完全基于检索资料，不编造（幻觉检测） |
| answer_relevancy | 答案相关性 | 答案是否切题 |
| context_precision | 上下文精度 | 检索到的资料是否都是相关的（污染检测） |
| context_recall | 上下文召回 | 正确资料是否都被检索到（召回检测） |

## 使用建议

1. **先建基线**：用当前系统跑一遍，记录各指标分数。
2. **每次改动后回归**：改 chunk / 检索 / prompt / 加查询改写后，重跑评估对比基线。
3. **分模块定位**：
   - `context_recall` 低 → 召回问题，加查询改写 / 多查询 / 换 embedding
   - `context_precision` 低 → 污染问题，加 Rerank / 阈值过滤
   - `faithfulness` 低 → 幻觉问题，加强 prompt 约束 / 引用校验
   - `answer_relevancy` 低 → 生成问题，调 prompt

## 注意事项

- 端到端评估较慢（每条问题 RAGAS 会多次调用 LLM 评分），建议用小评估集调试。
- 评估集是**业务资产**，应随业务数据一起维护，定期补充真实问题。
- 检索评估的召回判据是粗粒度关键词匹配，正式评估建议人工标注正确答案的 chunk ID。
