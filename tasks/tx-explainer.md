# 任务记录：交易解释器（最小版本）

> 来源：Handbook — 大语言模型（LLM）章节最小实践  
> 日期：2026-05-22  
> 状态：已完成

## 任务说明

输入一笔交易哈希，读取交易详情、事件日志和合约 ABI，让 LLM 生成解释。
输出必须包含：
- 用户发起了什么动作
- 涉及哪些资产和地址
- 哪些信息来自链上数据，哪些是模型推断
- 模型不确定的地方
- 签类似交易前应检查什么

练习重点：把**模型生成、链上事实、来源边界、不确定性**分开。

## 我的方案

三层分离架构：

```
链上数据层（RPC）
    ↓ 不可篡改的事实
解码层（ABI + etherscan）
    ↓ 把 bytes 变成可读结构，但需标注"ABI 来源"
LLM 推断层（Claude）
    ↓ 生成解释，强制标注 [链上事实] vs [模型推断]
```

关键设计：`_sources` 字段随数据一起传给 LLM，明确声明每一层的可信度。

## 实现细节

- 语言：Python 3
- 链上数据：`web3.py` + 公共 RPC（`ethereum.publicnode.com`）
- ABI 获取：Etherscan API（可选，无 key 时输出 raw selector）
- LLM：Anthropic Claude API（可选，无 key 时输出结构化 Prompt）
- 代码位置：`experiments/tx-explainer/tx_explainer.py`

## 运行方法

```bash
cd experiments/tx-explainer
cp .env.example .env   # 填入可选的 API Keys
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
ETH_RPC_URL=https://ethereum.publicnode.com .venv/bin/python tx_explainer.py <TX_HASH>
```

## 输出结构

```
── 链上事实（可验证数据）
{
  "_sources": { ... },        ← 来源声明
  "transaction": { ... },     ← RPC 数据，不可篡改
  "call": { ... },            ← 输入数据 + ABI 解码
  "events": [ ... ]           ← 事件日志 + ABI 解码
}

── LLM 解释（含不确定性标注）
## 1. 用户发起了什么动作
## 2. 涉及的资产和地址  [链上事实] / [模型推断]
## 3. 来源说明
## 4. 模型不确定的地方
## 5. 签署前应检查什么
```

## 复盘

**顺利的部分：**
- `_sources` 元数据设计自然地把可信度传达给 LLM
- 无 API Key 时 fallback 到打印 Prompt，学习成本低

**遇到的困难：**
- llamarpc.com 和 Ankr 免费节点不稳定，换用 publicnode.com
- 老区块历史数据（如第一笔 ETH 转账）在部分节点不可用

**延伸方向：**
- 加入 ERC-20 Transfer 事件的通用解码（不依赖主合约 ABI）
- 多链支持（Polygon、Base）
- 把不确定性评分量化（high/medium/low confidence）

## 提交记录

- 提交时间：（手动填写）
- 提交链接：https://web3career.build/zh/programs/AI-Web3-School#tab=learning
