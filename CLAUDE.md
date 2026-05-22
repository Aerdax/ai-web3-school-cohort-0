# AI × Web3 School — Learning Agent Context

## 项目身份

这是 Aerdax 在 [AI × Web3 School](https://aiweb3.school) Cohort 0 的个人学习仓库。
Learning Agent 的启动 Prompt：https://aiweb3.school/learning-agent.zh.txt  
课程 Handbook：https://aiweb3.school/zh/handbook/  
打卡平台：https://web3career.build/zh/programs/AI-Web3-School#tab=learning

## 学员画像

- AI 基础：有基础；Web3 基础：有基础；编程能力：能独立开发
- 目标方向：开发 / 技术
- 每日投入：2–3 小时；输出语言：中文

## 每日工作流

每次新会话，按以下流程推进：

1. **检查当日 daily note**：`daily/YYYY-MM-DD.md`，确认今日任务和学习路径
2. **阅读 Handbook 对应章节**（用户自行阅读后告知收获）
3. **完成实践任务**（见 `tasks/` 和 `experiments/`）
4. **整理打卡草稿**（格式见下方）
5. **更新 daily note 和 learning-plan.md**（标记已完成任务）

## 打卡草稿格式

每日打卡内容包含四项，直接提供可粘贴的纯文本：

```
今日完成：[具体完成内容]
学到的关键点：[核心概念或感悟]
遇到的问题：[问题和解决方式]
明日计划：[下一步]
```

## 目录结构

```
daily/          每日学习笔记 YYYY-MM-DD.md
tasks/          课程任务记录
experiments/    代码实验和 demo
handbook-feedback/  Handbook 反馈
submissions/    提交记录
templates/      笔记模板
```

## 已完成实验

| 实验 | 路径 | 说明 |
|------|------|------|
| 交易解释器 | `experiments/tx-explainer/` | 链上事实 / ABI 解码 / LLM 推断三层分离 |

### 交易解释器运行方式

```bash
cd experiments/tx-explainer
# .env 已配置（不在 git 中）
.venv/bin/python tx_explainer.py <以太坊交易哈希>
```

依赖：`web3`, `requests`, `python-dotenv`, `anthropic`（可选）  
RPC：`https://ethereum.publicnode.com`（无需 API Key）  
Etherscan API Key 已配置在 `.env` 中（V2 endpoint）

## 安全提醒

此仓库为**公开仓库**。`.env` 已在 `.gitignore` 中，API Key 不得提交。

## 开始新会话时

用户说"开始今日学习"时：
1. 读取今日 `daily/` 笔记（或创建新的）
2. 询问今日学习路径（最小 / 推荐 / 挑战）
3. 询问 Handbook 阅读进度
4. 按推进顺序陪跑
