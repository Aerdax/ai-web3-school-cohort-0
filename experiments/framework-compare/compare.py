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
