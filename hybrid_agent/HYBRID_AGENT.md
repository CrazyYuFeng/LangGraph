# LangGraph 项目使用文档

本项目包含两个子项目：**hybrid_agent**（按需智能查询）和 **weekly_report**（固定定时统计）。两者共享数据库和企微通知能力，但架构不同。

---

## 一、项目总览

```
LangGraph/
├── demo_basic.py          # 入门 demo（最简单的 StateGraph）
├── hybrid_agent/          # 多智能体协作（按需智能查询）★ 核心
├── weekly_report/         # 固定定时统计（每周一）
├── bin/ lib/ include/     # Python 虚拟环境
└── HYBRID_AGENT.md        # 本文档
```

### 两个子项目的区别

| 维度 | hybrid_agent | weekly_report |
|------|--------------|---------------|
| **架构** | LangGraph 多智能体 | LangGraph 确定性工作流 |
| **触发** | 用户随时说一句 | cron 定时（每周一） |
| **查询条件** | LLM 理解自然语言，灵活 | 代码写死 |
| **是否用 LLM** | 是（路由 + 理解 + 提取参数） | 否（纯确定性） |
| **企微通知** | 用户要求才发 | 每次都发 |

---

## 二、hybrid_agent —— 按需智能查询

### 2.1 架构

```
用户输入
   │
   ▼
┌─────────────────┐
│   Supervisor    │  DeepSeek 判断任务类型
└───────┬─────────┘
        │ 条件路由
   ┌────┴────┬─────────┬──────────┐
   ▼         ▼         ▼          ▼
Researcher  Coder     DBAgent   (直接回复)
 Web搜索    Python    结构化查询  简单问题
  (Tavily)  REPL     (SQL模板)
   │         │         │
   └────┬────┴────┬────┘
        ▼         ▼
     汇总回复 → END
```

### 2.2 目录结构

```
hybrid_agent/
├── config.py            # 配置（API key、数据库、企微 webhook）
├── main.py              # 入口
├── graph.py             # 组装整个图
├── supervisor.py        # 主管路由智能体
├── mock_helpers.py      # mock 模式辅助
├── workers/             # 各 Worker（ReAct 智能体）
│   ├── researcher.py    # 搜索 Worker
│   ├── coder.py         # 代码 Worker
│   └── db_agent.py      # 数据库 Worker
├── tools/               # 工具类模块
│   ├── web_search.py    # Tavily 搜索工具
│   ├── python_repl.py   # Python 执行工具
│   └── wecom_notifier.py# 企微通知工具
└── sql/                 # SQL 相关模块
    ├── query_templates.py   # 结构化查询模板（字段 + SQL）
    └── structured_query.py  # 结构化查询工具
```

### 2.3 核心设计：结构化查询（LLM 只填参数，不写 SQL）

**这是本项目最重要的设计。** 用户说"统计 CREDIT>15 且 STATUS=1 且 PLATFORM=iOS 的金额"时：

```
LLM 只提取参数：{"min_credit": 15, "status": 1, "platform": "iOS"}
   │
   ▼
sql/query_templates.py 用写死的 SQL 模板 + 参数执行（参数化，防注入）
```

**优势：**
- SQL 是写死的、经过测试的，不会出错
- LLM 只需要理解意图 + 提取参数，加再多条件也不会失控
- 参数化查询，安全
- 参数明确，可审计

**支持的过滤字段**（在 `sql/query_templates.py` 中定义）：
| 字段 | 类型 | 说明 |
|------|------|------|
| min_credit / max_credit | float | 金额范围 |
| start_time / end_time | str | 时间范围 |
| status | int | 状态 |
| pay_type | int | 支付类型 |
| user_id | int | 用户 |
| pid | int | 产品 |
| platform | str | 平台 |
| src | str | 来源 |

### 2.4 配置（config.py）

```python
OPENAI_API_KEY = "sk-..."           # DeepSeek API key
OPENAI_BASE_URL = "https://api.deepseek.com"  # API 端点
OPENAI_MODEL = "deepseek-v4-flash"  # 模型
TAVILY_API_KEY = "tvly-..."         # Tavily 搜索 key
DB_URL = "mysql+pymysql://user:pass@host:3306/db"  # 数据库
WECOM_WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..."  # 企微
```

### 2.5 运行方式

```bash
cd hybrid_agent

# 按需查询（不通知）
../bin/python main.py "统计 ORDER_INFO 表 CREDIT 大于 15 的金额"

# 多条件组合查询
../bin/python main.py "统计 ORDER_INFO 表 CREDIT 大于 15 且 STATUS 等于 1 且 PLATFORM 是 iOS 的金额"

# 时间范围 + 金额
../bin/python main.py "统计 2026-07-30 到 2026-07-31 之间 CREDIT 大于 15 的金额"

# 查询 + 发企微通知（用户明确要求才发）
../bin/python main.py "统计 ORDER_INFO 表 CREDIT 大于 15 的金额，发到群里通知一下"

# 计算 / 搜索
../bin/python main.py "计算 12345 * 6789"
../bin/python main.py "搜索 LangGraph 是什么"

# 简单问候
../bin/python main.py "你好"
```

---

## 三、weekly_report —— 固定定时统计

### 3.1 目录结构

```
weekly_report/
├── config.py          # 数据库 + 企微 webhook 配置
├── workflow.py        # LangGraph 确定性工作流
├── main.py            # 入口（支持 --save）
├── run_weekly.sh      # cron 触发脚本
├── wecom_notifier.py  # 企微通知
├── reports/           # 报告输出目录
└── logs/              # 运行日志
```

### 3.2 工作流

```
计算上周时间范围 → 查询 ORDER_INFO 统计 CREDIT>15 → 生成报告 → 企微通知 → END
```

### 3.3 运行方式

```bash
cd weekly_report
../bin/python main.py              # 运行并打印报告
../bin/python main.py --save       # 运行并保存到 reports/
./run_weekly.sh                    # 通过 cron 脚本运行（含日志）
```

### 3.4 配置 cron（每周一 09:00 自动执行）

```bash
crontab -e
# 添加这一行
0 9 * * 1 /Users/tme8000/workspace/LangGraph/weekly_report/run_weekly.sh
```

---

## 四、依赖安装

```bash
# 在项目根目录使用虚拟环境
./bin/pip install \
    langchain \
    langchain-openai \
    langchain-community \
    langchain-tavily \
    langchain-experimental \
    tavily-python \
    pymysql psycopg2-binary \
    sqlalchemy \
    requests \
    python-dotenv
```

> 注意：`langchain-experimental` 已弃用，本项目已自实现 Python 执行工具替代，仅保留以防其他依赖需要。

---

## 五、常见问题

### Q1: 为什么用 workflow 而不是 skill？
**答**：确定性、固定步骤的任务（如每周统计）用 workflow/脚本更可靠；需要 LLM 决策的任务（如按需查询）才需要依赖 LLM 的智能体。两者场景不同。

### Q2: 加很多过滤条件，LLM 会不会失控？
**答**：不会。本项目用结构化查询，LLM 只提取参数，SQL 由模板保证，条件再多也不会出错。

### Q3: 企微通知什么时候触发？
**答**：hybrid_agent 只在用户明确说"通知/发群里/推送"时才发；weekly_report 每次都发。

### Q4: 如何扩展新的查询场景？
**答**：在 `hybrid_agent/sql/query_templates.py` 的 `OrderQuery` 和 `build_sql` 中添加新字段即可，LLM 会自动识别。
