"""Export measured frame representations and hover positions for the atlas."""

from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export(
    data_root: Path, neighbours=12, crownfirst_embeddings=None, encoder_label=None
):
    if neighbours <= 0:
        raise ValueError("Neighbour count must be positive")
    inventory_path = data_root / "dataset_rows_combined.jsonl"
    inventory = {
        r["global_key"]: r
        for r in map(json.loads, inventory_path.read_text().splitlines())
    }
    records, vectors, sources, excluded, seen, versions = [], [], [], {}, set(), set()
    pools = []
    if crownfirst_embeddings:
        if not encoder_label:
            raise ValueError(
                "An explicit encoder label is required for crownfirst artifacts"
            )
        canonical = {}

        def canonical_key(key):
            return key.removeprefix("comb_").removesuffix(".JPG")

        for key in inventory:
            alias = canonical_key(key)
            if alias in canonical:
                raise ValueError("Canonical inventory key collision: " + alias)
            canonical[alias] = key
        external = json.loads(Path(crownfirst_embeddings).read_text())
        aliases = set()
        keys, vectors_external = [], []
        for key, vector in external.items():
            alias = canonical_key(key)
            if alias in aliases:
                raise ValueError("Canonical embedding key collision: " + alias)
            aliases.add(alias)
            keys.append(canonical.get(alias, key))
            vectors_external.append(vector)
        matrix = np.asarray(vectors_external, dtype=np.float64)
        sources.append(
            {
                "file": Path(crownfirst_embeddings).name,
                "sha256": sha(Path(crownfirst_embeddings)),
            }
        )
        pools.append(("Crownfirst pool", None, keys, matrix))
    else:
        for group, directory in [
            ("Labelled", "embeddings_labelled"),
            ("To label", "embeddings_queue"),
        ]:
            path = data_root / directory / "embeddings.npz"
            sources.append({"file": directory + "/embeddings.npz", "sha256": sha(path)})
            with np.load(path, allow_pickle=False) as archive:
                pools.append((group, directory, archive["keys"], archive["embeddings"]))
    for group, directory, keys, matrix in pools:
        if matrix.ndim != 2 or matrix.shape[1] < 3 or len(keys) != len(matrix):
            raise ValueError("Embedding keys and matrix rows must align")
        for key, vector in zip(keys, matrix):
            key = str(key)
            if key in seen:
                raise ValueError("Duplicate embedding key: " + key)
            seen.add(key)
            row = inventory.get(key)
            point = (row or {}).get("media_attributes", {}).get("gpsPoint")
            reason = None
            try:
                lat, lon = map(float, point.split(","))
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    raise ValueError()
            except (AttributeError, ValueError):
                reason = "missing_or_invalid_position"
            if not np.isfinite(vector).all() or np.linalg.norm(vector) == 0:
                reason = "invalid_embedding"
            if reason:
                excluded[reason] = excluded.get(reason, 0) + 1
                continue
            if crownfirst_embeddings:
                meta = {}
                version = encoder_label
            else:
                cache = data_root / directory / "cache" / (key + ".json")
                if not cache.exists():
                    raise ValueError("Missing encoder provenance: " + str(cache))
                meta = json.loads(cache.read_text())
                version = meta.get("version")
                if not version:
                    raise ValueError("Missing encoder version: " + key)
            versions.add(version)
            vectors.append(vector)
            records.append(
                {
                    "key": key,
                    "lat": lat,
                    "lon": lon,
                    "group": group,
                    "image": row.get("row_data", ""),
                    "mission": row.get("metadata", {}).get("mission", ""),
                    "crop": meta.get("crop_size"),
                    "version": version,
                }
            )
    if len(versions) > 1:
        raise ValueError("Mixed encoder versions cannot share a representation")
    if not vectors:
        raise ValueError("No valid positioned embeddings")
    x = np.asarray(vectors, dtype=np.float64)
    x /= np.linalg.norm(x, axis=1, keepdims=True)
    centered = x - x.mean(axis=0)
    values, axes = np.linalg.eigh(centered.T @ centered)
    explained = np.maximum(values, 0)[::-1]
    explained = explained / explained.sum() if explained.sum() else explained
    axes = axes[:, np.argsort(values)[::-1][:3]]
    for col in range(axes.shape[1]):
        if axes[np.argmax(np.abs(axes[:, col])), col] < 0:
            axes[:, col] *= -1
    projected = centered @ axes
    bounds = np.percentile(projected, [2, 98], axis=0)
    colors = np.clip(
        (projected - bounds[0]) / np.maximum(bounds[1] - bounds[0], 1e-12), 0, 1
    )
    for start in range(0, len(x), 128):
        similarity = x[start : start + 128] @ x.T
        for offset, scores in enumerate(similarity):
            i = start + offset
            scores[i] = -np.inf
            near = np.argsort(-scores, kind="stable")[: min(neighbours, len(x) - 1)]
            records[i].update(
                xy=projected[i, :2].round(7).tolist(),
                rgb=(55 + colors[i] * 175).astype(int).tolist(),
                neighbours=[[int(j), round(float(scores[j]), 5)] for j in near],
            )
    return {
        "points": records,
        "provenance": {
            "encoder": encoder_label
            if crownfirst_embeddings
            else "Pl@ntNet /v2/embeddings",
            "versions": sorted(versions),
            "dimensions": x.shape[1],
            "pca_explained_variance": explained[:3].round(8).tolist(),
            "projection": "PCA of L2-normalized vectors, fitted on this pool",
            "position": "Aircraft camera positions, not crown centroids",
            "excluded": excluded,
            "input_count": len(seen),
            "sources": sources
            + [{"file": inventory_path.name, "sha256": sha(inventory_path)}],
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument(
        "--output", type=Path, default=Path("build/embedding-atlas.json")
    )
    parser.add_argument("--crownfirst-embeddings", type=Path)
    parser.add_argument("--encoder-label")
    args = parser.parse_args()
    result = export(
        args.data_root,
        crownfirst_embeddings=args.crownfirst_embeddings,
        encoder_label=args.encoder_label,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, separators=(",", ":"), allow_nan=False))
    print(f"Exported {len(result['points'])} frame representations to {args.output}")


if __name__ == "__main__":
    main()
