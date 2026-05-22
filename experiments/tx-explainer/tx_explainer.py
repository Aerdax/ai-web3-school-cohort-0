#!/usr/bin/env python3
"""
交易解释器（最小版本）
核心设计原则：链上事实 / ABI 解码 / LLM 推断 明确分层，不混淆来源
"""

import sys
import json
import os
import requests
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

RPC_URL = os.getenv("ETH_RPC_URL", "https://eth.llamarpc.com")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

w3 = Web3(Web3.HTTPProvider(RPC_URL))


# ── 数据序列化 ────────────────────────────────────────────

def to_json(obj):
    """将 web3 返回的 HexBytes/AttributeDict 等类型转为可序列化格式"""
    if isinstance(obj, bytes):
        return "0x" + obj.hex()
    if isinstance(obj, dict):
        return {k: to_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_json(i) for i in obj]
    return obj


# ── 链上数据获取 ──────────────────────────────────────────

def fetch_abi(address: str) -> list | None:
    """从 Etherscan 获取合约 ABI（链下索引服务，需 API Key）"""
    if not ETHERSCAN_API_KEY:
        return None
    try:
        resp = requests.get(
            "https://api.etherscan.io/v2/api",
            params={
                "chainid": "1",
                "module": "contract",
                "action": "getabi",
                "address": address,
                "apikey": ETHERSCAN_API_KEY,
            },
            timeout=10,
        )
        data = resp.json()
        if data.get("status") == "1":
            return json.loads(data["result"])
    except Exception:
        pass
    return None


def decode_input(input_data, abi: list | None) -> dict:
    """解码交易输入数据。来源：链上输入字段 + ABI 解码"""
    hex_data = ("0x" + input_data.hex()) if isinstance(input_data, bytes) else (input_data or "0x")

    if hex_data in ("0x", ""):
        return {"decoded": False, "note": "纯 ETH 转账，无合约调用数据"}

    if not abi:
        return {"decoded": False, "selector": hex_data[:10], "note": "无 ABI，无法解码函数名"}

    try:
        contract = w3.eth.contract(abi=abi)
        func, params = contract.decode_function_input(hex_data)
        return {
            "decoded": True,
            "function": func.fn_name,
            "params": to_json(dict(params)),
        }
    except Exception:
        return {"decoded": False, "selector": hex_data[:10], "note": "ABI 存在但解码失败"}


def decode_logs(logs, to_addr: str, abi: list | None) -> list:
    """
    解码事件日志。
    注意：交易产生的日志可能来自多个合约，这里只用主合约 ABI 解码。
    来自其他合约的日志（如被调用的代币合约）可能无法解码。
    """
    results = []
    for log in logs:
        log_dict = dict(log)
        entry = {
            "address": log_dict.get("address", ""),
            "decoded": False,
            "note": "",
        }

        # 只有当 log 来自主合约且有 ABI 时才尝试解码
        if abi and log_dict.get("address", "").lower() == to_addr.lower():
            for event_item in abi:
                if event_item.get("type") != "event":
                    continue
                try:
                    event_class = getattr(w3.eth.contract(abi=abi).events, event_item["name"])
                    result = event_class().process_log(log)
                    entry["decoded"] = True
                    entry["event"] = result["event"]
                    entry["args"] = to_json(dict(result["args"]))
                    break
                except Exception:
                    continue
        else:
            topics = log_dict.get("topics", [])
            entry["topic0"] = topics[0].hex() if topics else ""
            entry["note"] = "来自其他合约，无对应 ABI"

        if not entry["decoded"] and not entry.get("note"):
            entry["note"] = "ABI 存在但事件解码失败"

        results.append(entry)
    return results


# ── 构建事实块 ────────────────────────────────────────────

def build_facts(tx_hash: str) -> dict:
    """
    读取链上数据，构建带来源标注的事实块。
    所有字段均标注数据来源，供 LLM 和用户识别可信度。
    """
    print("[*] 读取交易和收据...")
    try:
        tx = w3.eth.get_transaction(tx_hash)
        receipt = w3.eth.get_transaction_receipt(tx_hash)
    except Exception as e:
        print(f"[!] 无法读取交易：{e}")
        sys.exit(1)

    to_addr = tx.get("to") or receipt.get("contractAddress") or ""

    abi = None
    abi_note = "无（未提供 ETHERSCAN_API_KEY）"
    if to_addr and ETHERSCAN_API_KEY:
        print("[*] 获取合约 ABI...")
        abi = fetch_abi(to_addr)
        abi_note = "Etherscan（合约已验证源码）" if abi else "Etherscan（未找到，可能未验证）"

    print("[*] 解码数据...")
    value_eth = float(w3.from_wei(tx.get("value", 0), "ether"))
    gas_price = tx.get("gasPrice") or tx.get("maxFeePerGas") or 0
    fee_eth = float(w3.from_wei(receipt.get("gasUsed", 0) * gas_price, "ether"))

    return {
        # 来源声明——供 LLM 理解数据可信度
        "_sources": {
            "rpc_data": "来自 Ethereum RPC，链上不可篡改数据",
            "abi_data": abi_note,
            "llm_inference": "下方 LLM 解释中标注 [推断] 的内容由模型生成，不保证准确",
        },
        # 核心交易信息（全部来自 RPC）
        "transaction": {
            "hash": tx_hash,
            "block": tx.get("blockNumber"),
            "status": "成功" if receipt.get("status") == 1 else "失败",
            "from_address": tx.get("from"),
            "to_address": to_addr,
            "eth_value": value_eth,
            "fee_eth": round(fee_eth, 8),
            "gas_used": receipt.get("gasUsed"),
        },
        # 调用信息（输入字节来自链上，函数名来自 ABI 解码）
        "call": decode_input(tx.get("input"), abi),
        # 事件日志（日志本身来自链上，事件名和参数名来自 ABI 解码）
        "events": decode_logs(receipt.get("logs", []), to_addr, abi),
    }


# ── LLM 解释 ─────────────────────────────────────────────

SYSTEM = (
    "你是区块链交易分析助手。你的核心职责是区分链上事实和你的推断。"
    "对任何你不确定的内容，直接说明'不确定'，不要猜测或填补空白。"
)

PROMPT = """以下是一笔以太坊交易的结构化链上数据，请按格式分析。

```json
{facts}
```

请按以下结构输出（保留标题，内容用中文）：

## 1. 用户发起了什么动作
说明这笔交易的行为目的。

## 2. 涉及的资产和地址
逐项列出，每项后标注 [链上事实] 或 [模型推断]。

## 3. 来源说明
- **链上事实**（直接来自 RPC / 事件日志）：……
- **模型推断**（基于 ABI 解码、地址识别、行为模式）：……
- **无法确认**（需要外部数据库或私有信息）：……

## 4. 模型不确定的地方
明确列出无法确认的内容（合约用途、地址身份、代币价格等）。

## 5. 签署类似交易前应检查什么
具体可操作的检查点，不要泛泛而谈。"""


def explain(facts: dict) -> None:
    facts_str = json.dumps(facts, ensure_ascii=False, indent=2)
    prompt = PROMPT.format(facts=facts_str)

    if ANTHROPIC_API_KEY:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            print("[*] 调用 LLM（流式输出）...\n")
            with client.messages.stream(
                model="claude-haiku-4-5-20251001",
                max_tokens=1500,
                system=SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                for text in stream.text_stream:
                    print(text, end="", flush=True)
            print("\n")
            return
        except ImportError:
            print("[!] 未安装 anthropic，请运行: pip install anthropic")
        except Exception as e:
            print(f"[!] LLM 调用失败: {e}")

    # 无 API Key 时，输出结构化 Prompt 供手动使用
    print("\n" + "=" * 60)
    print("未检测到 ANTHROPIC_API_KEY")
    print("以下 Prompt 可直接粘贴到 Claude.ai 或任何 LLM 界面：")
    print("=" * 60 + "\n")
    print(prompt)


# ── 主流程 ────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("用法: python tx_explainer.py <交易哈希>")
        print("示例: python tx_explainer.py 0xabc123...")
        sys.exit(1)

    tx_hash = sys.argv[1].strip()
    print(f"\n=== 交易解释器 | {tx_hash[:18]}... ===\n")

    facts = build_facts(tx_hash)

    print("\n── 链上事实（可验证数据）─────────────────────────────")
    print(json.dumps(facts, ensure_ascii=False, indent=2))

    print("\n── LLM 解释（含不确定性标注）────────────────────────")
    explain(facts)

    print("=== 完成 ===\n")


if __name__ == "__main__":
    main()
