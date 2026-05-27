"""
DAO 提案研究 Agent - 最小实践

演示重点：State 在每个步骤间显式流动，不藏在 prompt 历史里。
每个 step 函数签名：(state: AgentState) -> AgentState
"""

import os
import json
import requests
from dataclasses import dataclass, field
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.1-8b-instant"


# ── State ──────────────────────────────────────────────────────────────────────

@dataclass
class AgentState:
    # 输入
    proposal_id: str

    # 各步骤写入的结果
    proposal_title: str = ""
    proposal_text: str = ""
    proposal_author: str = ""
    proposal_space: str = ""
    vote_end: str = ""

    pros: list = field(default_factory=list)
    cons: list = field(default_factory=list)
    risks: list = field(default_factory=list)
    missing_info: list = field(default_factory=list)
    checklist: list = field(default_factory=list)
    verdict: str = ""   # needs_review | ready_to_vote | high_risk

    # 权限升级：投票模拟（需人工确认才能进入）
    proposal_choices: list = field(default_factory=list)  # 从 Snapshot 读取的选项
    user_choice: int = 0             # 用户选择的选项编号（1-based）
    user_confirmed: bool = False     # 人工确认标记
    confirmation_time: str = ""      # 确认时间戳，写入 State 供审计
    vote_draft: dict = field(default_factory=dict)  # 生成的投票草稿结构

    # 审计轨迹（State 存在的意义之一）
    steps_completed: list = field(default_factory=list)
    sources_used: list = field(default_factory=list)
    errors: list = field(default_factory=list)


# ── 工具函数 ───────────────────────────────────────────────────────────────────

def call_llm(prompt: str, json_mode: bool = False) -> str:
    body = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
        json=body,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def parse_json_from_llm(text: str) -> dict:
    """从 LLM 输出里提取 JSON，容忍 markdown 代码块包裹。"""
    import re
    if not text or not text.strip():
        raise ValueError("LLM 返回空内容")
    match = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    raw = match.group(1) if match else text
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"LLM 输出中找不到 JSON 对象，原始内容：{text[:200]}")
    return json.loads(raw[start:end])


# ── Steps ──────────────────────────────────────────────────────────────────────

def step_fetch_proposal(state: AgentState) -> AgentState:
    """从 Snapshot GraphQL API 读取提案，只读，无副作用。"""
    print(f"\n[Step 1] 读取提案 {state.proposal_id} ...")

    query = """
    query Proposal($id: String!) {
      proposal(id: $id) {
        id title body author choices space { id name }
        start end state scores_total
      }
    }
    """
    resp = requests.post(
        "https://hub.snapshot.org/graphql",
        json={"query": query, "variables": {"id": state.proposal_id}},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json().get("data", {}).get("proposal")

    if not data:
        state.errors.append("Snapshot API 未返回提案数据，请检查 proposal_id")
        return state

    state.proposal_title = data.get("title", "")
    state.proposal_text = (data.get("body") or "")[:4000]   # 截断避免超 token
    state.proposal_author = data.get("author", "")
    state.proposal_space = data.get("space", {}).get("name", "")
    state.vote_end = datetime.utcfromtimestamp(data["end"]).strftime("%Y-%m-%d %H:%M UTC")

    state.proposal_choices = data.get("choices") or []
    state.sources_used.append(f"https://snapshot.org/#/{data['space']['id']}/proposal/{state.proposal_id}")
    state.steps_completed.append("fetch_proposal")
    print(f"  ✓ 标题：{state.proposal_title}")
    print(f"  ✓ 空间：{state.proposal_space}  投票截止：{state.vote_end}")
    return state


def step_analyze_content(state: AgentState) -> AgentState:
    """LLM 分析提案内容，提取 pros / cons / risks，写入 State。"""
    if "fetch_proposal" not in state.steps_completed:
        state.errors.append("step_analyze_content 跳过：fetch_proposal 未完成")
        return state

    print("\n[Step 2] 分析提案内容 ...")

    prompt = f"""你是一位 DAO 治理研究员，请分析以下提案并返回 JSON。

提案标题：{state.proposal_title}
提案内容：
{state.proposal_text}

请返回如下 JSON（不要添加其他文字）：
{{
  "pros": ["支持理由1", "支持理由2"],
  "cons": ["反对理由1", "反对理由2"],
  "risks": ["风险点1", "风险点2"]
}}"""

    try:
        result = parse_json_from_llm(call_llm(prompt, json_mode=True))
        state.pros = result.get("pros", [])
        state.cons = result.get("cons", [])
        state.risks = result.get("risks", [])
        state.steps_completed.append("analyze_content")
        print(f"  ✓ pros:{len(state.pros)}  cons:{len(state.cons)}  risks:{len(state.risks)}")
    except Exception as e:
        state.errors.append(f"step_analyze_content 解析失败: {e}")

    return state


def step_identify_gaps(state: AgentState) -> AgentState:
    """LLM 找出提案中缺失的关键信息，写入 State。"""
    if "analyze_content" not in state.steps_completed:
        state.errors.append("step_identify_gaps 跳过：analyze_content 未完成")
        return state

    print("\n[Step 3] 识别缺失信息 ...")

    prompt = f"""你是一位 DAO 治理审查员。以下提案在投票前缺少哪些关键信息？

提案标题：{state.proposal_title}
已识别的风险：{json.dumps(state.risks, ensure_ascii=False)}
提案内容（节选）：
{state.proposal_text[:2000]}

返回 JSON：
{{
  "missing_info": ["缺失项1", "缺失项2"]
}}"""

    try:
        result = parse_json_from_llm(call_llm(prompt, json_mode=True))
        state.missing_info = result.get("missing_info", [])
        print(f"  ✓ 发现 {len(state.missing_info)} 项缺失信息")
    except Exception as e:
        state.errors.append(f"step_identify_gaps 解析失败（降级为空列表）: {e}")
        state.missing_info = []
        print(f"  ⚠️  解析失败，缺失信息设为空，继续执行")

    # 无论是否解析成功，都标记完成，不阻断下游步骤
    state.steps_completed.append("identify_gaps")
    return state


def step_build_checklist(state: AgentState) -> AgentState:
    """LLM 生成投票前检查清单，写入 State。不投票，只生成清单。"""
    if "identify_gaps" not in state.steps_completed:
        state.errors.append("step_build_checklist 跳过：identify_gaps 未完成")
        return state

    print("\n[Step 4] 生成投票前检查清单 ...")

    prompt = f"""基于以下分析结果，为投票人生成一份投票前检查清单。

提案：{state.proposal_title}
支持理由：{json.dumps(state.pros, ensure_ascii=False)}
反对理由：{json.dumps(state.cons, ensure_ascii=False)}
风险：{json.dumps(state.risks, ensure_ascii=False)}
缺失信息：{json.dumps(state.missing_info, ensure_ascii=False)}

返回 JSON：
{{
  "checklist": ["检查项1", "检查项2"],
  "verdict": "needs_review"
}}

verdict 只能是以下三个值之一：
- "ready_to_vote"：信息充分，风险可接受
- "needs_review"：存在缺失信息或中等风险，建议先确认
- "high_risk"：存在重大风险或关键信息缺失，强烈建议暂缓投票"""

    try:
        result = parse_json_from_llm(call_llm(prompt, json_mode=True))
        state.checklist = result.get("checklist", [])
        state.verdict = result.get("verdict", "needs_review")
        state.steps_completed.append("build_checklist")
        print(f"  ✓ 生成 {len(state.checklist)} 条检查项，verdict: {state.verdict}")
    except Exception as e:
        state.errors.append(f"step_build_checklist 解析失败: {e}")

    return state


# ── 权限升级：投票模拟（需人工确认）─────────────────────────────────────────────

def step_simulate_vote(state: AgentState) -> AgentState:
    """
    生成投票交易草稿——只读分析之后的权限升级步骤。

    设计原则：
    - 只读步骤自动执行，写入/授权步骤必须人工确认。
    - 本步骤不提交任何交易，只生成草稿结构供用户核查。
    - 用户的确认行为本身写入 State，形成审计记录。
    """
    if "build_checklist" not in state.steps_completed:
        state.errors.append("step_simulate_vote 跳过：build_checklist 未完成")
        return state

    print("\n" + "─" * 60)
    print("[Step 5] 投票模拟（权限升级步骤）")
    print("─" * 60)

    # ── Policy 检查：根据 verdict 决定是否放行 ──────────────────────────────────
    if state.verdict == "high_risk":
        print(f"\n🚨 Policy 拦截：当前 verdict 为 high_risk")
        print("  风险项：")
        for r in state.risks:
            print(f"    · {r}")
        print("  缺失信息：")
        for m in state.missing_info:
            print(f"    · {m}")
        print("\n  系统建议暂缓投票。如需强制继续，请输入 OVERRIDE（否则直接回车跳过）：", end="")
        override = input().strip()
        if override != "OVERRIDE":
            state.steps_completed.append("simulate_vote_blocked")
            state.errors.append("simulate_vote：用户未覆盖 high_risk 拦截，步骤终止")
            print("  已跳过投票模拟。")
            return state
        print("  ⚠️  用户强制覆盖 high_risk 拦截，继续执行。")

    elif state.verdict == "needs_review":
        print(f"\n⚠️  当前 verdict 为 needs_review，存在以下缺失信息：")
        for m in state.missing_info:
            print(f"    · {m}")
        print("\n  是否仍要继续生成投票草稿？(y/N)：", end="")
        ans = input().strip().lower()
        if ans != "y":
            state.steps_completed.append("simulate_vote_skipped")
            print("  已跳过投票模拟。")
            return state

    # ── 展示可选选项 ────────────────────────────────────────────────────────────
    print(f"\n提案：{state.proposal_title}")
    print(f"可选项：")
    for i, choice in enumerate(state.proposal_choices, 1):
        print(f"  {i}. {choice}")

    print(f"\n请输入选项编号（1–{len(state.proposal_choices)}），或回车跳过：", end="")
    raw = input().strip()
    if not raw.isdigit() or not (1 <= int(raw) <= len(state.proposal_choices)):
        state.steps_completed.append("simulate_vote_skipped")
        print("  无效输入，已跳过投票模拟。")
        return state

    state.user_choice = int(raw)
    chosen_label = state.proposal_choices[state.user_choice - 1]

    # ── 生成草稿，展示给用户，再次确认 ────────────────────────────────────────
    space_id = state.sources_used[0].split("#/")[1].split("/proposal")[0] if state.sources_used else "unknown"
    state.vote_draft = {
        "domain": {"name": "snapshot", "version": "0.1.4"},
        "message": {
            "space": space_id,
            "proposal": state.proposal_id,
            "choice": state.user_choice,
            "choice_label": chosen_label,
            "reason": "",
            "app": "dao-research-agent",
            "metadata": "{}",
        },
        "note": "草稿仅供核查，提交须由用户在 Snapshot 网页使用钱包手动签名，本工具不执行实际提交。",
    }

    print(f"\n── 即将生成的投票草稿 ──")
    print(json.dumps(state.vote_draft, ensure_ascii=False, indent=2))

    print(f"\n⚠️  最终确认：以上草稿仅供核查，不会自动提交。确认记录将写入 State 审计轨迹。")
    print(f"确认生成此草稿？(y/N)：", end="")
    final = input().strip().lower()

    if final == "y":
        state.user_confirmed = True
        state.confirmation_time = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        state.steps_completed.append("simulate_vote_confirmed")
        print(f"  ✓ 草稿已确认，确认时间：{state.confirmation_time}")
        print(f"  提交请前往：{state.sources_used[0]}")
    else:
        state.user_confirmed = False
        state.vote_draft = {}
        state.steps_completed.append("simulate_vote_declined")
        print("  已取消，草稿未保留。")

    return state


# ── 输出 ───────────────────────────────────────────────────────────────────────

def print_report(state: AgentState):
    VERDICT_LABEL = {
        "ready_to_vote": "✅ 可以投票",
        "needs_review":  "⚠️  建议先复核",
        "high_risk":     "🚨 高风险，暂缓投票",
    }

    print("\n" + "=" * 60)
    print(f"DAO 提案研究报告")
    print("=" * 60)
    print(f"提案：{state.proposal_title}")
    print(f"空间：{state.proposal_space}")
    print(f"投票截止：{state.vote_end}")
    print(f"来源：{', '.join(state.sources_used)}")

    print(f"\n── 支持理由 ──")
    for i, p in enumerate(state.pros, 1):
        print(f"  {i}. {p}")

    print(f"\n── 反对理由 ──")
    for i, c in enumerate(state.cons, 1):
        print(f"  {i}. {c}")

    print(f"\n── 风险点 ──")
    for i, r in enumerate(state.risks, 1):
        print(f"  {i}. {r}")

    print(f"\n── 缺失信息 ──")
    for i, m in enumerate(state.missing_info, 1):
        print(f"  {i}. {m}")

    print(f"\n── 投票前检查清单 ──")
    for i, item in enumerate(state.checklist, 1):
        print(f"  □ {item}")

    print(f"\n综合判断：{VERDICT_LABEL.get(state.verdict, state.verdict)}")

    if state.vote_draft:
        print(f"\n── 投票草稿（已确认，待手动提交）──")
        print(f"  选择：{state.vote_draft['message'].get('choice_label')}（选项 {state.vote_draft['message'].get('choice')}）")
        print(f"  确认时间：{state.confirmation_time}")
        print(f"  提交地址：{state.sources_used[0] if state.sources_used else '—'}")
        print(f"  ⚠️  实际提交须在 Snapshot 网页使用钱包手动签名。")

    print(f"\n── 审计轨迹 ──")
    print(f"  完成步骤：{' → '.join(state.steps_completed)}")
    if state.errors:
        print(f"  错误：{state.errors}")

    print("=" * 60)
    print("注意：本报告仅供参考，不构成投票建议。最终投票须由用户自行判断并手动操作。")


# ── Agent 主循环 ───────────────────────────────────────────────────────────────

def run_agent(proposal_id: str):
    state = AgentState(proposal_id=proposal_id)

    # 只读步骤：自动执行
    state = step_fetch_proposal(state)
    state = step_analyze_content(state)
    state = step_identify_gaps(state)
    state = step_build_checklist(state)

    print_report(state)

    # 权限升级步骤：需人工确认，在报告后询问是否进入
    print(f"\n是否进入投票模拟步骤（权限升级）？(y/N)：", end="")
    if input().strip().lower() == "y":
        state = step_simulate_vote(state)
        if state.vote_draft:
            print_report(state)

    return state


if __name__ == "__main__":
    import sys

    # 默认使用一个 ENS DAO 的真实提案（活跃）
    DEFAULT_PROPOSAL = "0xe4e1c052b2ea4f640cab27ddec326df6290d8996a9219b60cda4c4d4509f5f9a"

    proposal_id = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PROPOSAL
    run_agent(proposal_id)
