# 混合智能体推荐方案（Hybrid Agent）

基于 **LangGraph** 的多智能体协作架构。采用经典的 **Supervisor（主管）+ 专业 Worker** 模式，这是 LangGraph 官方推荐、也最适合"混合智能体"的编排方式。

## 1. 架构总览

```
用户输入
   │
   ▼
┌─────────────────┐
│   Supervisor    │  OpenAI 判断：任务该交给哪个 Worker
│  (路由决策)     │
└───────┬─────────┘
        │ add_conditional_edges
        │
   ┌────┴────┬─────────┬──────────┐
   ▼         ▼         ▼          ▼
Researcher  Coder     DBAgent   (直接回复)
 Web搜索    Python    SQL查询   简单问题
  (Tavily)  REPL      (MySQL/PG)
   │         │         │
   └────┬────┴────┬────┘
        ▼         ▼
     汇总回复 → END
```

## 2. 为什么需要工具（回答核心疑问）

在多智能体协作里，**工具是 Worker 的"手脚"**。

- **Supervisor 负责"想"**：用 LLM 做路由决策，判断任务交给谁，本身不直接调用工具。
- **Worker 负责"干"**：每个 Worker 是一个 ReAct 智能体，内部循环「思考 → 调用工具 → 观察结果 → 再思考」，直到拿到答案。

| Worker | 挂载工具 | 解决什么问题 |
|--------|---------|-------------|
| **Researcher** | Tavily Web 搜索 | 查实时信息、资料、新闻 |
| **Coder** | Python REPL | 数学计算、跑代码、数据分析 |
| **DBAgent** | SQL 查询工具 | 读写数据库、查询结构化数据 |

## 3. 技术栈

| 组件 | 选型 | 说明 |
|------|------|------|
| 编排框架 | LangGraph 1.2.10 | 已安装 |
| 快速构建 ReAct Worker | langgraph-prebuilt 1.1.0 | 已安装，`create_react_agent` |
| OpenAI 接入 | langchain-openai | 需安装 |
| 工具集 | langchain-community | 需安装，提供 Tavily、Python REPL |
| Web 搜索 | tavily-python | 需安装 |
| MySQL 驱动 | pymysql | 需安装 |
| PostgreSQL 驱动 | psycopg2-binary | 需安装 |
| 配置管理 | python-dotenv | 需安装，读取 .env |

## 4. 目录结构

```
hybrid_agent/
├── .env              # 环境变量（API key、数据库连接）
├── tools.py          # 工具定义（搜索/代码/SQL）
├── supervisor.py     # 主管路由智能体
├── workers/
│   ├── __init__.py
│   ├── researcher.py # 搜索 Worker
│   ├── coder.py      # 代码 Worker
│   └── db_agent.py   # 数据库 Worker
├── graph.py          # 组装整个图
└── main.py           # 入口
```

## 5. 环境变量（.env）

```bash
OPENAI_API_KEY="sk-占位符"
TAVILY_API_KEY="tvly-占位符"
DB_URL="mysql+pymysql://user:pass@localhost:3306/dbname"
```

## 6. 安装命令

```bash
./bin/pip install langchain-openai langchain-community tavily-python pymysql psycopg2-binary python-dotenv
```

## 7. 运行方式

```bash
cd hybrid_agent
../bin/python main.py "帮我查一下2024年诺贝尔物理学奖得主"
../bin/python main.py "计算 12345 * 6789 等于多少"
../bin/python main.py "查询数据库里 users 表的前5条记录"
```

## 8. 关键设计决策

1. **Supervisor 用 OpenAI**：路由决策需要较强的理解能力。
2. **Worker 用 ReAct 循环**：`create_react_agent` 让 Worker 能自主多轮调用工具，比固定流程更灵活。
3. **工具隔离**：每个 Worker 只挂载自己需要的工具，减少 LLM 误用。
4. **数据库用环境变量**：`DB_URL` 灵活配置，不写死。
5. **占位符先跑通**：key 先用占位符，验证整体架构，后续填入真实 key。
