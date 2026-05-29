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
    try:
        recovered = Account.recover_message(msg, signature=signature)
        return {
            "valid": recovered.lower() == expected_address.lower(),
            "recovered_address": recovered,
            "expected_address": expected_address,
        }
    except Exception as e:
        return {"valid": False, "error": str(e)}


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
