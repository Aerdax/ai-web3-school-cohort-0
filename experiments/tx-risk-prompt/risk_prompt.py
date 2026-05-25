#!/usr/bin/env python3
"""
交易风险摘要 Prompt（提示词章节最小实践）
验证点：Structured Output / 意图不匹配检测 / 不确定性标注
"""

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / "tx-explainer" / ".env")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

SYSTEM_PROMPT = Path(__file__).parent / "prompts" / "system.txt"

# ── 三组测试用例 ──────────────────────────────────────────

TEST_CASES = [
    {
        "name": "普通转账",
        "expect_risk": "low",
        "expect_approval": False,
        "input": {
            "target_address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
            "function_name": "transfer (native ETH)",
            "params": {
                "to": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
                "value": "0.1 ETH"
            },
            "asset_changes": [
                {"asset": "ETH", "direction": "out", "amount": "0.1", "confirmed": True}
            ],
            "simulation_result": {
                "success": True,
                "gas_used": 21000,
                "revert_reason": None
            },
            "user_intent": "给朋友转 0.1 ETH"
        }
    },
    {
        "name": "无限授权 approve MAX",
        "expect_risk": "high",
        "expect_approval": True,
        "input": {
            "target_address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            "function_name": "approve",
            "params": {
                "spender": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
                "amount": "115792089237316195423570985008687907853269984665640564039457584007913129639935"
            },
            "asset_changes": [],
            "simulation_result": {
                "success": True,
                "gas_used": 46000,
                "revert_reason": None
            },
            "user_intent": "授权 Uniswap 使用我的 USDC"
        }
    },
    {
        "name": "目标地址与意图不匹配",
        "expect_risk": "critical",
        "expect_approval": True,
        "input": {
            "target_address": "0x1111111254EEB25477B68fb85Ed929f73A960582",
            "function_name": "swap",
            "params": {
                "fromToken": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                "toToken": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
                "amount": "1000000000",
                "recipient": "0xDeadBeef0000000000000000000000000000dEaD"
            },
            "asset_changes": [
                {"asset": "USDC", "direction": "out", "amount": "1000", "confirmed": True},
                {"asset": "USDT", "direction": "in", "amount": "998",
                 "recipient": "0xDeadBeef0000000000000000000000000000dEaD", "confirmed": True}
            ],
            "simulation_result": {
                "success": True,
                "gas_used": 180000,
                "revert_reason": None
            },
            "user_intent": "把 1000 USDC 换成 USDT，存入我的钱包"
        }
    }
]

# ── LLM 调用 ──────────────────────────────────────────────

def call_llm(system: str, user_input: dict) -> dict | None:
    if not ANTHROPIC_API_KEY:
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
            system=system,
            messages=[{"role": "user", "content": json.dumps(user_input, ensure_ascii=False)}]
        )
        text = msg.content[0].text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"  [!] JSON 解析失败: {e}\n  原始输出: {text[:200]}")
        return None
    except Exception as e:
        print(f"  [!] 调用失败: {e}")
        return None


def validate(result: dict, case: dict) -> list[str]:
    """检查模型输出是否满足关键约束"""
    failures = []
    if result.get("risk_level") != case["expect_risk"]:
        failures.append(
            f"risk_level 期望 {case['expect_risk']}，实际 {result.get('risk_level')}"
        )
    if result.get("requires_human_approval") != case["expect_approval"]:
        failures.append(
            f"requires_human_approval 期望 {case['expect_approval']}，实际 {result.get('requires_human_approval')}"
        )
    if not result.get("uncertainties"):
        failures.append("uncertainties 为空，模型没有标注不确定性")
    if not result.get("recommended_user_checks"):
        failures.append("recommended_user_checks 为空")
    return failures


# ── 主流程 ────────────────────────────────────────────────

def main():
    system = SYSTEM_PROMPT.read_text(encoding="utf-8")
    print("\n=== 交易风险摘要 Prompt 测试 ===\n")

    if not ANTHROPIC_API_KEY:
        print("未检测到 ANTHROPIC_API_KEY，输出 Prompt 供手动测试\n")
        for i, case in enumerate(TEST_CASES, 1):
            print(f"{'─'*50}")
            print(f"测试 {i}：{case['name']}")
            print(f"期望 risk_level: {case['expect_risk']}  |  requires_human_approval: {case['expect_approval']}")
            print(f"\n[USER INPUT]\n{json.dumps(case['input'], ensure_ascii=False, indent=2)}")
            print()
        print("[SYSTEM PROMPT]\n")
        print(system)
        return

    passed = 0
    for i, case in enumerate(TEST_CASES, 1):
        print(f"── 测试 {i}：{case['name']} {'─' * max(1, 38 - len(case['name']))}")
        print(f"   期望：risk_level={case['expect_risk']}  requires_approval={case['expect_approval']}")

        result = call_llm(system, case["input"])
        if not result:
            print("   [SKIP] 无输出\n")
            continue

        failures = validate(result, case)
        if failures:
            print(f"   [FAIL] {'; '.join(failures)}")
        else:
            print(f"   [PASS] risk={result['risk_level']}  approval={result['requires_human_approval']}")
            passed += 1

        print(f"\n   摘要：{result.get('summary', '')}")
        if result.get("permissions_changed"):
            for p in result["permissions_changed"]:
                print(f"   授权：{p.get('type')} | amount={p.get('amount')} | {p.get('risk_note', '')}")
        if result.get("uncertainties"):
            print(f"   不确定性：{result['uncertainties'][0]}" +
                  (f" 等 {len(result['uncertainties'])} 项" if len(result["uncertainties"]) > 1 else ""))
        print()

    print(f"=== 结果：{passed}/{len(TEST_CASES)} 通过 ===\n")


if __name__ == "__main__":
    main()
