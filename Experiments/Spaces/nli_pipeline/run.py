"""S0 — NLI Pipeline baseline: precomputed DeBERTa-v3-large space predictions.

Reads th_space predictions from Step 4 (cooccurrence_nli.jsonl) and evaluates
them against annotation_spaces.json. Matched by sentence text.

Dependency: Step 4 must have been run first:
    python run.py pipeline --step 4

Model: cross-encoder/nli-deberta-v3-large
Space hypotheses: "This text is about {label}." for each of 4 TH spaces.

Run:
    python Experiments/Spaces/nli_pipeline/run.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "shared"))
from eval_utils import (
    SPACE_LABELS,
    load_spaces_eval,
    save_outputs,
)

_REPO_ROOT = Path(__file__).parent.parent.parent.parent
_STEP3_DIR = _REPO_ROOT / "data/processed/step3"
NLI_FILE   = _STEP3_DIR / "cooccurrence_nli.jsonl"
FALLBACK    = _STEP3_DIR / "cooccurrence.jsonl"


def _load_space_lookup() -> dict[str, str]:
    """Build sentence_text → th_space lookup from NLI output."""
    source = NLI_FILE if NLI_FILE.exists() else FALLBACK
    if not source.exists():
        raise FileNotFoundError(
            f"NLI output not found: {NLI_FILE}\n"
            "Run step 4 first: python run.py pipeline --step 4"
        )
    if source == FALLBACK:
        print("[WARN] cooccurrence_nli.jsonl not found — falling back to cooccurrence.jsonl")
    else:
        print(f"[INFO] Reading NLI space predictions from {source.name}")

    lookup: dict[str, str] = {}
    with source.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            space = row.get("th_space")
            if not space:
                continue
            text = row.get("central_sent_text") or row.get("sent_text", "")
            if text and text not in lookup:
                lookup[text] = space
    return lookup


def main() -> None:
    eval_entries = load_spaces_eval()
    print(f"Loaded {len(eval_entries)} labeled space examples")

    space_lookup = _load_space_lookup()
    print(f"Loaded {len(space_lookup)} NLI space predictions from pipeline")

    true_labels, pred_labels = [], []
    not_found = 0

    for entry in eval_entries:
        sentence = entry.get("sentence", "").strip()
        pred = space_lookup.get(sentence)
        if pred is None:
            pred = "knowledge_space"  # most common class as fallback
            not_found += 1
        true_labels.append(entry["true_space"])
        pred_labels.append(pred)

    if not_found:
        print(f"[WARN] {not_found}/{len(eval_entries)} eval entries not found in NLI output "
              f"(matched by sentence text). Defaulting to knowledge_space.")

    predictions = [
        {"id": i, "true": t, "pred": p, "text": eval_entries[i]["sentence"]}
        for i, (t, p) in enumerate(zip(true_labels, pred_labels))
    ]

    approach_dir = Path(__file__).parent
    save_outputs(approach_dir, predictions, true_labels, pred_labels, SPACE_LABELS)


if __name__ == "__main__":
    main()
