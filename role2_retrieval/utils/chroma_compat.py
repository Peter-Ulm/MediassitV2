"""Compatibility helpers for the bundled ChromaDB store."""

from __future__ import annotations

import json
import pickle
import sqlite3
from dataclasses import dataclass
from pathlib import Path


_CURRENT_COLLECTION_CONFIG = {
    "hnsw_configuration": {
        "space": "l2",
        "ef_construction": 100,
        "ef_search": 10,
        "num_threads": 12,
        "M": 16,
        "resize_factor": 1.2,
        "batch_size": 100,
        "sync_threshold": 1000,
        "_type": "HNSWConfigurationInternal",
    },
    "_type": "CollectionConfigurationInternal",
}


@dataclass
class ChromaIndexMetadata:
    dimensionality: int
    total_elements_added: int
    max_seq_id: int
    id_to_label: dict
    label_to_id: dict
    id_to_seq_id: dict


def ensure_collection_config(chroma_path: str, collection_name: str) -> bool:
    """Patch legacy collection config rows so current ChromaDB can open them."""
    db_path = Path(chroma_path) / "chroma.sqlite3"
    if not db_path.exists():
        return False

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        row = cur.execute(
            "SELECT config_json_str FROM collections WHERE name = ?",
            (collection_name,),
        ).fetchone()
        if not row:
            return False

        config_json_str = row[0] or ""
        if '"_type"' in config_json_str:
            return False

        cur.execute(
            "UPDATE collections SET config_json_str = ? WHERE name = ?",
            (json.dumps(_CURRENT_COLLECTION_CONFIG), collection_name),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def ensure_index_metadata(chroma_path: str, collection_name: str) -> bool:
    """Rewrite legacy HNSW metadata pickles into the object shape Chroma expects."""
    root = Path(chroma_path)
    if not root.exists():
        return False

    collection_dimension = 0
    db_path = root / "chroma.sqlite3"
    if db_path.exists():
        conn = sqlite3.connect(db_path)
        try:
            cur = conn.cursor()
            row = cur.execute(
                "SELECT dimension FROM collections WHERE name = ?",
                (collection_name,),
            ).fetchone()
            if row and row[0]:
                collection_dimension = int(row[0])
        finally:
            conn.close()

    updated = False
    for metadata_path in root.glob("*/index_metadata.pickle"):
        with metadata_path.open("rb") as handle:
            payload = pickle.load(handle)

        dimensionality = None
        total_elements_added = 0
        max_seq_id = 0
        id_to_label = {}
        label_to_id = {}
        id_to_seq_id = {}

        if isinstance(payload, dict):
            dimensionality = payload.get("dimensionality")
            total_elements_added = payload.get("total_elements_added", 0)
            max_seq_id = payload.get("max_seq_id", 0)
            id_to_label = payload.get("id_to_label", {})
            label_to_id = payload.get("label_to_id", {})
            id_to_seq_id = payload.get("id_to_seq_id", {})
        elif hasattr(payload, "dimensionality"):
            dimensionality = getattr(payload, "dimensionality", None)
            total_elements_added = getattr(payload, "total_elements_added", 0)
            max_seq_id = getattr(payload, "max_seq_id", 0)
            id_to_label = getattr(payload, "id_to_label", {})
            label_to_id = getattr(payload, "label_to_id", {})
            id_to_seq_id = getattr(payload, "id_to_seq_id", {})
        else:
            continue

        migrated = ChromaIndexMetadata(
            dimensionality=int(dimensionality or collection_dimension or 0),
            total_elements_added=total_elements_added,
            max_seq_id=max_seq_id,
            id_to_label=id_to_label,
            label_to_id=label_to_id,
            id_to_seq_id=id_to_seq_id,
        )
        with metadata_path.open("wb") as handle:
            pickle.dump(migrated, handle, protocol=pickle.HIGHEST_PROTOCOL)
        updated = True

    return updated


def ensure_chroma_compatibility(chroma_path: str, collection_name: str) -> None:
    ensure_collection_config(chroma_path, collection_name)
    ensure_index_metadata(chroma_path, collection_name)