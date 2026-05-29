"""
只读 MCP Server — MCP 章节最小实践

暴露两个工具：
- search_docs(query): 在白名单目录内搜索文档内容
- get_file(path): 读取白名单目录内的文件

安全边界：
- 只能访问白名单目录，拒绝路径穿越
- 返回结果带来源路径
- 每次工具调用写日志
- 错误明确返回，不静默失败
"""

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# ── 配置 ──────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()

WHITELIST_DIRS = [
    PROJECT_ROOT / "daily",
    PROJECT_ROOT / "experiments",
    PROJECT_ROOT / "hackathon",
    PROJECT_ROOT / "handbook-feedback",
]

LOG_FILE = Path(__file__).parent / "tool_calls.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ── 权限检查 ───────────────────────────────────────────────────────────────────

def is_allowed(path: Path) -> bool:
    resolved = path.resolve()
    return any(
        str(resolved).startswith(str(allowed))
        for allowed in WHITELIST_DIRS
    )

# ── Server 定义 ────────────────────────────────────────────────────────────────

server = Server("readonly-docs-server")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_docs",
            description="在项目文档中搜索关键词，只能访问白名单目录（daily/、experiments/、hackathon/、handbook-feedback/）",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_file",
            description="读取白名单目录内的文件内容，返回文件路径和内容",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "相对于项目根目录的文件路径，如 daily/2026-05-29.md",
                    },
                },
                "required": ["path"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    logger.info("tool_call | tool=%s | args=%s", name, arguments)

    if name == "search_docs":
        return await _search_docs(arguments.get("query", ""))
    elif name == "get_file":
        return await _get_file(arguments.get("path", ""))
    else:
        logger.warning("unknown_tool | tool=%s", name)
        return [TextContent(type="text", text=f"错误：未知工具 {name}")]


# ── 工具实现 ───────────────────────────────────────────────────────────────────

async def _search_docs(query: str) -> list[TextContent]:
    if not query.strip():
        return [TextContent(type="text", text="错误：query 不能为空")]

    results = []
    for allowed_dir in WHITELIST_DIRS:
        if not allowed_dir.exists():
            continue
        for file_path in allowed_dir.rglob("*.md"):
            try:
                text = file_path.read_text(encoding="utf-8")
                lines = [
                    (i + 1, line)
                    for i, line in enumerate(text.splitlines())
                    if query.lower() in line.lower()
                ]
                if lines:
                    rel = file_path.relative_to(PROJECT_ROOT)
                    for lineno, line in lines[:3]:  # 每个文件最多 3 条
                        results.append(f"[{rel}:{lineno}] {line.strip()}")
            except Exception as e:
                logger.error("search_error | file=%s | error=%s", file_path, e)

    if not results:
        return [TextContent(type="text", text=f"未找到包含 '{query}' 的内容")]

    output = f"搜索 '{query}'，共找到 {len(results)} 条：\n\n" + "\n".join(results)
    logger.info("search_result | query=%s | hits=%d", query, len(results))
    return [TextContent(type="text", text=output)]


async def _get_file(relative_path: str) -> list[TextContent]:
    if not relative_path.strip():
        return [TextContent(type="text", text="错误：path 不能为空")]

    target = (PROJECT_ROOT / relative_path).resolve()

    if not is_allowed(target):
        logger.warning("access_denied | path=%s | resolved=%s", relative_path, target)
        return [TextContent(
            type="text",
            text=f"错误：路径 '{relative_path}' 不在白名单目录内，拒绝访问"
        )]

    if not target.exists():
        return [TextContent(type="text", text=f"错误：文件不存在 — {relative_path}")]

    if not target.is_file():
        return [TextContent(type="text", text=f"错误：路径不是文件 — {relative_path}")]

    try:
        content = target.read_text(encoding="utf-8")
        rel = target.relative_to(PROJECT_ROOT)
        logger.info("file_read | path=%s | size=%d", rel, len(content))
        return [TextContent(
            type="text",
            text=f"来源：{rel}\n\n{content}"
        )]
    except Exception as e:
        logger.error("read_error | path=%s | error=%s", relative_path, e)
        return [TextContent(type="text", text=f"错误：读取文件失败 — {e}")]


# ── 入口 ──────────────────────────────────────────────────────────────────────

async def main():
    logger.info("MCP readonly-docs-server 启动 | root=%s", PROJECT_ROOT)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
