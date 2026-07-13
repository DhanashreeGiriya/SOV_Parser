"""
Download the local embedding model used for semantic header matching.

Fetches BAAI/bge-large-en-v1.5 into models/bge-large-en-v1.5 (git-ignored).
The header-mapping pipeline loads it offline from that path; if the model is
missing, matching silently falls back to fuzzy string matching.

Usage:
    python scripts/download_model.py
Override the target dir with SOV_EMBED_MODEL, or the repo id with the first arg.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ID = sys.argv[1] if len(sys.argv) > 1 else "BAAI/bge-large-en-v1.5"
ROOT = Path(__file__).resolve().parent.parent
DEST = Path(os.environ.get("SOV_EMBED_MODEL", ROOT / "models" / REPO_ID.split("/")[-1]))

ALLOW = [
    "*.json", "*.txt", "*.safetensors", "tokenizer*", "vocab*",
    "special_tokens*", "sentence_bert_config.json", "modules.json",
    "config_sentence_transformers.json", "1_Pooling/*",
]


def main() -> None:
    from huggingface_hub import snapshot_download

    DEST.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {REPO_ID} -> {DEST} ...")
    path = snapshot_download(repo_id=REPO_ID, local_dir=str(DEST), allow_patterns=ALLOW)
    print(f"Done: {path}")


if __name__ == "__main__":
    main()
