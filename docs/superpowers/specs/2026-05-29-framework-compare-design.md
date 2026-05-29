# Framework Compare 实验设计

**日期**：2026-05-29  
**实验路径**：`experiments/framework-compare/`  
**目标**：同一个 Web3 tool-use 任务，用裸 API 和 LangGraph 两种方式实现，通过四维对比理解框架的实际价值。

---

## 背景

Handbook 框架（Frameworks）章节最小实践：同一任务两种实现，对比可读性、可扩展性、错误定位、回归测试四个维度。结论用于明日 Week 2 例会笔记分享。

---

## 目录结构

```
experiments/framework-compare/
├── tools.py           # 4 个 Web3 工具（纯函数，无框架依赖）
├── bare_agent.py      # 裸 API 实现：手动 tool-call loop
├── graph_agent.py     # LangGraph 实现：Node + Edge + State
├── compare.py         # 统一入口：同问题跑两个版本，输出并排
├── requirements.txt
└── README.md          # 四维对比表 + 结论
```

---

## §1 数据流

两个版本输入输出完全一致：

```
用户问题 (str)
    │
    ▼
Agent Loop
    ├── LLM 判断：调哪个工具 / 直接回答
    ├── 执行工具（get_eth_balance / get_tx_status /
    │           verify_signature / check_token_allowance）
    └── 循环直到 LLM 不再调工具
    │
    ▼
{"answer": str, "trace": list[dict], "steps": int}
```

---

## §2 tools.py

4 个纯函数，两个 Agent 版本共用，不依赖任何框架。

```python
def get_eth_balance(address: str) -> dict:
    # eth_getBalance RPC
    # 返回 {"address", "balance_eth", "balance_wei"}

def get_tx_status(tx_hash: str) -> dict:
    # eth_getTransactionByHash + eth_getTransactionReceipt
    # 返回 {"hash", "status": "success"|"failed"|"pending",
    #        "from", "to", "value_eth", "gas_used"}

def verify_signature(message: str, signature: str, expected_address: str) -> dict:
    # eth_account 本地验证，不需要 RPC
    # 返回 {"valid": bool, "recovered_address", "expected_address"}

def check_token_allowance(token_address: str, owner: str, spender: str) -> dict:
    # ERC-20 allowance(owner, spender)
    # 返回 {"token", "owner", "spender", "allowance_raw", "allowance_formatted"}
```

**依赖**：`web3`（复用 tx-explainer）、`eth-account`  
**RPC**：从 `.env` 读 `ETH_RPC_URL`

---

## §3 bare_agent.py

手写 tool-call loop，不引入任何框架。

```python
TOOLS = [...]  # 4 个工具的 JSON Schema

def run_bare_agent(question: str) -> dict:
    messages = [{"role": "user", "content": question}]
    trace = []
    while True:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # 或 groq: llama-3.3-70b-versatile
            messages=messages, tools=TOOLS
        )
        msg = response.choices[0].message
        if not msg.tool_calls:
            break
        for tc in msg.tool_calls:
            result = dispatch(tc.function.name, tc.function.arguments)
            trace.append({"tool": tc.function.name, "result": result})
            messages.append(tool_result_message(tc.id, result))
    return {"answer": msg.content, "trace": trace, "steps": len(trace)}
```

- State = `messages` list，无显式 schema
- 失败处理：catch 工具异常，把错误信息塞回 messages
- Trace：手动 append

---

## §4 graph_agent.py

用 LangGraph 的 State + Node + Edge 替代手写 loop。

```python
class AgentState(TypedDict):
    messages: list[BaseMessage]
    trace: list[dict]

def call_model(state: AgentState) -> AgentState: ...
def call_tools(state: AgentState) -> AgentState: ...

def should_continue(state: AgentState) -> str:
    return "call_tools" if state["messages"][-1].tool_calls else END

graph = StateGraph(AgentState)
graph.add_node("call_model", call_model)
graph.add_node("call_tools", call_tools)
graph.add_edge(START, "call_model")
graph.add_conditional_edges("call_model", should_continue)
graph.add_edge("call_tools", "call_model")
app = graph.compile()
```

- State = 有类型约束的 `TypedDict`
- Loop 控制 = `should_continue` 条件边
- Trace 在 State 里流动
- 扩展（如 human-in-the-loop）只需插新 Node

---

## §5 compare.py

```python
TEST_QUESTIONS = [
    "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 的 ETH 余额是多少？",
    "交易 0xabc...123 的状态如何，花了多少 gas？",
    "地址 0xSpender 被 0xOwner 授权了多少 USDC？",
]

for q in TEST_QUESTIONS:
    bare  = run_bare_agent(q)
    graph = run_graph_agent(q)
    print_comparison(q, bare, graph)
```

输出：每个问题并排展示 answer + trace + steps。

---

## §6 README 四维对比表

| 维度 | bare_agent.py | graph_agent.py | 结论 |
|------|--------------|----------------|------|
| 代码可读性 | while loop 直白 | 声明式，初看需理解概念 | bare 入门更快 |
| 加工具 | 改 TOOLS + dispatch | 只改 TOOLS | graph 扩展更干净 |
| 定位错误 | 手动 print | State 流动可查 | graph 更易排查 |
| 写回归测试 | mock messages list | mock State，边界更清晰 | graph 更易测试 |
| **适合场景** | 简单单轮/少工具 | 多步骤/需恢复/长期运行 | — |

---

## 依赖

```
web3>=6.0.0
eth-account>=0.10.0
langgraph>=0.1.0
langchain-openai>=0.1.0
python-dotenv
```

## 环境变量

```
ETH_RPC_URL=...       # 复用 tx-explainer 已有配置
OPENAI_API_KEY=...    # 或 GROQ_API_KEY
```
