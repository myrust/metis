"""Mnemosyne: Cloud-API-driven LightRAG + RAG-Anything with local file persistence.

Uses NetworkXStorage + NanoVectorDBStorage on local disk with zero local
embedding or vision models; all LLM, embedding, and vision calls route through
configured OpenAI-compatible endpoints (defaulting to Qwen DashScope compat).
"""

from __future__ import annotations

import importlib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from metis.config import MemoryRoleConfig, MnemosyneConfig


def _default_mnemosyne_config() -> MnemosyneConfig:
    base = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    return MnemosyneConfig(
        llm=MemoryRoleConfig(base_url=base, api_key=None, model="qwen-plus"),
        embedding=MemoryRoleConfig(base_url=base, api_key=None, model="text-embedding-v3"),
        vision=MemoryRoleConfig(base_url=base, api_key=None, model="qwen-vl-plus"),
        embedding_dim=1024,
    )


class MnemosyneMemory:
    """External-storage LightRAG + RAG-Anything backed by OpenAI-compatible cloud APIs."""

    def __init__(
        self,
        graph_dir: Path,
        memory_config: MnemosyneConfig | None = None,
    ) -> None:
        self.graph_dir = Path(graph_dir).expanduser().resolve()
        self.graph_dir.mkdir(parents=True, exist_ok=True)
        self.memory_config = memory_config or _default_mnemosyne_config()
        self._rag: Any = None
        self._rag_anything: Any = None

    @staticmethod
    def _client_for(role: MemoryRoleConfig, role_name: str) -> AsyncOpenAI:
        if not role.api_key:
            raise RuntimeError(
                f"Mnemosyne '{role_name}' API key is not configured "
                f"(model={role.model}, base_url={role.base_url})."
            )
        return AsyncOpenAI(api_key=role.api_key, base_url=role.base_url)

    async def _llm_model_func(
        self,
        prompt: str,
        system_prompt: str | None = None,
        history_messages: list[dict[str, Any]] | None = None,
        **_kwargs: Any,
    ) -> str:
        role = self.memory_config.llm
        client = self._client_for(role, "llm")
        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history_messages:
            messages.extend(history_messages)
        messages.append({"role": "user", "content": prompt})

        resp = await client.chat.completions.create(model=role.model, messages=messages)
        return str(resp.choices[0].message.content or "")

    async def _embedding_func(self, texts: Sequence[str]) -> list[list[float]]:
        role = self.memory_config.embedding
        client = self._client_for(role, "embedding")
        resp = await client.embeddings.create(model=role.model, input=list(texts))
        return [list(item.embedding) for item in resp.data]

    async def _vision_model_func(
        self,
        prompt: str,
        system_prompt: str | None = None,
        history_messages: list[dict[str, Any]] | None = None,
        image_data: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        **_kwargs: Any,
    ) -> str:
        role = self.memory_config.vision
        client = self._client_for(role, "vision")
        payload_messages: list[dict[str, Any]] = []
        if messages:
            payload_messages = list(messages)
        else:
            if system_prompt:
                payload_messages.append({"role": "system", "content": system_prompt})
            if history_messages:
                payload_messages.extend(history_messages)
            if image_data:
                url = (
                    image_data
                    if image_data.startswith(("http://", "https://", "data:"))
                    else f"data:image/jpeg;base64,{image_data}"
                )
                payload_messages.append(
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": url}},
                        ],
                    }
                )
            else:
                payload_messages.append({"role": "user", "content": prompt})

        resp = await client.chat.completions.create(model=role.model, messages=payload_messages)
        return str(resp.choices[0].message.content or "")

    def _build_lightrag(self) -> Any:
        lightrag_mod = importlib.import_module("lightrag")
        utils_mod = importlib.import_module("lightrag.utils")
        LightRAG = lightrag_mod.LightRAG
        EmbeddingFunc = utils_mod.EmbeddingFunc

        return LightRAG(
            working_dir=str(self.graph_dir),
            llm_model_func=self._llm_model_func,
            embedding_func=EmbeddingFunc(
                embedding_dim=self.memory_config.embedding_dim,
                max_token_size=8192,
                func=self._embedding_func,
            ),
            graph_storage="NetworkXStorage",
            vector_storage="NanoVectorDBStorage",
        )

    def ensure_initialized(self) -> Any:
        """Lazily construct LightRAG and RAG-Anything instances."""
        if self._rag is None:
            self._rag = self._build_lightrag()
        if self._rag_anything is None:
            try:
                raganything_mod = importlib.import_module("raganything")
                RAGAnything = getattr(raganything_mod, "RAGAnything", None)
                if RAGAnything is not None:
                    self._rag_anything = RAGAnything(
                        lightrag=self._rag,
                        vision_model_func=self._vision_model_func,
                    )
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
        """Parse complex documents (PDF/charts) via RAG-Anything cloud vision, or fallback to text."""
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
