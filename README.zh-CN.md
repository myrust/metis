# Metis

**Metis** 是基于 **OpenHarness** 内核构建的跨平台（macOS / Linux 通用）个人 AI 工作台后端，集成多模型路由、执行护栏与人工审批、`SKILL.md` 渐进式技能引擎、轻量 Cron/Telegram 自动化以及图谱记忆模块。

[English README](README.md)

## 核心模块

- **Hephaestus 模型桥接层（`src/metis/providers/`）**：统一 `BaseModelProvider`（预留可选 `UsageRecorderHook` 统计扩展接口）、标准 API Key 适配器（`GeminiApiProvider`、`OpenAICompatProvider`、`AnthropicApiProvider`）、`CodexCliProvider`（`codex exec --json`）以及支持任务路由与降级切换的 `ProviderRouter`。
- **执行护栏与事件流（`src/metis/runtime/`）**：FastAPI 服务（默认监听 `127.0.0.1:9119`），支持 SSE 流式输出（`/api/chat/stream`）、敏感操作人工审批（`/api/approval`）、连续 3 次相同错误/重复调用熔断（`LoopCircuitBreaker`）、`WorkspaceGuard` 工作区隔离（行号读取与局部 Diff 替换），并预留静态前端挂载点（`METIS_STATIC_DIR`）。
- **技能进化与运维（`src/metis/skills_engine/` & `skills/`）**：支持仅注入名称与简短描述、按需读取全文的渐进式 `SKILL.md` 加载器（`SkillRegistry`）及会话提炼器（`SkillDistiller`），内置三份跨平台技能：
  - `deepcode-plan-verify`：代码库索引、规划、审查与验证流程。
  - `system-health`：基于 `psutil` 的跨平台 CPU/内存/磁盘巡检。
  - `workspace-backup`：工作区与图谱目录增量 `.tar.gz` 归档备份。
- **定时巡检与网关（`src/metis/automation/`）**：受配置开关控制的 `CronHeartbeatService` 与 `TelegramGateway`。
- **Mnemosyne 图谱记忆（`src/metis/memory/`）**：外部独立存储目录模式的 `LightRAG`（`NetworkXStorage` + `NanoVectorDBStorage` + 轻量 CPU Embedding），前置 `RAG-Anything` 解析复杂文档并复用 Hephaestus 算力。

## 跨平台配置

所有路径与参数通过环境变量或 `~/.metis/config.json` 加载，默认回退至 `~/.metis/` 与 `shutil.which()`：

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `METIS_HOME` | `~/.metis` | 基础配置与数据目录 |
| `METIS_WORKSPACE` | `~/.metis/workspace` | 隔离工作区根目录 |
| `METIS_GRAPH_DIR` | `~/.metis/memory/graph` | Mnemosyne 图谱外部存储目录 |
| `METIS_SKILLS_DIR` | `~/.metis/skills` | 用户沉淀技能目录 |
| `METIS_STATIC_DIR` | `None` | 可选静态前端目录 |
| `METIS_HOST` / `METIS_PORT` | `127.0.0.1` / `9119` | FastAPI 监听地址与端口 |
| `METIS_CODEX_BIN` | `shutil.which("codex")` | 指定 `codex` 可执行文件路径 |
| `METIS_CRON_ENABLED` | `false` | 是否启用 Cron 心跳 |
| `METIS_TELEGRAM_ENABLED` | `false` | 是否启用 Telegram 网关 |

按需配置对应环境变量：`GEMINI_API_KEY`（或 `GOOGLE_API_KEY`）、`OPENAI_API_KEY`、`ANTHROPIC_API_KEY`、`METIS_TELEGRAM_TOKEN`。

## 快速开始

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"

# 启动后端服务（默认 127.0.0.1:9119）
.venv/bin/metis

# 运行单元测试与代码检查
.venv/bin/pytest tests/metis -v
.venv/bin/ruff check src/metis tests/metis
```

## 致谢

本项目基于并参考以下开源组件：
- [HKUDS/OpenHarness](https://github.com/HKUDS/OpenHarness)
- [HKUDS/LightRAG](https://github.com/HKUDS/LightRAG) & [HKUDS/RAG-Anything](https://github.com/HKUDS/RAG-Anything)
- [HKUDS/nanobot](https://github.com/HKUDS/nanobot)
- [HKUDS/DeepCode](https://github.com/HKUDS/DeepCode)
- [OpenHands](https://github.com/All-Hands-AI/OpenHands)
- [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)

## 开源协议

MIT License — 详见 [LICENSE](LICENSE)。
