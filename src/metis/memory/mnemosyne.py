"""Mnemosyne: Graph memory module combining LightRAG + RAG-Anything + Hephaestus LLM."""

from __future__ import annotations

import hashlib
import importlib
import math
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from metis.providers.base import BaseModelProvider, ProviderRequest
from metis.providers.router import ProviderRouter


def lightweight_cpu_embed(texts: Sequence[str], dim: int = 128) -> list[list[float]]:
    """Deterministic lightweight CPU embedding using signed n-gram hashing.

    Provides zero-GPU, zero-network local vectorization for NanoVectorDBStorage
    when an external embedding model is not configured.
    """
    vectors: list[list[float]] = []
    for text in texts:
        vec = [0.0] * dim
        tokens = text.lower().split() or [text.lower()]
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            idx = int.from_bytes(digest[:4], "little") % dim
            sign = 1.0 if (digest[4] & 1) == 0 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        vectors.append([v / norm for v in vec])
    return vectors


class MnemosyneMemory:
    """External-storage LightRAG + RAG-Anything memory backed by Hephaestus."""

    def __init__(
        self,
        graph_dir: Path,
        llm_backend: BaseModelProvider | ProviderRouter,
        embed_dim: int = 128,
        embed_fn: Callable[[Sequence[str]], list[list[float]]] | None = None,
    ) -> None:
        self.graph_dir = Path(graph_dir).expanduser().resolve()
        self.graph_dir.mkdir(parents=True, exist_ok=True)
        self.llm_backend = llm_backend
        self.embed_dim = embed_dim
        self._embed_fn = embed_fn or (lambda texts: lightweight_cpu_embed(texts, dim=embed_dim))
        self._rag: Any = None
        self._rag_anything: Any = None

    async def _llm_model_func(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **_kwargs: Any,
    ) -> str:
        req = ProviderRequest(prompt=prompt, system_prompt=system_prompt)
        return await self.llm_backend.generate(req)

    def _build_lightrag(self) -> Any:
        lightrag_mod = importlib.import_module("lightrag")
        utils_mod = importlib.import_module("lightrag.utils")
        LightRAG = lightrag_mod.LightRAG
        EmbeddingFunc = utils_mod.EmbeddingFunc

        async def _async_embed(texts: list[str]) -> Any:
            return self._embed_fn(texts)

        return LightRAG(
            working_dir=str(self.graph_dir),
            llm_model_func=self._llm_model_func,
            embedding_func=EmbeddingFunc(
                embedding_dim=self.embed_dim,
                max_token_size=8192,
                func=_async_embed,
            ),
            graph_storage="NetworkXStorage",
            vector_storage="NanoVectorDBStorage",
        )

    def ensure_initialized(self) -> Any:
        """Lazily construct the LightRAG (and optional RAG-Anything) instances."""
        if self._rag is None:
            self._rag = self._build_lightrag()
        if self._rag_anything is None:
            try:
                raganything_mod = importlib.import_module("raganything")
                RAGAnything = getattr(raganything_mod, "RAGAnything", None)
                if RAGAnything is not None:
                    self._rag_anything = RAGAnything(lightrag=self._rag)
            except ImportError:
                self._rag_anything = None
        return self._rag

    async def ingest_text(self, text: str) -> None:
        """Insert plain text into the external LightRAG graph/vector store."""
        rag = self.ensure_initialized()
        if hasattr(rag, "ainsert"):
            await rag.ainsert(text)
        else:
            rag.insert(text)

    async def ingest_document(self, file_path: Path) -> None:
        """Parse complex documents (PDF/charts) via RAG-Anything, or fallback to text."""
        target = Path(file_path).expanduser().resolve()
        self.ensure_initialized()
        if self._rag_anything is not None and hasattr(self._rag_anything, "process_document_complete"):
            await self._rag_anything.process_document_complete(file_path=str(target))
            return
        await self.ingest_text(target.read_text(encoding="utf-8"))

    async def query(self, question: str, mode: str = "hybrid") -> str:
        """Query Mnemosyne graph memory using LightRAG."""
        rag = self.ensure_initialized()
        lightrag_mod = importlib.import_module("lightrag")
        QueryParam = lightrag_mod.QueryParam
        param = QueryParam(mode=mode)
        if hasattr(rag, "aquery"):
            return str(await rag.aquery(question, param=param))
        return str(rag.query(question, param=param))
