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
    # Look up from module globals so patch() works in tests
    import bare_agent as _self
    fn = getattr(_self, name, None)
    if fn is None or name not in TOOL_REGISTRY:
        return {"error": f"Unknown tool: {name}"}
    try:
        return fn(**json.loads(arguments))
    except Exception as e:
        return {"error": str(e)}


def run_bare_agent(question: str) -> dict:
    messages = [{"role": "user", "content": question}]
    trace = []
    max_steps = 10

    while len(trace) < max_steps:
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

    return {"answer": msg.content or "", "trace": trace, "steps": len(trace)}
