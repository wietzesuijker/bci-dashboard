"""Build the self-contained spatial representation explorer, using stdlib only."""

import argparse
import json
import runpy
from pathlib import Path


def validate_comparison(atlas, comparison):
    """Require comparison inputs to identify this exact representation and labels."""
    atlas_sources = atlas.get("provenance", {}).get("sources", [])
    embeddings = [s for s in atlas_sources if s["file"].endswith((".npz", ".json"))]
    if not embeddings:
        raise ValueError("Atlas embedding source provenance is missing")
    comparison_sources = {}
    for source in comparison.get("sources", []):
        name, digest = source["file"], source["sha256"]
        if name in comparison_sources and comparison_sources[name] != digest:
            raise ValueError("Conflicting comparison source hashes: " + name)
        comparison_sources[name] = digest
    required = embeddings + [s for s in atlas_sources if s["file"].endswith(".csv")]
    for source in required:
        name = source["file"]
        if name not in comparison_sources:
            raise ValueError("Comparison is missing atlas input source: " + name)
        if comparison_sources[name] != source["sha256"]:
            raise ValueError("Comparison source hash mismatch: " + name)
    available = atlas.get("provenance", {}).get("labels", {}).get("available")
    if available is not None and available != comparison.get("labels_available"):
        raise ValueError("Comparison and atlas label availability differ")


def build(source, output, comparison=None):
    data = json.loads(Path(source).read_text())
    if comparison:
        result = json.loads(Path(comparison).read_text())
        validate_comparison(data, result)
        data["comparison"] = result
    template = runpy.run_path(
        str(Path(__file__).with_name("embedding_atlas_assets.py"))
    )["HTML"]
    payload = json.dumps(data, separators=(",", ":"), allow_nan=False).replace(
        "<", "\\u003c"
    )
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(template.replace("__ATLAS_DATA__", payload))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="build/embedding-atlas.json")
    parser.add_argument("--output", default="build/embedding-atlas.html")
    parser.add_argument("--comparison")
    args = parser.parse_args()
    build(args.input, args.output, args.comparison)
