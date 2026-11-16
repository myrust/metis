"""Tests for cloud-API-driven Mnemosyne (Qwen OpenAI-compatible multi-role routing)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from metis.config import MemoryRoleConfig, MnemosyneConfig
from metis.memory import mnemosyne as mnemosyne_mod
from metis.memory.mnemosyne import MnemosyneMemory


def test_no_local_cpu_embedding_in_mnemosyne() -> None:
    assert not hasattr(mnemosyne_mod, "lightweight_cpu_embed")


@pytest.mark.asyncio
async def test_mnemosyne_routes_llm_embedding_and_vision_to_openai_compat(
    monkeypatch,
    tmp_path: Path,
) -> None:
    created_clients: list[dict[str, str | None]] = []

    class _FakeAsyncOpenAI:
        def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
            created_clients.append({"api_key": api_key, "base_url": base_url})
            self.chat = MagicMock()
            self.chat.completions.create = AsyncMock(
                return_value=SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content="cloud-ok"))]
                )
            )
            self.embeddings = MagicMock()
            self.embeddings.create = AsyncMock(
                return_value=SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])])
            )

    monkeypatch.setattr(mnemosyne_mod, "AsyncOpenAI", _FakeAsyncOpenAI)

    cfg = MnemosyneConfig(
        llm=MemoryRoleConfig("https://dashscope.aliyuncs.com/compatible-mode/v1", "k-llm", "qwen-plus"),
        embedding=MemoryRoleConfig(
            "https://dashscope.aliyuncs.com/compatible-mode/v1", "k-emb", "text-embedding-v3"
        ),
        vision=MemoryRoleConfig(
            "https://dashscope.aliyuncs.com/compatible-mode/v1", "k-vis", "qwen-vl-plus"
        ),
        embedding_dim=3,
    )
    memory = MnemosyneMemory(graph_dir=tmp_path / "graph", memory_config=cfg)

    llm_res = await memory._llm_model_func("Extract entities")
    emb_res = await memory._embedding_func(["hello"])
    vis_res = await memory._vision_model_func("Describe chart", image_data="ZmFrZQ==")

    assert llm_res == "cloud-ok"
    assert emb_res == [[0.1, 0.2, 0.3]]
    assert vis_res == "cloud-ok"
    assert [c["api_key"] for c in created_clients] == ["k-llm", "k-emb", "k-vis"]
