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
llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY") or "placeholder").bind_tools(TOOLS)
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
        "answer": result["messages"][-1].content or "",
        "trace": result["trace"],
        "steps": len(result["trace"]),
    }
