"""Independent model registry (~/.metis/models.json) decoupling providers and role routing."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import httpx

from metis.config import MemoryRoleConfig, MnemosyneConfig
from metis.providers.api_adapter import (
    AnthropicApiProvider,
    GeminiApiProvider,
    OpenAICompatProvider,
)
from metis.providers.base import BaseModelProvider
from metis.providers.codex_cli import CodexCliProvider
from metis.providers.router import ProviderRouter


@dataclass
class ProviderCredentialEntry:
    """Single provider entry in ~/.metis/models.json."""

    id: str
    type: str  # "gemini" | "openai_compat" | "anthropic" | "codex" (plugin slot)
    base_url: str | None = None
    api_key: str | None = None
    default_model: str | None = None
    enabled: bool = True
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class RoleRouteEntry:
    """Maps a business role (chat, code, memory_llm, etc.) to a provider + model."""

    provider_id: str
    model: str | None = None
    fallback_providers: list[str] = field(default_factory=list)


class ModelsRegistry:
    """Loads and persists ~/.metis/models.json."""

    def __init__(self, models_file: Path) -> None:
        self.models_file = Path(models_file).expanduser().resolve()
        self.providers: dict[str, ProviderCredentialEntry] = {}
        self.roles: dict[str, RoleRouteEntry] = {}
        self.load()

    def _seed_defaults(self) -> None:
        qwen_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.providers = {
            "gemini": ProviderCredentialEntry(
                id="gemini",
                type="gemini",
                default_model="gemini-2.5-flash",
            ),
            "openai": ProviderCredentialEntry(
                id="openai",
                type="openai_compat",
                default_model="gpt-4o-mini",
            ),
            "anthropic": ProviderCredentialEntry(
                id="anthropic",
                type="anthropic",
                default_model="claude-sonnet-4-5",
            ),
            "qwen": ProviderCredentialEntry(
                id="qwen",
                type="openai_compat",
                base_url=qwen_url,
                default_model="qwen-plus",
            ),
            "codex": ProviderCredentialEntry(
                id="codex",
                type="codex",
                default_model=None,
                enabled=True,
                extra={"plugin_slot": "codex-cli"},
            ),
        }
        self.roles = {
            "chat": RoleRouteEntry(
                provider_id="gemini",
                fallback_providers=["openai", "anthropic", "codex"],
            ),
            "code": RoleRouteEntry(
                provider_id="codex",
                fallback_providers=["anthropic", "gemini", "openai"],
            ),
            "memory_llm": RoleRouteEntry(provider_id="qwen", model="qwen-plus"),
            "memory_embedding": RoleRouteEntry(provider_id="qwen", model="text-embedding-v3"),
            "memory_vision": RoleRouteEntry(provider_id="qwen", model="qwen-vl-plus"),
        }

    def load(self) -> None:
        if not self.models_file.is_file():
            self._seed_defaults()
            return
        try:
            raw = json.loads(self.models_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._seed_defaults()
            return

        if not isinstance(raw, dict):
            self._seed_defaults()
            return

        self.providers = {}
        for item in raw.get("providers", []):
            if isinstance(item, dict) and item.get("id"):
                entry = ProviderCredentialEntry(
                    id=str(item["id"]),
                    type=str(item.get("type", "openai_compat")),
                    base_url=item.get("base_url"),
                    api_key=item.get("api_key"),
                    default_model=item.get("default_model"),
                    enabled=bool(item.get("enabled", True)),
                    extra=dict(item.get("extra", {})),
                )
                self.providers[entry.id] = entry

        self.roles = {}
        roles_raw = raw.get("roles", {})
        if isinstance(roles_raw, dict):
            for role_name, val in roles_raw.items():
                if isinstance(val, dict) and val.get("provider_id"):
                    self.roles[str(role_name)] = RoleRouteEntry(
                        provider_id=str(val["provider_id"]),
                        model=val.get("model"),
                        fallback_providers=list(val.get("fallback_providers", [])),
                    )

        if not self.providers:
            self._seed_defaults()

    def save(self) -> None:
        self.models_file.parent.mkdir(parents=True, exist_ok=True)
        self.models_file.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "providers": [asdict(p) for p in self.providers.values()],
            "roles": {name: asdict(r) for name, r in self.roles.items()},
        }

    def update_from_dict(self, payload: dict[str, Any]) -> None:
        if "providers" in payload and isinstance(payload["providers"], list):
            new_providers: dict[str, ProviderCredentialEntry] = {}
            for item in payload["providers"]:
                if isinstance(item, dict) and item.get("id"):
                    entry = ProviderCredentialEntry(
                        id=str(item["id"]),
                        type=str(item.get("type", "openai_compat")),
                        base_url=item.get("base_url"),
                        api_key=item.get("api_key"),
                        default_model=item.get("default_model"),
                        enabled=bool(item.get("enabled", True)),
                        extra=dict(item.get("extra", {})),
                    )
                    new_providers[entry.id] = entry
            self.providers = new_providers
        if "roles" in payload and isinstance(payload["roles"], dict):
            new_roles: dict[str, RoleRouteEntry] = {}
            for role_name, val in payload["roles"].items():
                if isinstance(val, dict) and val.get("provider_id"):
                    new_roles[str(role_name)] = RoleRouteEntry(
                        provider_id=str(val["provider_id"]),
                        model=val.get("model"),
                        fallback_providers=list(val.get("fallback_providers", [])),
                    )
            self.roles = new_roles
        self.save()

    def resolve_mnemosyne_config(self, base_cfg: MnemosyneConfig) -> MnemosyneConfig:
        """Overlay memory_* roles from models.json onto MnemosyneConfig when configured."""

        def _merge(role_key: str, fallback: MemoryRoleConfig) -> MemoryRoleConfig:
            route = self.roles.get(role_key)
            if route is None:
                return fallback
            prov = self.providers.get(route.provider_id)
            if prov is None or not prov.enabled:
                return fallback
            return MemoryRoleConfig(
                base_url=prov.base_url or fallback.base_url,
                api_key=prov.api_key or fallback.api_key,
                model=route.model or prov.default_model or fallback.model,
            )

        return MnemosyneConfig(
            llm=_merge("memory_llm", base_cfg.llm),
            embedding=_merge("memory_embedding", base_cfg.embedding),
            vision=_merge("memory_vision", base_cfg.vision),
            embedding_dim=base_cfg.embedding_dim,
        )

    def build_provider_router(
        self,
        codex_bin: str | None = None,
        workspace_dir: Path | None = None,
    ) -> ProviderRouter:
        """Build a live ProviderRouter from providers + roles in models.json."""
        built: list[BaseModelProvider] = []
        for entry in self.providers.values():
            if not entry.enabled:
                continue
            provider: BaseModelProvider | None = None
            if entry.type == "gemini":
                provider = GeminiApiProvider(
                    api_key=entry.api_key,
                    base_url=entry.base_url,
                    default_model=entry.default_model or "gemini-2.5-flash",
                )
            elif entry.type == "openai_compat":
                provider = OpenAICompatProvider(
                    api_key=entry.api_key,
                    base_url=entry.base_url,
                    default_model=entry.default_model or "gpt-4o-mini",
                )
            elif entry.type == "anthropic":
                provider = AnthropicApiProvider(
                    api_key=entry.api_key,
                    base_url=entry.base_url,
                    default_model=entry.default_model or "claude-sonnet-4-5",
                )
            elif entry.type == "codex":
                provider = CodexCliProvider(
                    binary_path=codex_bin,
                    workspace_dir=workspace_dir,
                )
            if provider is not None:
                provider.name = entry.id
                built.append(provider)

        task_routes: dict[str, list[str]] = {}
        for role_name, route in self.roles.items():
            task_routes[role_name] = [route.provider_id, *route.fallback_providers]

        return ProviderRouter(providers=built, task_routes=task_routes)


async def discover_gemini_models(
    api_key: str | None = None,
    base_url: str | None = None,
) -> list[str]:
    """Query Google AI Studio /v1beta/models to list generateContent-capable models."""
    key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        return []
    root = (base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
    url = f"{root}/models"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, params={"key": key})
        resp.raise_for_status()
        payload = resp.json()

    models: list[str] = []
    for item in payload.get("models", []):
        methods = item.get("supportedGenerationMethods") or []
        if "generateContent" not in methods:
            continue
        raw_name = str(item.get("name", ""))
        model_id = raw_name.removeprefix("models/")
        if model_id:
            models.append(model_id)
    return models
