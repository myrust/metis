# Metis

**Metis** is a cross-platform (macOS / Linux) personal AI workbench backend built on top of the **OpenHarness** kernel, integrating multi-provider model routing, execution guardrails, progressive `SKILL.md` loading, lightweight Cron/Telegram automation, and graph memory.

[中文文档](README.zh-CN.md)

## Architecture

- **Hephaestus (`src/metis/providers/`)** — Unified `BaseModelProvider` (with optional `UsageRecorderHook` extension point), standard API Key adapters (`GeminiApiProvider`, `OpenAICompatProvider`, `AnthropicApiProvider`), `CodexCliProvider` (`codex exec --json`), and `ProviderRouter` for task routing and fallback.
- **Runtime & Guardrails (`src/metis/runtime/`)** — FastAPI server (`127.0.0.1:9119` by default) with SSE streaming (`/api/chat/stream`), human-in-the-loop approval (`/api/approval`), 3-strike anti-loop `LoopCircuitBreaker`, `WorkspaceGuard` path isolation with line-numbered reads and local diff edits, and an optional static frontend mount (`METIS_STATIC_DIR`).
- **Skills Engine (`src/metis/skills_engine/` & `skills/`)** — Progressive `SKILL.md` disclosure (name + short description in system prompt, full body loaded on demand) and session skill distillation (`SkillDistiller`). Built-in cross-platform skills:
  - `deepcode-plan-verify`: structured indexing, planning, plan review, and verification workflow.
  - `system-health`: cross-platform CPU/memory/disk inspection via `psutil`.
  - `workspace-backup`: incremental `.tar.gz` archive backup for workspace and graph directories.
- **Automation (`src/metis/automation/`)** — Config-gated `CronHeartbeatService` (`croniter` + `asyncio`) and `TelegramGateway` (`python-telegram-bot`).
- **Mnemosyne (`src/metis/memory/`)** — External-storage `LightRAG` (`NetworkXStorage` + `NanoVectorDBStorage` + deterministic lightweight CPU embedding) paired with `RAG-Anything` document pre-parsing and Hephaestus LLM extraction.

## Cross-Platform Configuration

All paths and runtime parameters are resolved via environment variables or `~/.metis/config.json`, falling back to `~/.metis/` and `shutil.which()`:

| Variable | Default | Description |
| --- | --- | --- |
| `METIS_HOME` | `~/.metis` | Base configuration and data directory |
| `METIS_WORKSPACE` | `~/.metis/workspace` | Isolated workspace root |
| `METIS_GRAPH_DIR` | `~/.metis/memory/graph` | External Mnemosyne LightRAG storage |
| `METIS_SKILLS_DIR` | `~/.metis/skills` | User-distilled skills directory |
| `METIS_STATIC_DIR` | `None` | Optional static frontend directory |
| `METIS_HOST` / `METIS_PORT` | `127.0.0.1` / `9119` | FastAPI listen address |
| `METIS_CODEX_BIN` | `shutil.which("codex")` | Override `codex` CLI binary path |
| `METIS_CRON_ENABLED` | `false` | Enable Cron heartbeat loop |
| `METIS_TELEGRAM_ENABLED` | `false` | Enable Telegram gateway |

Set your API key(s) as needed: `GEMINI_API_KEY` (or `GOOGLE_API_KEY`), `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `METIS_TELEGRAM_TOKEN`.

## Quick Start

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"

# Start FastAPI backend (127.0.0.1:9119)
.venv/bin/metis

# Run Metis unit tests & lint
.venv/bin/pytest tests/metis -v
.venv/bin/ruff check src/metis tests/metis
```

## Acknowledgements

Metis builds on and draws inspiration from:
- [HKUDS/OpenHarness](https://github.com/HKUDS/OpenHarness) (core agent harness)
- [HKUDS/LightRAG](https://github.com/HKUDS/LightRAG) & [HKUDS/RAG-Anything](https://github.com/HKUDS/RAG-Anything) (graph memory & document parsing)
- [HKUDS/nanobot](https://github.com/HKUDS/nanobot) (Cron heartbeat & Telegram gateway)
- [HKUDS/DeepCode](https://github.com/HKUDS/DeepCode) (planning & verification workflow)
- [OpenHands](https://github.com/All-Hands-AI/OpenHands) (guardrails & approval patterns)
- [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) (progressive `SKILL.md` disclosure)

## License

MIT License — see [LICENSE](LICENSE).
