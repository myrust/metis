"""Tests for Mnemosyne graph memory and lightweight CPU embeddings."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from metis.memory.mnemosyne import MnemosyneMemory, lightweight_cpu_embed
from metis.providers.base import BaseModelProvider, ProviderRequest, ProviderStreamEvent


class _StubProvider(BaseModelProvider):
    name = "stub"

    def is_available(self) -> bool:
        return True

    async def stream(self, request: ProviderRequest) -> AsyncIterator[ProviderStreamEvent]:
        yield ProviderStreamEvent(kind="text_delta", content=f"summary:{request.prompt[:20]}")
        yield ProviderStreamEvent(kind="done", content="")


def test_lightweight_cpu_embed_deterministic_and_unit_norm() -> None:
    vecs = lightweight_cpu_embed(["Metis knowledge graph", "Metis knowledge graph"], dim=64)
    assert len(vecs) == 2
    assert len(vecs[0]) == 64
    assert vecs[0] == vecs[1]
    norm_sq = sum(x * x for x in vecs[0])
    assert abs(norm_sq - 1.0) < 1e-6


@pytest.mark.asyncio
async def test_mnemosyne_uses_external_dir_and_hephaestus_llm(tmp_path: Path) -> None:
    graph_dir = tmp_path / "external_graph"
    memory = MnemosyneMemory(graph_dir=graph_dir, llm_backend=_StubProvider())
    assert graph_dir.is_dir()

    llm_out = await memory._llm_model_func("Extract entities from Metis.")
    assert llm_out.startswith("summary:")
