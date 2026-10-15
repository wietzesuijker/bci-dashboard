"""Representation export boundaries and safe standalone rendering."""

import importlib.util
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]


def module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def fixture_pool(tmp_path):
    np = pytest.importorskip("numpy")
    rows = []
    for directory, entries in [
        ("embeddings_labelled", [("a", [1.0, 0, 0]), ("b", [0.99, 0.01, 0])]),
        ("embeddings_queue", [("c", [0.0, 1, 0]), ("missing", [0.0, 0, 1])]),
    ]:
        folder = tmp_path / directory
        (folder / "cache").mkdir(parents=True)
        np.savez(
            folder / "embeddings.npz",
            keys=[k for k, v in entries],
            embeddings=[v for k, v in entries],
        )
        for key, _ in entries:
            (folder / "cache" / (key + ".json")).write_text(
                json.dumps({"version": "test-encoder", "crop_size": 1280})
            )
            rows.append(
                {
                    "global_key": key,
                    "media_attributes": {
                        "gpsPoint": None if key == "missing" else "9.1,-79.8"
                    },
                    "metadata": {},
                    "row_data": "https://example.org/frame.jpg",
                }
            )
    (tmp_path / "dataset_rows_combined.jsonl").write_text(
        "\n".join(map(json.dumps, rows))
    )
    return tmp_path


def test_real_cosine_neighbors_and_excluded_positions(tmp_path):
    export = module(ROOT / "labelling/export_embedding_atlas.py").export
    result = export(fixture_pool(tmp_path))
    assert len(result["points"]) == 3
    assert result["points"][0]["neighbours"][0][0] == 1
    assert result["points"][0]["neighbours"][0][1] > 0.99
    assert result["provenance"]["excluded"] == {"missing_or_invalid_position": 1}
    assert result["provenance"]["input_count"] == 4
    assert all(len(s["sha256"]) == 64 for s in result["provenance"]["sources"])
    assert "not crown centroids" in result["provenance"]["position"]


def test_encoder_mismatch_fails(tmp_path):
    export = module(ROOT / "labelling/export_embedding_atlas.py").export
    fixture_pool(tmp_path)
    (tmp_path / "embeddings_queue/cache/c.json").write_text('{"version":"another"}')
    with pytest.raises(ValueError, match="Mixed encoder"):
        export(tmp_path)


def test_builder_escapes_script_injection(tmp_path):
    source, output = tmp_path / "source.json", tmp_path / "atlas.html"
    source.write_text(
        json.dumps(
            {
                "points": [],
                "provenance": {"encoder": "</script><script>alert(1)</script>"},
            }
        )
    )
    module(ROOT / "dashboard/build_embedding_atlas.py").build(source, output)
    html = output.read_text()
    assert "</script><script>alert(1)" not in html
    assert "__ATLAS_DATA__" not in html
    assert "\\u003c/script>" in html


def test_crownfirst_separate_space_and_canonical_collision(tmp_path):
    export = module(ROOT / "labelling/export_embedding_atlas.py").export
    fixture_pool(tmp_path)
    source = tmp_path / "crownfirst.json"
    source.write_text(
        json.dumps({"comb_a.JPG": [1.0, 0, 0], "b": [0.9, 0.1, 0], "c": [0, 1.0, 0]})
    )
    result = export(
        tmp_path, crownfirst_embeddings=source, encoder_label="PlantCLEF test"
    )
    assert len(result["points"]) == 3
    assert result["provenance"]["encoder"] == "PlantCLEF test"
    assert result["points"][0]["key"] == "a"
    assert all("embedding" not in p for p in result["points"])
    source.write_text(json.dumps({"a": [1.0, 0, 0], "comb_a.JPG": [0.0, 1, 0]}))
    with pytest.raises(ValueError, match="collision"):
        export(tmp_path, crownfirst_embeddings=source, encoder_label="test")


def test_external_vector_shape_and_neighbor_count(tmp_path):
    export = module(ROOT / "labelling/export_embedding_atlas.py").export
    fixture_pool(tmp_path)
    source = tmp_path / "external.json"
    source.write_text('{"a": 1, "b": 2}')
    with pytest.raises(ValueError, match="align"):
        export(tmp_path, crownfirst_embeddings=source, encoder_label="test")
    with pytest.raises(ValueError, match="positive"):
        export(tmp_path, neighbours=0)
    result = export(tmp_path)
    assert 0 <= sum(result["provenance"]["pca_explained_variance"][:2]) <= 1.000001


def test_atlas_has_styles_for_its_own_classes():
    import re
    html = module(ROOT / 'dashboard/embedding_atlas_assets.py').HTML
    css = html.split('<style>')[1].split('</style>')[0]
    classes = {c for match in re.findall(r'class="([\w -]+)"', html) for c in match.split()}
    assert classes <= set(re.findall(r'\.([a-zA-Z][\w-]*)', css))
