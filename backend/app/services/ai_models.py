"""Provider abstraction for AI Auto-Takeoff (Sprint AI-01).

Three protocols cover every external model call we make in the pipeline:

* ``VisionModel`` -- image-in tasks (sheet classification fallback, lineless
  schedule extraction, ambiguous-symbol regions).
* ``EmbeddingModel`` -- text vectorization for the condition resolver (AI-04).
* ``LLMModel`` -- structured-text tasks (condition name summarization,
  assembly item enrichment).

Concrete implementations live in this module so tests can patch the SDK calls
at the boundary. Factory functions (``get_*_model``) read the configured
provider/model id from ``app.config`` at call time -- swapping providers is a
config change, never a code change.

Cost attribution: every external call is wrapped in ``with_cost_tracking``,
which reads the active ``ai_run_id`` from a ``ContextVar`` and increments the
run row. Tasks set the contextvar at the top of each stage; nothing in the
business code passes ``ai_run_id`` to model calls explicitly. When no run is
active (e.g. unit tests, ad-hoc scripts) the cost wrapper is a no-op.
"""

from __future__ import annotations

import base64
import contextvars
import json
import logging
import re
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator, Protocol

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.ai_run import AiRun

logger = logging.getLogger(__name__)


def _round_up_cents(value: float) -> int:
    """Round to integer cents, biased up so we never under-bill ourselves.

    Cost telemetry feeds the per-org daily abuse cutoff and per-run reporting;
    biasing up by <1 cent per call is safer than the inverse.
    """
    if value <= 0:
        return 0
    if value >= 1:
        return int(value + 0.999)
    return 1  # any non-zero usage costs at least 1 cent at our reporting precision


# ─── Cost attribution context ───────────────────────────────────────────────

_active_ai_run_id: contextvars.ContextVar[uuid.UUID | None] = contextvars.ContextVar(
    "active_ai_run_id", default=None
)
#: Sync session factory injected by the Celery worker (``ai_pipeline``) so the
#: cost wrapper can write to the DB without taking a session as an argument.
#: Async API code does not write costs (only the worker calls models).
_sync_session_factory: contextvars.ContextVar[Any] = contextvars.ContextVar(
    "ai_sync_session_factory", default=None
)


def set_active_ai_run(ai_run_id: uuid.UUID | None) -> contextvars.Token:
    """Bind the active run id for cost attribution. Returns a token to reset."""
    return _active_ai_run_id.set(ai_run_id)


def reset_active_ai_run(token: contextvars.Token) -> None:
    _active_ai_run_id.reset(token)


def get_active_ai_run() -> uuid.UUID | None:
    return _active_ai_run_id.get()


def set_sync_session_factory(factory: Any) -> contextvars.Token:
    """Inject the Celery worker's sync ``sessionmaker`` for cost writes."""
    return _sync_session_factory.set(factory)


def reset_sync_session_factory(token: contextvars.Token) -> None:
    _sync_session_factory.reset(token)


# ─── Cost record ─────────────────────────────────────────────────────────────


@dataclass
class CostRecord:
    """Result of a single external model call."""

    cost_cents: int = 0
    tokens_used: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@contextmanager
def with_cost_tracking(call_label: str) -> Iterator[CostRecord]:
    """Wrap a model call to attribute its cost to the active ``ai_runs`` row.

    Usage::

        with with_cost_tracking("vision.classify_image") as cost:
            response = sdk.call(...)
            cost.cost_cents = compute_cost_cents(response)
            cost.tokens_used = response.usage.total_tokens

    On exit, ``cost.cost_cents`` and ``cost.tokens_used`` are added to the
    active run. When no run is active (no ContextVar set, or no session
    factory), the wrapper logs the call and returns without touching the DB --
    this keeps tests, scripts, and dev probes free of side effects.
    """
    record = CostRecord()
    try:
        yield record
    finally:
        ai_run_id = _active_ai_run_id.get()
        factory = _sync_session_factory.get()
        if ai_run_id is None or factory is None:
            logger.debug(
                "Cost recorded outside a run: label=%s cost=%s tokens=%s",
                call_label,
                record.cost_cents,
                record.tokens_used,
            )
            return
        if record.cost_cents == 0 and record.tokens_used == 0:
            return
        try:
            with factory() as session:  # type: Session
                session.execute(
                    update(AiRun)
                    .where(AiRun.id == ai_run_id)
                    .values(
                        cost_cents=AiRun.cost_cents + record.cost_cents,
                        tokens_used=AiRun.tokens_used + record.tokens_used,
                    )
                )
                session.commit()
        except Exception:
            # Cost telemetry must never block the pipeline.
            logger.exception(
                "Failed to write cost for run %s (label=%s)", ai_run_id, call_label
            )


# ─── Protocols ───────────────────────────────────────────────────────────────


class VisionModel(Protocol):
    """Image-in tasks. Implementations call vendor SDKs internally."""

    model_id: str

    def classify_image(
        self, image_bytes: bytes, *, schema: dict[str, Any]
    ) -> dict[str, Any]:
        """Return a structured classification per the JSON schema."""
        ...

    def extract_structured(
        self,
        image_bytes: bytes,
        *,
        prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Extract structured data (e.g. a schedule table) from an image."""
        ...

    def analyze_region(
        self,
        image_bytes: bytes,
        *,
        bbox_pdf: dict[str, float],
        prompt: str,
    ) -> str:
        """Free-form analysis of a sub-region (used for ambiguous symbols)."""
        ...


class EmbeddingModel(Protocol):
    """Text vectorization for the condition resolver."""

    model_id: str
    dimensions: int

    def embed_text(self, text: str) -> list[float]:
        ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        ...


class LLMModel(Protocol):
    """Structured-text tasks (name summarization, assembly enrichment)."""

    model_id: str

    def summarize(self, text: str, *, max_chars: int) -> str:
        ...

    def structured_output(
        self, prompt: str, *, schema: dict[str, Any]
    ) -> dict[str, Any]:
        ...


# ─── Concrete implementations ────────────────────────────────────────────────


#: Max output tokens for the multimodal classify call. The schema is small
#: (a few short strings + 1-2 floats per sheet) so 1024 is generous; capping
#: at 1024 keeps an unintentionally chatty model from blowing through the
#: cost budget if the prompt is misread.
_CLASSIFY_MAX_TOKENS = 1024


def _strip_code_fences(text: str) -> str:
    """Strip ```json ... ``` fences if the model returned a fenced block."""
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


class AnthropicVisionModel:
    """Default vision provider. Wraps Anthropic Claude (current Sonnet).

    ``classify_image`` is wired in Sprint AI-02 for sheet classification.
    The other two methods remain stubs for AI-03 (schedule extraction) and
    AI-06 (ambiguous-symbol region analysis).

    The SDK is imported lazily inside the method so:
      * Tests can patch ``app.services.ai_models.anthropic.Anthropic`` even
        when the real package is missing locally.
      * Importing ``ai_models`` for type hints (factories) does not pay the
        SDK import cost (~50ms).
    """

    def __init__(self, model_id: str, api_key: str) -> None:
        self.model_id = model_id
        self._api_key = api_key

    def _ensure_configured(self) -> None:
        if not self._api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not configured -- AI vision calls will fail"
            )

    def classify_image(
        self, image_bytes: bytes, *, schema: dict[str, Any]
    ) -> dict[str, Any]:
        """Classify an image (or stack of images) using Claude vision.

        ``schema`` is a JSON schema (dict) describing the expected response
        shape; it is embedded in the system prompt so the model knows what
        to return. Multimodal callers (Stage 2 batch fallback) pre-compose a
        single PNG strip of N sheets before calling -- the schema then asks
        for a list of N classification objects.

        Returns the parsed JSON. Raises ``RuntimeError`` if the model returns
        non-JSON output (caller falls back to lexical-only on the bucket).
        """
        self._ensure_configured()
        with with_cost_tracking("anthropic_vision.classify_image") as cost:
            try:
                import anthropic  # type: ignore[import-untyped]
            except ImportError as exc:  # pragma: no cover -- installed via requirements.txt
                raise RuntimeError(
                    "anthropic SDK is not installed; pip install anthropic"
                ) from exc

            client = anthropic.Anthropic(api_key=self._api_key)
            schema_json = json.dumps(schema, indent=2)
            system_prompt = (
                "You are a construction-document classifier. Look at the supplied image "
                "and return a JSON object that matches this schema EXACTLY. Output ONLY "
                "the JSON -- no prose, no code fences.\n\nSchema:\n" + schema_json
            )
            image_b64 = base64.standard_b64encode(image_bytes).decode("ascii")
            response = client.messages.create(
                model=self.model_id,
                max_tokens=_CLASSIFY_MAX_TOKENS,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_b64,
                                },
                            },
                            {
                                "type": "text",
                                "text": (
                                    "Classify the construction drawing(s) in the image "
                                    "according to the schema. Return JSON only."
                                ),
                            },
                        ],
                    }
                ],
            )

            usage = getattr(response, "usage", None)
            input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
            output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
            settings = get_settings()
            input_cents = (
                input_tokens / 1000.0 * settings.ai_anthropic_vision_input_per_1k_cents
            )
            output_cents = (
                output_tokens / 1000.0 * settings.ai_anthropic_vision_output_per_1k_cents
            )
            cost.cost_cents = _round_up_cents(input_cents + output_cents)
            cost.tokens_used = input_tokens + output_tokens
            cost.metadata = {
                "model_id": self.model_id,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }

            content_blocks = getattr(response, "content", None) or []
            text_chunks: list[str] = []
            for block in content_blocks:
                # Anthropic SDK returns objects with a ``type`` and ``text``
                # attribute; tests may pass dicts.
                btype = getattr(block, "type", None) or (
                    block.get("type") if isinstance(block, dict) else None
                )
                if btype != "text":
                    continue
                btext = getattr(block, "text", None) or (
                    block.get("text") if isinstance(block, dict) else None
                )
                if btext:
                    text_chunks.append(str(btext))

            raw = "".join(text_chunks).strip()
            if not raw:
                raise RuntimeError(
                    "AnthropicVisionModel.classify_image: empty response body"
                )
            try:
                return json.loads(_strip_code_fences(raw))
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"AnthropicVisionModel.classify_image: response was not JSON: {raw[:200]}"
                ) from exc

    def extract_structured(
        self,
        image_bytes: bytes,
        *,
        prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        self._ensure_configured()
        with with_cost_tracking("anthropic_vision.extract_structured"):
            raise NotImplementedError(
                "AnthropicVisionModel.extract_structured is wired in Sprint AI-03"
            )

    def analyze_region(
        self,
        image_bytes: bytes,
        *,
        bbox_pdf: dict[str, float],
        prompt: str,
    ) -> str:
        self._ensure_configured()
        with with_cost_tracking("anthropic_vision.analyze_region"):
            raise NotImplementedError(
                "AnthropicVisionModel.analyze_region is wired in Sprint AI-06"
            )


class AnthropicLLMModel:
    """Default text-only LLM. Same SDK family as the vision model."""

    def __init__(self, model_id: str, api_key: str) -> None:
        self.model_id = model_id
        self._api_key = api_key

    def _ensure_configured(self) -> None:
        if not self._api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not configured -- AI LLM calls will fail"
            )

    def summarize(self, text: str, *, max_chars: int) -> str:
        self._ensure_configured()
        with with_cost_tracking("anthropic_llm.summarize"):
            raise NotImplementedError(
                "AnthropicLLMModel.summarize is wired in Sprint AI-04"
            )

    def structured_output(
        self, prompt: str, *, schema: dict[str, Any]
    ) -> dict[str, Any]:
        self._ensure_configured()
        with with_cost_tracking("anthropic_llm.structured_output"):
            raise NotImplementedError(
                "AnthropicLLMModel.structured_output is wired in Sprint AI-04"
            )


class OpenAIEmbeddingModel:
    """Default embedding provider. ``text-embedding-3-small`` is 1536-dim."""

    DEFAULT_DIMENSIONS = 1536

    def __init__(self, model_id: str, api_key: str) -> None:
        self.model_id = model_id
        self._api_key = api_key
        self.dimensions = self.DEFAULT_DIMENSIONS

    def _ensure_configured(self) -> None:
        if not self._api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured -- AI embedding calls will fail"
            )

    def embed_text(self, text: str) -> list[float]:
        self._ensure_configured()
        with with_cost_tracking("openai_embedding.embed_text"):
            raise NotImplementedError(
                "OpenAIEmbeddingModel.embed_text is wired in Sprint AI-04"
            )

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self._ensure_configured()
        with with_cost_tracking("openai_embedding.embed_batch"):
            raise NotImplementedError(
                "OpenAIEmbeddingModel.embed_batch is wired in Sprint AI-04"
            )


# ─── Factories ───────────────────────────────────────────────────────────────


_VISION_PROVIDERS: dict[str, type] = {
    "anthropic": AnthropicVisionModel,
}
_EMBEDDING_PROVIDERS: dict[str, type] = {
    "openai": OpenAIEmbeddingModel,
}
_LLM_PROVIDERS: dict[str, type] = {
    "anthropic": AnthropicLLMModel,
}


def _resolve(name: str, provider: str, table: dict[str, type]) -> type:
    cls = table.get(provider.lower())
    if cls is None:
        valid = ", ".join(sorted(table.keys()))
        raise RuntimeError(
            f"Unknown {name} provider '{provider}' (configured providers: {valid})"
        )
    return cls


def get_vision_model() -> VisionModel:
    settings = get_settings()
    cls = _resolve("vision", settings.ai_vision_provider, _VISION_PROVIDERS)
    return cls(model_id=settings.ai_vision_model, api_key=settings.anthropic_api_key)


def get_embedding_model() -> EmbeddingModel:
    settings = get_settings()
    cls = _resolve("embedding", settings.ai_embedding_provider, _EMBEDDING_PROVIDERS)
    return cls(model_id=settings.ai_embedding_model, api_key=settings.openai_api_key)


def get_llm_model() -> LLMModel:
    settings = get_settings()
    cls = _resolve("llm", settings.ai_llm_provider, _LLM_PROVIDERS)
    return cls(model_id=settings.ai_llm_model, api_key=settings.anthropic_api_key)


def model_versions_snapshot() -> dict[str, str]:
    """Snapshot the active provider+model ids for ``ai_runs.model_versions``."""
    settings = get_settings()
    return {
        "vision": f"{settings.ai_vision_provider}:{settings.ai_vision_model}",
        "embedding": f"{settings.ai_embedding_provider}:{settings.ai_embedding_model}",
        "llm": f"{settings.ai_llm_provider}:{settings.ai_llm_model}",
    }
