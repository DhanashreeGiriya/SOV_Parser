"""
Local embedding matcher for header mapping.

Wraps a locally-downloaded BAAI/BGE sentence-transformer model and exposes
cosine-similarity matching of raw column headers against the ALIAS_MAP
synonym phrases (grouped by target field).

This is used as an *added* semantic pass in map_headers(): embeddings replace
the lexical fuzzy score in the reference-dictionary fuzzy pass, with the old
fuzzywuzzy path retained as a fallback (see matching.py). The model runs on
CPU and is loaded once (lazy singleton); alias-phrase embeddings are
precomputed at construction and cached for the process lifetime.

Model location is `models/bge-large-en-v1.5` by default, overridable via the
SOV_EMBED_MODEL env var. The loader forces offline mode so a first run never
silently hits the network — the weights must already be on disk.
"""
from __future__ import annotations

import os
from collections import defaultdict
from pathlib import Path

import numpy as np

from header_mapping.aliases import ALIAS_MAP
from header_mapping.excel_io import _normalise

# ── configuration ────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_MODEL_DIR = _REPO_ROOT / "models" / "bge-large-en-v1.5"
MODEL_PATH = os.environ.get("SOV_EMBED_MODEL", str(_DEFAULT_MODEL_DIR))

# Master switch — set SOV_DISABLE_EMBEDDINGS=1 to fall back to pure fuzzy.
EMBEDDINGS_ENABLED = os.environ.get("SOV_DISABLE_EMBEDDINGS", "0") != "1"

# ── cosine -> confidence calibration (tuned against the gold set) ─────────────
# Below EMBED_MIN_COS the embedding pass declines and hands back to fuzzy.
# The confidence curve is deliberately conservative: only genuinely close
# matches reach the 82 auto-accept line so we don't manufacture new silent
# corruption. See eval harness for the numbers behind these constants.
EMBED_MIN_COS = 0.62          # floor to even consider an embedding match
EMBED_ACCEPT_COS = 0.78       # cosine at which confidence hits the 82 threshold
EMBED_HIGH_COS = 0.92         # cosine at which confidence saturates near 97
# Country codes are a notorious false-positive magnet (county/country, etc.);
# require a very strong signal, mirroring the >=96 fuzzy guard in matching.py.
EMBED_COUNTRY_MIN_COS = 0.90
# Ownership guard: the per-field loop in map_headers processes schema fields in
# order and claims greedily, so an earlier field can steal a header that clearly
# belongs to a later field (e.g. LocationID stealing "Number of Buildings" from
# RiskCount). A field may only claim a header if it is that header's globally
# best target, or within this cosine margin of it.
EMBED_OWNERSHIP_MARGIN = 0.02


def _compute_embedding_confidence(cos: float) -> int:
    """Map a cosine similarity in [EMBED_MIN_COS, 1] to the 0-100 confidence
    scale used throughout the mapping pipeline. Piecewise-linear:
      EMBED_ACCEPT_COS -> 82   (the auto-accept / AI-review threshold)
      EMBED_HIGH_COS   -> 97
    Clamped to [70, 97] so an embedding match never claims exact-match certainty.
    """
    if cos <= EMBED_ACCEPT_COS:
        # 70 at the floor, ramping up to 82 at the accept line
        span = max(1e-6, EMBED_ACCEPT_COS - EMBED_MIN_COS)
        conf = 70 + (cos - EMBED_MIN_COS) / span * (82 - 70)
    else:
        span = max(1e-6, EMBED_HIGH_COS - EMBED_ACCEPT_COS)
        conf = 82 + (cos - EMBED_ACCEPT_COS) / span * (97 - 82)
    return int(max(70, min(97, round(conf))))


class Embedder:
    """Lazy, CPU-only sentence-transformer wrapper with an alias corpus."""

    def __init__(self, model_path: str = MODEL_PATH):
        # Never reach for the network — weights must be on disk already.
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        from sentence_transformers import SentenceTransformer  # heavy import, defer

        self.model = SentenceTransformer(model_path, device="cpu")
        self._vec_cache: dict[str, np.ndarray] = {}

        # Build alias corpus grouped by target field, embedded once.
        target_phrases: dict[str, list[str]] = defaultdict(list)
        for phrase, target in ALIAS_MAP.items():
            target_phrases[target].append(_normalise(phrase))

        self._target_phrases: dict[str, list[str]] = {}
        self._target_mat: dict[str, np.ndarray] = {}
        for target, phrases in target_phrases.items():
            uniq = sorted(set(p for p in phrases if p))
            if not uniq:
                continue
            self._target_phrases[target] = uniq
            self._target_mat[target] = self._encode(uniq)

    # ── encoding ──────────────────────────────────────────────────────────
    def _encode(self, texts: list[str]) -> np.ndarray:
        """Return L2-normalised embeddings [n, dim] for a list of strings."""
        return np.asarray(
            self.model.encode(
                texts,
                normalize_embeddings=True,
                show_progress_bar=False,
                convert_to_numpy=True,
            ),
            dtype=np.float32,
        )

    def vec(self, text: str) -> np.ndarray:
        """Cached single-string embedding (normalised)."""
        key = text or ""
        v = self._vec_cache.get(key)
        if v is None:
            v = self._encode([key])[0]
            self._vec_cache[key] = v
        return v

    def warm(self, texts: list[str]) -> None:
        """Pre-embed a batch of strings into the cache in one forward pass."""
        missing = [t for t in {(t or "") for t in texts} if t not in self._vec_cache]
        if not missing:
            return
        mat = self._encode(missing)
        for t, v in zip(missing, mat):
            self._vec_cache[t] = v

    # ── matching ────────────────────────────────────────────────────────────
    def best_alias(self, header_norm: str, target: str) -> tuple[float, str]:
        """Best cosine similarity of `header_norm` to any alias phrase of
        `target`, plus the winning alias phrase. (0.0, "") if target has no
        aliases."""
        mat = self._target_mat.get(target)
        if mat is None or len(mat) == 0:
            return 0.0, ""
        sims = mat @ self.vec(header_norm)
        i = int(np.argmax(sims))
        return float(sims[i]), self._target_phrases[target][i]

    def best_target(self, header_norm: str) -> tuple[str, float, str]:
        """Best target across the whole alias corpus — for diagnostics."""
        best_t, best_c, best_p = "", 0.0, ""
        v = self.vec(header_norm)
        for target, mat in self._target_mat.items():
            sims = mat @ v
            i = int(np.argmax(sims))
            if sims[i] > best_c:
                best_c, best_t, best_p = float(sims[i]), target, self._target_phrases[target][i]
        return best_t, best_c, best_p


# ── lazy singleton ───────────────────────────────────────────────────────────
_EMBEDDER: Embedder | None = None
_LOAD_FAILED = False


def get_embedder() -> Embedder | None:
    """Return the process-wide Embedder, or None if embeddings are disabled or
    the model cannot be loaded (caller then falls back to fuzzy matching)."""
    global _EMBEDDER, _LOAD_FAILED
    if not EMBEDDINGS_ENABLED or _LOAD_FAILED:
        return None
    if _EMBEDDER is None:
        try:
            _EMBEDDER = Embedder()
        except Exception as exc:  # noqa: BLE001 - degrade gracefully to fuzzy
            _LOAD_FAILED = True
            import warnings
            warnings.warn(f"Embedding model unavailable ({exc}); using fuzzy matching only.")
            return None
    return _EMBEDDER
