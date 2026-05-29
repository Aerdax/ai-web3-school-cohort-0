# Framework Compare：裸 API vs LangGraph

> Handbook「框架（Frameworks）」章节最小实践  
> 同一个 Web3 tool-use 任务，两种实现方式的四维对比。

## 运行方法

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# 确认根目录 .env 中有 ETH_RPC_URL 和 GROQ_API_KEY
.venv/bin/python compare.py
```

## 测试

```bash
.venv/bin/pytest test_tools.py test_bare_agent.py test_graph_agent.py -v
```

## 四维对比

| 维度 | bare_agent.py | graph_agent.py | 结论 |
|------|--------------|----------------|------|
| 代码可读性 | while loop 直白，100 行内完整 | 声明式 Graph，需理解 State/Node/Edge 概念 | bare 入门更快，graph 意图更清晰 |
| 加新工具 | 改 TOOLS 列表 + 手写 dispatch（注册表 + getattr）| 只改 TOOLS 列表，ToolNode 自动处理 | graph 扩展更干净 |
| 定位错误 | 靠手动 print trace，需在 loop 里埋点 | State 流动可查，trace 自动累积在 State | graph 多步骤错误更易排查 |
| 写回归测试 | mock messages list，边界模糊 | mock State 输入/输出，边界清晰 | graph 更易写测试 |
| **适合场景** | 简单单轮、工具少、快速原型 | 多步骤、需恢复、长期运行 | 按场景选择 |

## 关键结论

> Framework 不是让代码更少，而是让复杂度**显式化**。  
> bare_agent 在工具少时更透明；LangGraph 在多步骤、需追踪 State 时优势明显。  
> AI × Web3 场景（payment 流程、permission 检查）通常需要多步工具调用 + 可审计 trace，LangGraph 更适合生产。

## 文件说明

| 文件 | 说明 |
|------|------|
| `tools.py` | 4 个 Web3 纯函数工具（两个版本共享） |
| `bare_agent.py` | 裸 API 实现：手写 while loop |
| `graph_agent.py` | LangGraph 实现：State + Node + Edge |
| `compare.py` | 统一入口：同问题跑两个版本并排输出 |
| `test_tools.py` | tools 单元测试（7 个） |
| `test_bare_agent.py` | bare agent 单元测试（4 个） |
| `test_graph_agent.py` | graph agent 单元测试（4 个） |
