# Zero

用 ~5000 行 Python 还原 CC 的核心 Agent Runtime。

## 这是什么

CC 是 Anthropic 官方的 AI 编程 CLI，它的本质是一个 **tool-use agent loop**：模型读代码、改文件、跑命令、自主决策，循环往复直到任务完成。

这个项目从 TypeScript 源码（1884 个文件、38 万行）中，提取并翻译了核心运行时逻辑，用纯 Python 实现了一个功能对齐的 Agent CLI。

**不是封装 API 的 wrapper，是完整还原了 agent 内核。**

## 还原了什么

| 能力 | 状态 | 说明 |
|------|------|------|
| Agent Loop（状态机） | ✅ | 多轮 tool-use 循环，流式响应，错误恢复，自动重试 |
| 12 个内置工具 | ✅ | Bash、Read、Edit、Write、Glob、Grep、Agent、WebFetch、AskUser、Task 系列 |
| System Prompt 体系 | ✅ | 11 段动态拼装，含完整 Memory 行为指导 |
| CLAUDE.md 加载 | ✅ | 目录层级遍历 + `@include` 递归展开 |
| 自动上下文压缩 | ✅ | Token 预算监控，超限自动 compact，长对话不崩 |
| Memory 系统 | ✅ | 四类记忆分类、MEMORY.md 索引、后台异步提取 |
| MCP 协议支持 | ✅ | stdio 传输、动态工具注册、多 server 并行 |
| 工具编排引擎 | ✅ | 并发/串行分批、流式执行器、unknown tool 容错 |
| Hooks 系统 | ✅ | PreToolUse/PostToolUse 拦截，shell 命令执行 |
| Skills 系统 | ✅ | frontmatter 定义、slash 命令触发、prompt 注入 |
| Session 持久化 | ✅ | 会话保存/恢复、历史记录 |
| REPL + Print 模式 | ✅ | 交互式循环 + 单次管道模式 |

## 架构

```
cc/                          5138 行，66 个文件
├── core/          343 行    Agent 内核：query_loop 状态机、事件流、状态转换
├── api/           314 行    Anthropic API：流式调用、客户端管理、token 统计
├── models/        545 行    数据模型：消息类型、content blocks、API 规范化
├── prompts/       533 行    System Prompt：11 段文本 + 动态拼装 + Memory 指导
├── tools/        1432 行    12 个工具实现 + 编排引擎 + 流式执行器
├── compact/       159 行    上下文压缩：token 预算监控、摘要生成
├── memory/        312 行    记忆系统：加载/保存/提取/索引
├── mcp/           259 行    MCP 协议：stdio 客户端、工具桥接
├── hooks/         157 行    Hooks：配置加载、PreToolUse/PostToolUse
├── skills/        100 行    Skills：定义加载、slash 命令注册
├── session/       280 行    会话管理：持久化、历史记录
├── commands/       92 行    Slash 命令：/clear /compact /model /help /cost
├── ui/             96 行    终端渲染：Rich 流式输出
└── main.py        473 行    入口：REPL 循环、模块组装

tests/                       2843 行，43 个文件，218 个测试用例
```

### 核心数据流

```
用户输入
  → main.py 追加到 messages（transcript）
  → query_loop 发送到 Claude API
  → 流式接收：TextDelta / ToolUseBlock / TurnComplete
  → 如果有 tool_use → 编排引擎并发执行 → tool_result 塞回 transcript → 再调 API
  → 循环直到 end_turn
  → 渲染输出，等待下一轮输入
```

一次用户输入可以触发多轮模型调用和多次工具执行——这就是 agent，不是 chatbot。

## 快速开始

### 环境要求

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

### 安装

```bash
cd cc-python-claude
uv sync
```

### 配置 API Key

```bash
# 环境变量
export ANTHROPIC_API_KEY=sk-ant-...

# 或项目 .env 文件
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
```

### 启动

```bash
# REPL 交互模式
uv run python -m cc

# 单次问答（管道模式）
echo "用 Python 写一个快排" | uv run python -m cc -p

# 指定模型
uv run python -m cc --model claude-haiku-4-5-20251001

# 恢复会话
uv run python -m cc -c <session-id>
```

### 测试

```bash
uv run pytest tests/unit/ -v
```

## 交流

对 CC 源码还原或 Agent Runtime 感兴趣可以扫二维码，进 CC 讨论群：

<img src="assets/wechat.jpg" width="300">

