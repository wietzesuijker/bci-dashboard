"""Fair comparison of independent representations on a shared candidate set."""

import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]


def comparison():
    pytest.importorskip("numpy")
    path = ROOT / "labelling/compare_embedding_atlases.py"
    spec = importlib.util.spec_from_file_location("comparison_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def decoded(result):
    keys = [row[0] for row in result["cohort"]]
    return {
        key: {
            "overlap": row[0],
            "models": [
                {
                    "labelled_support": model[0],
                    "same_recorded_label": model[1],
                    "neighbors": [[keys[i], score] for i, score in model[2]],
                }
                for model in row[1]
            ],
        }
        for key, row in zip(keys, result["frames"])
    }


def test_common_candidates_self_exclusion_and_distinct_dimensions():
    result = comparison().compare_matrices(
        {
            "comb_a.JPG": [1.0, 0],
            "comb_b.JPG": [0.9, 0.1],
            "comb_c.JPG": [0.0, 1],
            "only_first": [1.0, 0],
        },
        {
            "a": [1.0, 0, 0],
            "b": [0, 1.0, 0],
            "c": [0.9, 0, 0.1],
            "only_second": [1.0, 0, 0],
        },
        {"comb_a.JPG": "A", "comb_b.JPG": "A"},
        neighbours=1,
    )
    assert result["cohort_size"] == 3
    assert result["dimensions"] == [2, 3]
    assert result["unshared_counts"] == [1, 1]
    a = decoded(result)["comb_a.JPG"]
    assert a["overlap"] == 0
    assert a["models"][0]["neighbors"][0][0] == "comb_b.JPG"
    assert a["models"][1]["neighbors"][0][0] == "comb_c.JPG"
    assert a["models"][0]["labelled_support"] == 1
    assert a["models"][0]["same_recorded_label"] == 1
    assert a["models"][1]["labelled_support"] == 0
    assert decoded(result)["comb_c.JPG"]["models"][0]["same_recorded_label"] is None
    assert "embedding" not in str(result)


def test_ties_order_by_frame_key_and_no_self_or_unshared():
    result = comparison().compare_matrices(
        {"c": [1.0, 0], "b": [1.0, 0], "a": [1.0, 0]},
        {"a": [1.0, 0], "c": [1.0, 0], "b": [1.0, 0]},
        neighbours=12,
    )
    assert result["k"] == 2
    assert decoded(result)["c"]["models"][0]["neighbors"] == [["a", 1.0], ["b", 1.0]]
    assert all(row["overlap"] == 2 for row in decoded(result).values())
    assert result["labelled_cohort_support"] == 0


def test_alias_collisions_invalid_vectors_and_shape_boundaries():
    with pytest.raises(ValueError, match="collision"):
        comparison().compare_matrices(
            {"a": [1.0, 0], "comb_a.JPG": [1.0, 0]}, {"a": [1.0, 0]}
        )
    with pytest.raises(ValueError, match="dimensions"):
        comparison().compare_matrices(
            {"a": [1.0, 0], "b": [1.0, 0, 0]}, {"a": [1.0, 0], "b": [1.0, 0]}
        )
    result = comparison().compare_matrices(
        {"a": [1.0, 0], "b": [0.0, 1], "c": [float("nan"), 0]},
        {"a": [1.0, 0], "b": [0.0, 1], "c": [1.0, 0]},
    )
    assert result["invalid_common_keys"] == ["c"]
    assert result["cohort_size"] == 2


def test_compact_comparison_renders_neighbor_label_and_selection():
    from test_atlas_mission_view import photo, run_atlas

    checks = r"""
data.comparison={cohort:[['a','Species A'],['b','Species B']],frames:[[1,[[1,0,[[1,.3]]],[1,0,[[1,.4]]]]]],models:['first','second'],k:1,cohort_size:2,labelled_cohort_support:2,labels_available:true,method:'cosine',label_boundary:'recorded',invalid_common_keys:[],unshared_counts:[0,0],sources:[]};
compareSelection('a');
assert.match($('modelComparisonQueryLabel').textContent,/Species A/);
assert.match($('comparisonSummary').textContent,/1 of 1 nearest frames shared/);
const model=$('comparisonModels').children[0];
assert.match(model.children[1].textContent,/0 of 1 labelled neighbors/);
const button=model.children[2].children[0].children[0];
assert.match(button.textContent,/Select this photo: Species B.*b.*Shared-cohort cosine 0.300/);
button.onclick();assert.equal(selected,1);
assert.equal(document.activeElement,$('modelComparisonQueryKey'));
compareSelection('outside');assert.match($('comparisonSummary').textContent,/outside the shared/);
"""
    run_atlas(
        [photo("a", "mission", label="Species A"), photo("b", "mission", label="Species B")],
        checks,
        initial_hash="#frame=a",
    )
