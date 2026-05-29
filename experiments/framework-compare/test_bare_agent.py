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
