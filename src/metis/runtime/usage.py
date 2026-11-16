"""Token usage & cost estimation tracker implementing UsageRecorderHook."""

from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from metis.providers.base import ProviderRequest

# Approximate USD per 1M tokens: (input_per_1m, output_per_1m)
_DEFAULT_PRICING_PER_1M: dict[str, tuple[float, float]] = {
    "gemini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "claude": (3.00, 15.00),
    "qwen-plus": (0.40, 1.20),
    "qwen-turbo": (0.10, 0.30),
    "qwen-vl": (0.80, 2.40),
}


def _estimate_tokens(text: str | None) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


def _pricing_for(model: str, provider: str) -> tuple[float, float]:
    key = (model or provider).lower()
    for prefix, rates in _DEFAULT_PRICING_PER_1M.items():
        if prefix in key:
            return rates
    return (0.50, 1.50)


class UsageTracker:
    """Appends model invocation records to JSONL and aggregates cost/token summaries."""

    def __init__(self, log_path: Path) -> None:
        self.log_path = Path(log_path).expanduser().resolve()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def on_invocation_start(self, provider_name: str, request: ProviderRequest) -> None:
        return None

    def on_invocation_end(
        self,
        provider_name: str,
        request: ProviderRequest,
        usage: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        model = request.model or provider_name
        in_tok = int((usage or {}).get("input_tokens") or _estimate_tokens(request.prompt))
        out_tok = int((usage or {}).get("output_tokens") or 0)
        in_rate, out_rate = _pricing_for(model, provider_name)
        cost = (in_tok * in_rate + out_tok * out_rate) / 1_000_000.0
        record = {
            "ts": time.time(),
            "provider": provider_name,
            "model": model,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "cost_usd": round(cost, 6),
            "ok": error is None,
        }
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def record_completion(
        self,
        provider_name: str,
        model: str | None,
        prompt_text: str,
        output_text: str,
        ok: bool = True,
    ) -> None:
        """Record a streamed completion directly from the agent loop."""
        m = model or provider_name
        in_tok = _estimate_tokens(prompt_text)
        out_tok = _estimate_tokens(output_text)
        in_rate, out_rate = _pricing_for(m, provider_name)
        cost = (in_tok * in_rate + out_tok * out_rate) / 1_000_000.0
        record = {
            "ts": time.time(),
            "provider": provider_name,
            "model": m,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "cost_usd": round(cost, 6),
            "ok": ok,
        }
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def summary(self, days: int = 7) -> dict[str, Any]:
        cutoff = time.time() - (days * 86400)
        total_calls = 0
        total_in = 0
        total_out = 0
        total_cost = 0.0
        by_model: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
        )

        if self.log_path.is_file():
            for line in self.log_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if float(rec.get("ts", 0)) < cutoff:
                    continue
                total_calls += 1
                in_t = int(rec.get("input_tokens", 0))
                out_t = int(rec.get("output_tokens", 0))
                cost = float(rec.get("cost_usd", 0.0))
                total_in += in_t
                total_out += out_t
                total_cost += cost
                m = str(rec.get("model", "unknown"))
                by_model[m]["calls"] += 1
                by_model[m]["input_tokens"] += in_t
                by_model[m]["output_tokens"] += out_t
                by_model[m]["cost_usd"] = round(by_model[m]["cost_usd"] + cost, 6)

        return {
            "days": days,
            "total_calls": total_calls,
            "total_input_tokens": total_in,
            "total_output_tokens": total_out,
            "total_cost_usd": round(total_cost, 6),
            "by_model": dict(by_model),
        }
