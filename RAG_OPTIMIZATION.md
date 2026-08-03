# RAG 系统优化速查手册

针对**业务数据 + LangChain RAG** 场景的四大核心问题优化方案。

---

## 1. Chunk 优化（向量词切分）

### 核心原则：Chunk 粒度取决于回答粒度

| 内容类型 | 策略 |
|---------|------|
| 业务数据（报表/记录） | **按记录/实体切分**，每条记录一个 chunk |
| 技术文档 | 按段落/小节切分，500-800 tokens |
| 长文 | 分层切分（parent-child） |

### 关键优化点

**① 语义完整切分，而非固定长度**
```python
# ✅ 按语义边界切分（段落/句子），注意中文分隔符
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=100,          # 重叠 10-20%，保留上下文
    separators=["\n\n", "\n", "。", "；", "，", " ", ""],
)
```

**② 业务数据按记录切分 + 元数据标签**
```python
for row in db_records:
    doc = Document(
        page_content=f"订单:{row['id']} 用户:{row['user_id']} 金额:{row['credit']}...",
        metadata={"order_id": row["id"], "date": row["time"]}  # 用于检索过滤
    )
```

**③ 元数据过滤**：给 chunk 打标签（日期/类型/用户），检索时过滤，大幅提升准确率。

---

## 2. 解决幻觉

幻觉 = LLM 编造上下文之外的信息。根源是**检索不精准** + **prompt 约束弱**。

### 三层防线

**① 检索层**：混合检索（向量+BM25）+ Rerank 精排

**② 生成层：强约束 prompt**
```python
SYSTEM_PROMPT = """回答规则：
1. 只能基于【提供的资料】回答，禁止编造
2. 资料中没有答案时，明确说"资料中未找到相关信息"
3. 引用资料时标注来源编号 [1][2]
4. 不补充资料之外的知识
"""
```

**③ 验证层**：要求标注引用来源，后端校验引用真实性，不存在的拒绝。

---

## 3. 解决上下文污染

上下文污染 = 检索到不相关/过时/冲突资料，误导 LLM。

### 对策

| 污染源 | 对策 |
|--------|------|
| 不相关 chunk | Rerank + 相似度阈值过滤 |
| 过时数据 | 元数据时间过滤，只检索最新 |
| 多文档冲突 | 按来源分组，标注可信度 |
| 上下文过长稀释 | 压缩，只保留相关片段 |

### 推荐：混合检索 + Rerank + 阈值过滤
```python
# 1. 混合检索（向量 + BM25，RRF 融合）—— 提升召回
# 2. Rerank（交叉编码器精排）—— 提升精度
# 3. 阈值过滤（低于阈值丢弃）—— 防污染
from rag.hybrid_retriever import get_hybrid_retriever
from rag.reranker import rerank

hybrid = get_hybrid_retriever()
candidates = hybrid.retrieve(query, k=15)   # 召回多一点供精排
reranked = rerank(query, candidates, top_k=5)  # 精排保留 top5
filtered = [d for d in reranked if d.metadata["score"] > 0.4]  # 阈值过滤
```

### 本项目已实现的检索流程
```
查询 → 混合检索(向量+BM25, RRF融合) → Rerank精排 → 阈值过滤 → 生成
```

---

## 4. 解决 Defect（系统缺陷）

### 建立评估集（最重要）
```python
eval_set = [
    {"question": "上个月 CREDIT>100 的订单？", "expected": "..."},
    # 50-100 条真实问题 + 期望答案
]
```

### 分模块定位缺陷
- **检索评估**：top_k 里有没有正确答案（召回率）
- **生成评估**：答案是否准确、引用是否正确
- **端到端**：整体质量

### 常见缺陷清单

| 缺陷 | 症状 | 修复 |
|------|------|------|
| 召回失败 | 答非所问 | 换 embedding、加关键词检索 |
| 精度不足 | 答错 | Rerank、元数据过滤 |
| 上下文污染 | 被无关信息带偏 | 阈值过滤、压缩 |
| 幻觉 | 编造 | prompt 约束、引用校验 |

---

## 最佳实践路径

```
业务数据 RAG 优化：
1. Chunk：按记录切分 + 元数据标签
2. 检索：混合检索 + Rerank + 阈值过滤
3. 生成：强约束 prompt + 引用溯源
4. 评估：建评估集，分模块定位缺陷
```

---

## 5. 生命周期管理（增量更新 + 定时任务）

### 文档生命周期

```
采集 → 清洗 → 切分 → 向量化 → 入库 → 检索生成 → 反馈
  └─────────── 持续增量更新（增/删/改）──────────────┘
```

### 更新策略对比

| 策略 | 做法 | 适用 |
|------|------|------|
| 全量重建 | 清空全部重新入库 | 数据量小、结构大改 |
| **增量更新** | 只处理新增/修改/删除 | **主流做法，推荐** |
| 定时刷新 | 按周期检查变更 | 数据定期更新 |

### 增量更新原理（基于稳定 ID）

每条文档有稳定 ID（如 `db-订单ID`、`file-文件名-序号`），更新时对比：

```
当前数据源 ID 集合  vs  索引中已有 ID 集合
  ├── 数据源有、索引无 → 新增（add_documents）
  ├── 数据源有、索引有 → 更新（update_documents）
  └── 数据源无、索引有 → 删除（delete）
```

### 本项目的增量更新用法

```bash
# 增量更新（推荐日常使用）
./bin/python -m rag.update

# 全量重建（结构大改时）
./bin/python -m rag.update --rebuild

# 定时脚本（cron 用，含日志）
./run_rag_update.sh
```

### 配置 cron（每天 02:00 自动增量更新）

```bash
crontab -e
# 添加这一行
0 2 * * * /Users/tme8000/workspace/LangGraph/run_rag_update.sh
```

### 定时脚本说明

- 日志保存到 `rag/logs/rag_update_YYYYMMDD.log`（按天）
- 自动切换到项目根目录，使用虚拟环境 Python
- 支持 `--rebuild` 参数全量重建

### 实时增量更新（CDC，基于 binlog）

定时更新是分钟级/小时级，若需要**秒级实时同步**数据库变更到向量库，用 CDC。

```bash
# 检查 binlog 是否开启
./bin/python -m rag.cdc --check-binlog

# 启动 CDC 监听（常驻进程，实时同步增删改）
./run_cdc.sh

# 从上次断点续传（重启后继续）
./run_cdc.sh --resume
```

**前置条件（需开启 MySQL binlog）**：
1. 编辑 MySQL 配置（如 `/etc/my.cnf`，需 sudo）：
   ```ini
   [mysqld]
   log_bin=mysql-bin
   binlog_format=ROW
   server-id=1
   ```
2. 重启 MySQL：`sudo launchctl stop com.oracle.oss.mysql.mysqld` 再 start
3. 验证：`SHOW VARIABLES LIKE 'log_bin';` 应为 `ON`

**CDC 与定时更新的关系**：
- CDC：实时，常驻进程，适合高频变更业务数据
- 定时更新：兜底，适合低频变更/本地文件
- 两者可共存，CDC 为主、定时为辅

---

## 6. 召回优化（提升召回率）

召回率 = 检索结果中**包含正确答案**的比例。召回率低会导致"该答的没答出来"。

### 召回率低的常见原因

| 原因 | 症状 | 解法 |
|------|------|------|
| 向量检索漏掉关键词匹配 | 问法不同但意思相同 | **混合检索**（向量+BM25） |
| embedding 模型能力不足 | 语义近义词匹配不到 | 换更强的 embedding |
| chunk 切分不合理 | 答案被切断 | 调整 chunk 大小/重叠 |
| 检索 top_k 太小 | 正确答案排后面被截断 | 增大 top_k |
| 查询改写不足 | 用户口语化，检索不到 | **查询改写/多查询** |

### 召回优化策略（按优先级）

**① 混合检索**（已实现）
向量语义 + BM25 关键词互补，RRF 融合。

**② 多查询（Multi-Query）**
用 LLM 把一个问题改写成多个角度，分别检索再合并：
```python
# 示例：把一个问题改写成 3 个变体查询
queries = llm.generate_queries(question)  # 返回多个改写
all_docs = [retrieve(q) for q in queries]  # 分别检索
merged = merge_dedupe(all_docs)             # 合并去重
```

**③ 查询改写（Query Rewriting）**
让 LLM 把口语化问题转成适合检索的规范查询。

**④ 增大召回 + Rerank 兜底**
召回 top_k 大一点（如 15-20），靠 Rerank 精排，避免漏掉。

**⑤ 元数据过滤**
按日期/类型/来源过滤，缩小检索范围，提升相关性。

---

## 7. 缓存（提升性能）

缓存解决**重复查询**的性能问题：相同/相似问题不重复检索和生成。

### 缓存策略对比

| 策略 | 做法 | 适用 |
|------|------|------|
| **精确缓存** | 完全相同的问题直接返回缓存 | 低频、问题固定 |
| **语义缓存** | 相似问题（向量相似度高）返回缓存 | 高频、问题多变 |
| 不缓存 | 每次都检索+生成 | 数据实时变化 |

### 精确缓存（最简单）
```python
import hashlib, json

cache = {}  # 可用 Redis 替代

def get_cached(query):
    key = hashlib.md5(query.encode()).hexdigest()
    return cache.get(key)

def set_cached(query, answer):
    key = hashlib.md5(query.encode()).hexdigest()
    cache[key] = answer
```

### 语义缓存（更智能）
用向量相似度判断问题是否和已缓存的问题相似：
```python
def semantic_cache(query, cached_queries, threshold=0.9):
    """如果 query 和某个已缓存问题相似，返回缓存答案。"""
    for cached_q, answer in cached_queries:
        if similarity(query, cached_q) > threshold:
            return answer
    return None
```

### 缓存注意事项

| 注意点 | 说明 |
|--------|------|
| **缓存失效** | 数据更新后要清缓存（增量更新时清相关缓存） |
| **TTL 过期** | 设置过期时间，避免旧数据长期驻留 |
| **缓存 key** | 用规范化后的查询做 key（去除标点、统一大小写） |
| **存储介质** | 单机用内存/文件，分布式用 Redis |

### 缓存与增量更新的配合

```
增量更新时：
  1. 更新索引
  2. 清空/失效相关缓存  ← 关键！否则返回旧数据
```

### 本项目建议的缓存方案

1. **精确缓存**：相同问题直接返回（用 Redis 或内存）
2. **TTL**：设置 1 小时过期
3. **更新时清缓存**：`rag.update` 运行时清空缓存

### 本项目已实现的分层缓存（四层）

```bash
# 启动 Redis 服务
brew services start redis
```

```python
# rag/cache.py —— 分层缓存系统
from rag.cache import (
    instant_cache,    # 瞬时缓存（内存）
    short_cache,      # 短缓存（Redis）
    long_cache,       # 长缓存（Redis）
    preference_cache, # 偏好缓存（Redis）
    get_cached,       # 按查询类型自动选层查缓存
    set_cached,       # 按查询类型自动选层写缓存
    clear_all_cache,  # 清空缓存（增量更新时调用）
)
```

**四层缓存对比**：

| 缓存层 | 生命周期 | 存储 | TTL | 缓存内容 |
|--------|---------|------|-----|---------|
| 瞬时 | 秒-分钟级 | 内存 | 5分钟 | 会话上下文、问候 |
| 短 | 分钟级 | Redis | 30分钟 | 实时数据查询 |
| 长 | 小时级 | Redis | 24小时 | 知识库问答、业务规则 |
| 偏好 | 永久 | Redis | 无 | 用户偏好、个性化设置 |

**缓存选择逻辑**（`classify_query`）：

| 查询类型 | 关键词 | 缓存层 |
|---------|--------|--------|
| 偏好表达 | 我偏好/我的设置/记住我 | preference |
| 知识问答 | 表示/是什么/说明/规则 | long |
| 实时数据 | 当前/统计/金额/订单 | short |
| 会话问候 | 你好/hi/hello | instant |

**配置**（`rag/config.py`）：
```python
REDIS_URL = "redis://localhost:6379/0"
```

**缓存与增量更新联动**：
- `rag.update` 运行时清空瞬时/短/长缓存
- **偏好缓存保留**（用户偏好不随数据更新失效）
- 已验证：增量更新 → 瞬时/短/长清空，偏好保留

---

## 8. 企业级进阶（已实现）

### 8.1 评估框架（RAGAS）

量化评估检索与生成质量，建立基线 + 回归测试。**这是所有优化的验证基础。**

```bash
../bin/python -m rag.eval.run_eval --init-template  # 生成评估集模板
../bin/python -m rag.eval.run_eval --retrieval       # 检索评估（召回率）
../bin/python -m rag.eval.run_eval --e2e             # 端到端 RAGAS 评分
```

指标：faithfulness（幻觉）、answer_relevancy（切题）、context_precision（污染）、context_recall（召回）。
详见 `rag/eval/README.md`。

### 8.2 查询改写 / 多查询（提升召回）

解决口语化提问、问法不同但意思相同的召回问题。

```python
# rag/query_rewriter.py
from rag.query_rewriter import query_rewrite, multi_query

# 查询改写：口语化 → 规范检索查询
query_rewrite("上个月花了多少钱")   # -> "上月消费金额 CREDIT"

# 多查询：改写多个角度检索后合并去重
multi_query("上个月花了多少钱")     # -> 原问题 + 3 个改写变体
```

在 RAGRetriever / RAGChain 按需开启：
```python
chain.answer(question, rewrite=True)        # 查询改写
chain.answer(question, multi_query=True)    # 多查询（默认改写 3 个）
```

### 8.3 可观测性（Langfuse trace）

记录每次查询的完整链路（检索 chunk、分数、LLM 输入输出），定位缺陷 + 审计。

```bash
# 配置环境变量后自动启用（未配置则静默跳过，不影响功能）
export LANGFUSE_PUBLIC_KEY="..."
export LANGFUSE_SECRET_KEY="..."
export LANGFUSE_HOST="https://cloud.langfuse.com"
```

```python
# rag/tracing.py —— 已接入 rag_chain.answer()
from rag.tracing import get_tracing, is_tracing_enabled
```

### 8.4 依赖安装

```bash
./bin/pip install -r requirements.txt   # 一键安装所有依赖
```

---

## 9. 工程化（企业级基础设施）

### 9.1 向量库可切换（Chroma / pgvector / Milvus）

通过统一接口层 `rag/vectorstore.py`，三种后端运行时切换，无需改代码。

**当前默认使用 Chroma（单机文件存储）**，数据在 `rag/chroma_db/`。

```bash
# 切换后端：改 .env 的 VECTOR_STORE_TYPE
VECTOR_STORE_TYPE="chroma"      # 默认，单机文件
VECTOR_STORE_TYPE="pgvector"    # PostgreSQL + pgvector 扩展
VECTOR_STORE_TYPE="milvus"      # 专业向量库
```

切换后需重建索引：
```bash
./bin/python -m rag.update --rebuild
```

**三种后端对比**：

| 后端 | 适用场景 | 前置条件 |
|------|---------|---------|
| Chroma | 单机、数据量小（百万级以下） | 无需额外服务 |
| pgvector | 业务数据与向量同库，增量一致 | PostgreSQL + pgvector 扩展 |
| Milvus | 超大向量规模、高并发 | Milvus 服务（Docker） |

### 9.2 统一日志（结构化 + 滚动）

所有模块通过 `rag/logging_setup.py` 输出日志：
- 控制台：可读格式
- 文件：JSON 结构化（`rag/logs/rag.log`），按天滚动保留 30 天
- 级别由环境变量 `LOG_LEVEL` 控制（默认 INFO）

```python
from rag.logging_setup import get_logger
logger = get_logger(__name__)
logger.info("...")
logger.error("...", exc_info=True)
```

### 9.3 密钥管理（统一 .env）

所有真实密钥统一放在项目根目录 `.env`（已被 .gitignore 忽略，不入库）。
代码里零硬编码密钥，通过 `os.getenv` 读取。

```bash
# 复制模板并填写（env.example 是模板）
cp env.example .env
# 编辑 .env 填入真实 key
```

配置项：`OPENAI_API_KEY`、`TAVILY_API_KEY`、`WECOM_WEBHOOK_URL`、`LANGFUSE_*`、`DB_URL` 等。

### 9.4 自动化测试

不依赖外部服务（数据库/Redis/LLM/Chroma），可离线运行，适合 CI。

```bash
./bin/python -m pytest tests/ -v
```

覆盖模块：
- `test_cache.py`：缓存、查询分类
- `test_retrieval.py`：分词、RRF 融合、阈值过滤
- `test_query_rewriter.py`：查询改写、多查询解析
- `test_eval.py`：评估集
- `test_vectorstore.py`：向量库切换

### 9.5 依赖管理

`requirements.txt` 锁定所有依赖版本，一键安装：
```bash
./bin/pip install -r requirements.txt
```

### 9.6 版本控制（.gitignore）

`.gitignore` 已配置，忽略：虚拟环境、密钥、缓存、日志、向量库数据、模型文件、评估生成物。
源码、文档、配置模板、评估集、知识库正常提交。

