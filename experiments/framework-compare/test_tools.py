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
