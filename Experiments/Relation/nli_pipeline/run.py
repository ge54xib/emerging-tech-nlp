"""R0 — NLI Pipeline baseline: precomputed DeBERTa-v3-large relation predictions.

This is not a standalone experiment — it reads predictions already computed by
Step 4 of the main pipeline (cooccurrence_nli.jsonl) and evaluates them against
the gold-standard annotation.json eval set.

Paper: Sainz et al. (2021). Label Verbalization and Entailment for Effective
       Zero and Few-Shot Relation Extraction. EMNLP 2021.
       (Same NLI RE principle; pipeline uses cross-encoder/nli-deberta-v3-large
        with Ranga & Etzkowitz 2013 verbalizations and 0.5 threshold.)

Dependency: Step 4 must have been run first:
    python run.py pipeline --step 4

Model: cross-encoder/nli-deberta-v3-large (435M params)
Threshold: NLI_THRESHOLD env var (default 0.5)

Run:
    python Experiments/Relation/nli_pipeline/run.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "shared"))
from eval_utils import (
    RELATION_LABELS,
    load_relation_eval,
    save_outputs,
)

_REPO_ROOT = Path(__file__).parent.parent.parent.parent
_STEP3_DIR = _REPO_ROOT / "data/processed/step3"
NLI_FILE   = _STEP3_DIR / "cooccurrence_nli.jsonl"
FALLBACK    = _STEP3_DIR / "cooccurrence.jsonl"


def _load_nli_lookup() -> dict[tuple, str]:
    """Build (doc_id, entity_1, entity_2) → relation_type lookup from NLI output."""
    source = NLI_FILE if NLI_FILE.exists() else FALLBACK
    if not source.exists():
        raise FileNotFoundError(
            f"NLI output not found: {NLI_FILE}\n"
            "Run step 4 first: python run.py pipeline --step 4"
        )
    if source == FALLBACK:
        print(f"[WARN] cooccurrence_nli.jsonl not found — falling back to cooccurrence.jsonl")
    else:
        print(f"[INFO] Reading NLI predictions from {source.name}")

    lookup: dict[tuple, str] = {}
    with source.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            rel = row.get("relation_type") or "no_explicit_relation"
            key = (
                str(row.get("doc_id", "")),
                str(row.get("entity_1", "")),
                str(row.get("entity_2", "")),
            )
            # Keep first occurrence (highest-scored pair from NLI)
            if key not in lookup:
                lookup[key] = rel
            # Also store reverse direction for lookup robustness
            rev = (key[0], key[2], key[1])
            if rev not in lookup:
                lookup[rev] = rel
    return lookup


def main() -> None:
    eval_entries = load_relation_eval()
    print(f"Loaded {len(eval_entries)} labeled relation examples")

    nli_lookup = _load_nli_lookup()
    print(f"Loaded {len(nli_lookup)} NLI predictions from pipeline")

    true_labels, pred_labels = [], []
    not_found = 0

    for entry in eval_entries:
        key = (
            str(entry.get("doc_id", "")),
            str(entry.get("entity_1", "")),
            str(entry.get("entity_2", "")),
        )
        pred = nli_lookup.get(key)
        if pred is None:
            pred = "no_explicit_relation"
            not_found += 1
        true_labels.append(entry["true_relation"])
        pred_labels.append(pred)

    if not_found:
        print(f"[WARN] {not_found}/{len(eval_entries)} eval entries not found in NLI output "
              f"(matched by doc_id + entity pair). Defaulting to no_explicit_relation.")

    predictions = [
        {
            "id":   i,
            "true": t,
            "pred": p,
            "text": eval_entries[i].get("central_sent_text") or eval_entries[i].get("sent_text", ""),
        }
        for i, (t, p) in enumerate(zip(true_labels, pred_labels))
    ]

    approach_dir = Path(__file__).parent
    save_outputs(approach_dir, predictions, true_labels, pred_labels, RELATION_LABELS)


if __name__ == "__main__":
    main()
