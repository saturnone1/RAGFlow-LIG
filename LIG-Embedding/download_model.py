from __future__ import annotations

import argparse
from pathlib import Path

from huggingface_hub import snapshot_download


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    snapshot_download(
        repo_id=args.model_id,
        revision=args.revision,
        local_dir=args.output,
        allow_patterns=[
            "1_Pooling/*",
            "config.json",
            "config_sentence_transformers.json",
            "merges.txt",
            "model.safetensors",
            "modules.json",
            "sentence_bert_config.json",
            "special_tokens_map.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "vocab.json",
        ],
    )


if __name__ == "__main__":
    main()
