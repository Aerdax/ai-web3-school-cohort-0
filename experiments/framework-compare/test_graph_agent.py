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
