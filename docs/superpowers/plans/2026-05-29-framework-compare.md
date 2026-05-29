# Framework Compare 实验实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用同一个 Web3 tool-use 任务实现裸 API 和 LangGraph 两个版本，通过 compare.py 并排运行，生成 README 四维对比表。

**Architecture:** `tools.py` 提供 4 个共享纯函数；`bare_agent.py` 用手写 while loop 实现 tool-call 循环；`graph_agent.py` 用 LangGraph StateGraph 实现同等逻辑；`compare.py` 把同一问题输入两个版本并打印并排结果。

**Tech Stack:** Python 3.11+, web3.py, eth-account, langgraph, langchain-core, langchain-groq, openai (Groq compatible), pytest, python-dotenv

---

### Task 1: 项目初始化

**Files:**
- Create: `experiments/framework-compare/requirements.txt`
- Create: `experiments/framework-compare/.env.example`

- [ ] **Step 1: 创建目录和 requirements.txt**

```bash
mkdir -p experiments/framework-compare
```

`experiments/framework-compare/requirements.txt`:
```
web3>=6.0.0
eth-account>=0.10.0
langgraph>=0.2.0
langchain-core>=0.2.0
langchain-groq>=0.1.0
openai>=1.0.0
python-dotenv>=1.0.0
pytest>=7.0.0
```

- [ ] **Step 2: 创建 .env.example**

`experiments/framework-compare/.env.example`:
```
ETH_RPC_URL=https://eth.llamarpc.com
GROQ_API_KEY=your_groq_api_key_here
```

- [ ] **Step 3: 创建 venv 并安装依赖**

```bash
cd experiments/framework-compare
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Expected: 所有包安装成功，无报错。

- [ ] **Step 4: 确认 .env 中有需要的变量**

```bash
grep -E "ETH_RPC_URL|GROQ_API_KEY" ../../.env || echo "请在根目录 .env 补充 ETH_RPC_URL 和 GROQ_API_KEY"
```

- [ ] **Step 5: Commit**

```bash
git add experiments/framework-compare/requirements.txt experiments/framework-compare/.env.example
git commit -m "feat: framework-compare 项目初始化"
```

---

### Task 2: tools.py 实现 + 测试

**Files:**
- Create: `experiments/framework-compare/tools.py`
- Create: `experiments/framework-compare/test_tools.py`

- [ ] **Step 1: 写测试文件 test_tools.py（先失败）**

`experiments/framework-compare/test_tools.py`:
```python
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, ".")
import tools  # noqa: E402


def test_get_eth_balance_structure():
    with patch.object(tools, "w3") as mock_w3:
        mock_w3.to_checksum_address.return_value = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
        mock_w3.eth.get_balance.return_value = 1_500_000_000_000_000_000
        mock_w3.from_wei.return_value = 1.5
        result = tools.get_eth_balance("0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045")
    assert result["balance_eth"] == "1.5"
    assert "balance_wei" in result
    assert "address" in result


def test_get_tx_status_success():
    with patch.object(tools, "w3") as mock_w3:
        mock_w3.eth.get_transaction.return_value = {"from": "0xfrom", "to": "0xto", "value": 0}
        mock_receipt = MagicMock()
        mock_receipt.status = 1
        mock_receipt.gasUsed = 21000
        mock_w3.eth.get_transaction_receipt.return_value = mock_receipt
        mock_w3.from_wei.return_value = 0.0
        result = tools.get_tx_status("0x" + "a" * 64)
    assert result["status"] == "success"
    assert result["gas_used"] == 21000


def test_get_tx_status_pending():
    with patch.object(tools, "w3") as mock_w3:
        mock_w3.eth.get_transaction.return_value = {"from": "0xfrom", "to": "0xto", "value": 0}
        mock_w3.eth.get_transaction_receipt.return_value = None
        mock_w3.from_wei.return_value = 0.0
        result = tools.get_tx_status("0x" + "b" * 64)
    assert result["status"] == "pending"
    assert result["gas_used"] is None


def test_verify_signature_valid():
    from eth_account import Account
    from eth_account.messages import encode_defunct

    private_key = "0x" + "1" * 64
    account = Account.from_key(private_key)
    msg = encode_defunct(text="hello web3")
    sig = Account.sign_message(msg, private_key=private_key)
    result = tools.verify_signature("hello web3", sig.signature.hex(), account.address)
    assert result["valid"] is True
    assert result["recovered_address"].lower() == account.address.lower()


def test_verify_signature_invalid():
    from eth_account import Account
    from eth_account.messages import encode_defunct

    private_key = "0x" + "1" * 64
    account = Account.from_key(private_key)
    msg = encode_defunct(text="hello web3")
    sig = Account.sign_message(msg, private_key=private_key)
    result = tools.verify_signature("hello web3", sig.signature.hex(), "0x" + "2" * 40)
    assert result["valid"] is False


def test_check_token_allowance_structure():
    mock_contract = MagicMock()
    mock_contract.functions.allowance.return_value.call.return_value = 1_000_000
    mock_contract.functions.decimals.return_value.call.return_value = 6
    with patch.object(tools, "w3") as mock_w3:
        mock_w3.to_checksum_address.side_effect = lambda x: x
        mock_w3.eth.contract.return_value = mock_contract
        result = tools.check_token_allowance("0xtoken", "0xowner", "0xspender")
    assert result["allowance_formatted"] == "1.0"
    assert result["allowance_raw"] == "1000000"
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd experiments/framework-compare
.venv/bin/pytest test_tools.py -v
```

Expected: `ModuleNotFoundError: No module named 'tools'` 或导入失败。

- [ ] **Step 3: 实现 tools.py**

`experiments/framework-compare/tools.py`:
```python
import os

from dotenv import load_dotenv
from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3

load_dotenv()

w3 = Web3(Web3.HTTPProvider(os.getenv("ETH_RPC_URL", "https://eth.llamarpc.com")))

ERC20_ABI = [
    {
        "inputs": [{"name": "owner", "type": "address"}, {"name": "spender", "type": "address"}],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function",
    },
]


def get_eth_balance(address: str) -> dict:
    checksum = w3.to_checksum_address(address)
    balance_wei = w3.eth.get_balance(checksum)
    balance_eth = w3.from_wei(balance_wei, "ether")
    return {"address": checksum, "balance_eth": str(balance_eth), "balance_wei": str(balance_wei)}


def get_tx_status(tx_hash: str) -> dict:
    try:
        tx = w3.eth.get_transaction(tx_hash)
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        if receipt is None:
            status = "pending"
        elif receipt.status == 1:
            status = "success"
        else:
            status = "failed"
        return {
            "hash": tx_hash,
            "status": status,
            "from": tx["from"],
            "to": tx["to"],
            "value_eth": str(w3.from_wei(tx["value"], "ether")),
            "gas_used": receipt.gasUsed if receipt else None,
        }
    except Exception as e:
        return {"hash": tx_hash, "error": str(e)}


def verify_signature(message: str, signature: str, expected_address: str) -> dict:
    msg = encode_defunct(text=message)
    recovered = Account.recover_message(msg, signature=signature)
    return {
        "valid": recovered.lower() == expected_address.lower(),
        "recovered_address": recovered,
        "expected_address": expected_address,
    }


def check_token_allowance(token_address: str, owner: str, spender: str) -> dict:
    contract = w3.eth.contract(address=w3.to_checksum_address(token_address), abi=ERC20_ABI)
    allowance_raw = contract.functions.allowance(
        w3.to_checksum_address(owner), w3.to_checksum_address(spender)
    ).call()
    try:
        decimals = contract.functions.decimals().call()
        allowance_formatted = str(allowance_raw / (10**decimals))
    except Exception:
        allowance_formatted = str(allowance_raw)
    return {
        "token": token_address,
        "owner": owner,
        "spender": spender,
        "allowance_raw": str(allowance_raw),
        "allowance_formatted": allowance_formatted,
    }
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd experiments/framework-compare
.venv/bin/pytest test_tools.py -v
```

Expected: 6 个测试全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add experiments/framework-compare/tools.py experiments/framework-compare/test_tools.py
git commit -m "feat: framework-compare tools.py 4 个 Web3 工具 + 测试"
```

---

### Task 3: bare_agent.py 实现 + 测试

**Files:**
- Create: `experiments/framework-compare/bare_agent.py`
- Create: `experiments/framework-compare/test_bare_agent.py`

- [ ] **Step 1: 写测试文件 test_bare_agent.py（先失败）**

`experiments/framework-compare/test_bare_agent.py`:
```python
import json
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, ".")
import bare_agent  # noqa: E402


def test_run_bare_agent_no_tool_calls():
    mock_msg = MagicMock()
    mock_msg.tool_calls = None
    mock_msg.content = "The answer is 42."
    mock_msg.model_dump.return_value = {"role": "assistant", "content": "The answer is 42."}
    mock_response = MagicMock(choices=[MagicMock(message=mock_msg)])

    with patch.object(bare_agent, "client") as mock_client:
        mock_client.chat.completions.create.return_value = mock_response
        result = bare_agent.run_bare_agent("What is 6 times 7?")

    assert result["answer"] == "The answer is 42."
    assert result["steps"] == 0
    assert result["trace"] == []


def test_run_bare_agent_one_tool_call():
    tool_call = MagicMock()
    tool_call.id = "call_abc"
    tool_call.function.name = "get_eth_balance"
    tool_call.function.arguments = json.dumps({"address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"})

    msg1 = MagicMock()
    msg1.tool_calls = [tool_call]
    msg1.content = None
    msg1.model_dump.return_value = {"role": "assistant"}

    msg2 = MagicMock()
    msg2.tool_calls = None
    msg2.content = "The ETH balance is 1.5 ETH."
    msg2.model_dump.return_value = {"role": "assistant", "content": "The ETH balance is 1.5 ETH."}

    resp1 = MagicMock(choices=[MagicMock(message=msg1)])
    resp2 = MagicMock(choices=[MagicMock(message=msg2)])
    tool_result = {"address": "0x...", "balance_eth": "1.5", "balance_wei": "1500000000000000000"}

    with patch.object(bare_agent, "client") as mock_client, \
         patch.object(bare_agent, "dispatch", return_value=tool_result):
        mock_client.chat.completions.create.side_effect = [resp1, resp2]
        result = bare_agent.run_bare_agent("What is the ETH balance of 0xd8dA...?")

    assert result["answer"] == "The ETH balance is 1.5 ETH."
    assert result["steps"] == 1
    assert result["trace"][0]["tool"] == "get_eth_balance"


def test_dispatch_known_tool():
    with patch("bare_agent.get_eth_balance") as mock_fn:
        mock_fn.return_value = {"address": "0x123", "balance_eth": "0.5", "balance_wei": "500000000000000000"}
        result = bare_agent.dispatch("get_eth_balance", json.dumps({"address": "0x123"}))
    assert result["balance_eth"] == "0.5"


def test_dispatch_unknown_tool():
    result = bare_agent.dispatch("nonexistent_tool", "{}")
    assert "error" in result
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd experiments/framework-compare
.venv/bin/pytest test_bare_agent.py -v
```

Expected: `ModuleNotFoundError: No module named 'bare_agent'`

- [ ] **Step 3: 实现 bare_agent.py**

`experiments/framework-compare/bare_agent.py`:
```python
import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from tools import check_token_allowance, get_eth_balance, get_tx_status, verify_signature

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY", ""),
    base_url="https://api.groq.com/openai/v1",
)
MODEL = "llama-3.3-70b-versatile"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_eth_balance",
            "description": "Get ETH balance for an Ethereum address",
            "parameters": {
                "type": "object",
                "properties": {"address": {"type": "string", "description": "Ethereum address (0x...)"}},
                "required": ["address"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tx_status",
            "description": "Get transaction status, value, and gas usage by transaction hash",
            "parameters": {
                "type": "object",
                "properties": {"tx_hash": {"type": "string", "description": "Transaction hash (0x...)"}},
                "required": ["tx_hash"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verify_signature",
            "description": "Verify an Ethereum signature against an expected signer address",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Original message that was signed"},
                    "signature": {"type": "string", "description": "Hex signature string (0x...)"},
                    "expected_address": {"type": "string", "description": "Expected signer address"},
                },
                "required": ["message", "signature", "expected_address"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_token_allowance",
            "description": "Check ERC-20 token allowance granted by owner to spender",
            "parameters": {
                "type": "object",
                "properties": {
                    "token_address": {"type": "string", "description": "ERC-20 token contract address"},
                    "owner": {"type": "string", "description": "Token owner address"},
                    "spender": {"type": "string", "description": "Spender address"},
                },
                "required": ["token_address", "owner", "spender"],
            },
        },
    },
]

TOOL_REGISTRY = {
    "get_eth_balance": get_eth_balance,
    "get_tx_status": get_tx_status,
    "verify_signature": verify_signature,
    "check_token_allowance": check_token_allowance,
}


def dispatch(name: str, arguments: str) -> dict:
    fn = TOOL_REGISTRY.get(name)
    if not fn:
        return {"error": f"Unknown tool: {name}"}
    try:
        return fn(**json.loads(arguments))
    except Exception as e:
        return {"error": str(e)}


def run_bare_agent(question: str) -> dict:
    messages = [{"role": "user", "content": question}]
    trace = []

    while True:
        response = client.chat.completions.create(
            model=MODEL, messages=messages, tools=TOOLS, tool_choice="auto"
        )
        msg = response.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))

        if not msg.tool_calls:
            break

        for tc in msg.tool_calls:
            result = dispatch(tc.function.name, tc.function.arguments)
            trace.append({
                "tool": tc.function.name,
                "args": json.loads(tc.function.arguments),
                "result": result,
            })
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)})

    return {"answer": msg.content, "trace": trace, "steps": len(trace)}
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd experiments/framework-compare
.venv/bin/pytest test_bare_agent.py -v
```

Expected: 4 个测试全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add experiments/framework-compare/bare_agent.py experiments/framework-compare/test_bare_agent.py
git commit -m "feat: framework-compare bare_agent.py 手写 tool-call loop + 测试"
```

---

### Task 4: graph_agent.py 实现 + 测试

**Files:**
- Create: `experiments/framework-compare/graph_agent.py`
- Create: `experiments/framework-compare/test_graph_agent.py`

- [ ] **Step 1: 写测试文件 test_graph_agent.py（先失败）**

`experiments/framework-compare/test_graph_agent.py`:
```python
import sys
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage

sys.path.insert(0, ".")
import graph_agent  # noqa: E402


def test_run_graph_agent_returns_structure():
    mock_result = {
        "messages": [AIMessage(content="The balance is 1.5 ETH.")],
        "trace": [],
    }
    with patch.object(graph_agent, "app") as mock_app:
        mock_app.invoke.return_value = mock_result
        result = graph_agent.run_graph_agent("What is the ETH balance?")
    assert "answer" in result
    assert "trace" in result
    assert "steps" in result
    assert result["answer"] == "The balance is 1.5 ETH."
    assert result["steps"] == 0


def test_run_graph_agent_with_trace():
    mock_result = {
        "messages": [AIMessage(content="Balance is 2.0 ETH.")],
        "trace": [{"tool": "lc_get_eth_balance", "result": '{"balance_eth": "2.0"}'}],
    }
    with patch.object(graph_agent, "app") as mock_app:
        mock_app.invoke.return_value = mock_result
        result = graph_agent.run_graph_agent("What is the balance of 0xabc?")
    assert result["steps"] == 1
    assert result["trace"][0]["tool"] == "lc_get_eth_balance"


def test_should_continue_with_tool_calls():
    msg = MagicMock()
    msg.tool_calls = [MagicMock()]
    state = {"messages": [msg], "trace": []}
    assert graph_agent.should_continue(state) == "call_tools"


def test_should_continue_without_tool_calls():
    from langgraph.graph import END
    msg = MagicMock()
    msg.tool_calls = []
    state = {"messages": [msg], "trace": []}
    assert graph_agent.should_continue(state) == END
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd experiments/framework-compare
.venv/bin/pytest test_graph_agent.py -v
```

Expected: `ModuleNotFoundError: No module named 'graph_agent'`

- [ ] **Step 3: 实现 graph_agent.py**

`experiments/framework-compare/graph_agent.py`:
```python
import json
import operator
import os
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from tools import check_token_allowance, get_eth_balance, get_tx_status, verify_signature

load_dotenv()


@tool
def lc_get_eth_balance(address: str) -> str:
    """Get ETH balance for an Ethereum address."""
    return json.dumps(get_eth_balance(address))


@tool
def lc_get_tx_status(tx_hash: str) -> str:
    """Get transaction status, value, and gas usage by transaction hash."""
    return json.dumps(get_tx_status(tx_hash))


@tool
def lc_verify_signature(message: str, signature: str, expected_address: str) -> str:
    """Verify an Ethereum signature against an expected signer address."""
    return json.dumps(verify_signature(message, signature, expected_address))


@tool
def lc_check_token_allowance(token_address: str, owner: str, spender: str) -> str:
    """Check ERC-20 token allowance granted by owner to spender."""
    return json.dumps(check_token_allowance(token_address, owner, spender))


TOOLS = [lc_get_eth_balance, lc_get_tx_status, lc_verify_signature, lc_check_token_allowance]
llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY", "")).bind_tools(TOOLS)
tool_node = ToolNode(TOOLS)


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]
    trace: Annotated[list[dict], operator.add]


def call_model(state: AgentState) -> dict:
    response = llm.invoke(state["messages"])
    return {"messages": [response]}


def call_tools_node(state: AgentState) -> dict:
    result = tool_node.invoke({"messages": state["messages"]})
    new_trace = [
        {"tool": msg.name, "result": msg.content}
        for msg in result["messages"]
        if hasattr(msg, "name") and msg.name
    ]
    return {"messages": result["messages"], "trace": new_trace}


def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "call_tools"
    return END


graph = StateGraph(AgentState)
graph.add_node("call_model", call_model)
graph.add_node("call_tools", call_tools_node)
graph.add_edge(START, "call_model")
graph.add_conditional_edges("call_model", should_continue)
graph.add_edge("call_tools", "call_model")
app = graph.compile()


def run_graph_agent(question: str) -> dict:
    result = app.invoke({"messages": [HumanMessage(content=question)], "trace": []})
    return {
        "answer": result["messages"][-1].content,
        "trace": result["trace"],
        "steps": len(result["trace"]),
    }
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd experiments/framework-compare
.venv/bin/pytest test_graph_agent.py -v
```

Expected: 4 个测试全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add experiments/framework-compare/graph_agent.py experiments/framework-compare/test_graph_agent.py
git commit -m "feat: framework-compare graph_agent.py LangGraph 实现 + 测试"
```

---

### Task 5: compare.py

**Files:**
- Create: `experiments/framework-compare/compare.py`

- [ ] **Step 1: 实现 compare.py**

`experiments/framework-compare/compare.py`:
```python
import textwrap

from eth_account import Account
from eth_account.messages import encode_defunct

from bare_agent import run_bare_agent
from graph_agent import run_graph_agent

# 本地生成一个签名用于测试（不需要 RPC）
_private_key = "0x" + "a" * 64
_account = Account.from_key(_private_key)
_msg_text = "authorize payment 100 USDC to 0xSpender"
_sig = Account.sign_message(encode_defunct(text=_msg_text), private_key=_private_key)

TEST_QUESTIONS = [
    "vitalik.eth (0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045) 现在的 ETH 余额是多少？",
    (
        f"请验证这条签名是否来自地址 {_account.address}："
        f"消息='{_msg_text}'，签名={_sig.signature.hex()}"
    ),
    (
        "USDC 合约 (0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48) 中，"
        "地址 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 "
        "授权给 0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45 的额度是多少？"
    ),
]

WIDTH = 72


def print_comparison(question: str, bare: dict, graph: dict) -> None:
    print("\n" + "━" * WIDTH)
    print(f"问题：{textwrap.shorten(question, width=WIDTH - 4)}")
    print("─" * WIDTH)
    print(f"[bare]  steps={bare['steps']}  answer: {textwrap.shorten(str(bare['answer']), width=55)}")
    for t in bare["trace"]:
        print(f"        → {t['tool']}({list(t['args'].keys())})")
    print(f"[graph] steps={graph['steps']}  answer: {textwrap.shorten(str(graph['answer']), width=55)}")
    for t in graph["trace"]:
        print(f"        → {t['tool']}")


if __name__ == "__main__":
    print("Framework Compare — bare API vs LangGraph")
    print("同一问题跑两个 Agent 版本\n")
    for q in TEST_QUESTIONS:
        try:
            bare_result = run_bare_agent(q)
            graph_result = run_graph_agent(q)
            print_comparison(q, bare_result, graph_result)
        except Exception as e:
            print(f"\n[ERROR] {textwrap.shorten(q, 50)} → {e}")
    print("\n" + "━" * WIDTH)
    print("完成。查看 README.md 了解四维对比分析。")
```

- [ ] **Step 2: 运行 compare.py，观察输出**

```bash
cd experiments/framework-compare
.venv/bin/python compare.py
```

Expected: 3 个问题各打印 [bare] 和 [graph] 的结果，steps 和 answer 均有内容。第 2 题（verify_signature）不需要 RPC，应稳定成功。

- [ ] **Step 3: Commit**

```bash
git add experiments/framework-compare/compare.py
git commit -m "feat: framework-compare compare.py 并排运行对比"
```

---

### Task 6: README.md + 全套测试确认 + 最终 commit

**Files:**
- Create: `experiments/framework-compare/README.md`

- [ ] **Step 1: 运行全套测试，确认全部通过**

```bash
cd experiments/framework-compare
.venv/bin/pytest test_tools.py test_bare_agent.py test_graph_agent.py -v
```

Expected: 14 个测试全部 PASS，0 FAIL。

- [ ] **Step 2: 写 README.md**

根据 compare.py 的实际运行体验填写结论列（尤其是「代码可读性」和「定位错误」两列的个人感受）。

`experiments/framework-compare/README.md`:
```markdown
# Framework Compare：裸 API vs LangGraph

> Handbook「框架（Frameworks）」章节最小实践  
> 同一个 Web3 tool-use 任务，两种实现方式的四维对比。

## 运行方法

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# 确认根目录 .env 中有 ETH_RPC_URL 和 GROQ_API_KEY
.venv/bin/python compare.py
```

## 测试

```bash
.venv/bin/pytest test_tools.py test_bare_agent.py test_graph_agent.py -v
```

## 四维对比

| 维度 | bare_agent.py | graph_agent.py | 结论 |
|------|--------------|----------------|------|
| 代码可读性 | while loop 直白，100 行内完整 | 声明式 Graph，需理解 State/Node/Edge 概念 | bare 入门更快，graph 意图更清晰 |
| 加新工具 | 改 TOOLS 列表 + dispatch if/elif | 只改 TOOLS 列表，ToolNode 自动处理 | graph 扩展更干净 |
| 定位错误 | 靠手动 print trace，需在 loop 里埋点 | State 流动可查，trace 自动累积在 State | graph 多步骤错误更易排查 |
| 写回归测试 | mock messages list，边界模糊 | mock State 输入/输出，边界清晰 | graph 更易写测试 |
| **适合场景** | 简单单轮、工具少、快速原型 | 多步骤、需恢复、长期运行 | 按场景选择 |

## 关键结论

> Framework 不是让代码更少，而是让复杂度**显式化**。  
> bare_agent 在工具少时更透明；LangGraph 在多步骤、需追踪 State 时优势明显。  
> AI × Web3 场景（payment 流程、permission 检查）通常需要多步工具调用 + 可审计 trace，LangGraph 更适合生产。

## 文件说明

| 文件 | 说明 |
|------|------|
| `tools.py` | 4 个 Web3 纯函数工具（两个版本共享） |
| `bare_agent.py` | 裸 API 实现：手写 while loop |
| `graph_agent.py` | LangGraph 实现：State + Node + Edge |
| `compare.py` | 统一入口：同问题跑两个版本并排输出 |
| `test_tools.py` | tools 单元测试（6 个） |
| `test_bare_agent.py` | bare agent 单元测试（4 个） |
| `test_graph_agent.py` | graph agent 单元测试（4 个） |
```

- [ ] **Step 3: 最终 commit**

```bash
git add experiments/framework-compare/README.md
git commit -m "docs: framework-compare README 四维对比表"
```
