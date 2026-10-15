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

    html = module(ROOT / "dashboard/embedding_atlas_assets.py").HTML
    css = html.split("<style>")[1].split("</style>")[0]
    classes = {
        c for match in re.findall(r'class="([\w -]+)"', html) for c in match.split()
    }
    assert classes <= set(re.findall(r"\.([a-zA-Z][\w-]*)", css))


def test_stable_frame_url_encoding_and_unknown_key_fallback():
    import shutil
    import subprocess

    if not shutil.which("node"):
        pytest.skip("Node is needed to execute browser URL helpers")
    html = module(ROOT / "dashboard/embedding_atlas_assets.py").HTML
    helpers = html.split("// URL_HELPERS_START")[1].split("// URL_HELPERS_END")[0]
    checks = r"""
const assert = require('node:assert/strict');
const key = 'comb_frame + #&/é.JPG';
const points = [{key:'first'}, {key}];
assert.deepEqual(frameFromHash(frameHash(key), points), {index:1,missing:false});
assert.deepEqual(frameFromHash('#frame=unknown', points), {index:0,missing:true});
assert.deepEqual(frameFromHash('', points), {index:0,missing:false});
assert.deepEqual(frameFromHash('#frame=%E0%A4%A', points), {index:0,missing:true});
"""
    subprocess.run(["node", "-e", helpers + checks], check=True)


def test_botanist_labels_exact_join_missing_and_provenance(tmp_path):
    export = module(ROOT / "labelling/export_embedding_atlas.py").export
    fixture_pool(tmp_path)
    (tmp_path / "gt_dominant_taxon.csv").write_text(
        "global_key,wcvp_canonical_name\na,Apeiba membranacea\ncomb_b.JPG,Not an exact key\nc,\n"
    )
    result = export(tmp_path)
    assert [p["label"] for p in result["points"]] == ["Apeiba membranacea", None, None]
    assert result["provenance"]["labels"]["matched_count"] == 1
    assert result["provenance"]["labels"]["source_count"] == 2
    assert result["provenance"]["labels"]["available"] is True
    assert any(
        s["file"] == "gt_dominant_taxon.csv" and len(s["sha256"]) == 64
        for s in result["provenance"]["sources"]
    )
    (tmp_path / "gt_dominant_taxon.csv").unlink()
    result = export(tmp_path)
    assert result["provenance"]["labels"]["available"] is False
    assert all(p["label"] is None for p in result["points"])


@pytest.mark.parametrize("second", ["Same label", "Conflicting label"])
def test_duplicate_botanist_label_keys_fail(tmp_path, second):
    fixture_pool(tmp_path)
    (tmp_path / "gt_dominant_taxon.csv").write_text(
        "global_key,wcvp_canonical_name\na,Same label\na," + second + "\n"
    )
    with pytest.raises(ValueError, match="Duplicate or conflicting"):
        module(ROOT / "labelling/export_embedding_atlas.py").export(tmp_path)


def test_map_zoom_pan_and_tile_work_remain_bounded():
    import shutil
    import subprocess
    if not shutil.which('node'):
        pytest.skip('Node is needed to execute map geometry helpers')
    html = module(ROOT / 'dashboard/embedding_atlas_assets.py').HTML
    helpers = html.split('// MAP_HELPERS_START')[1].split('// MAP_HELPERS_END')[0]
    checks = r'''
const assert=require('node:assert/strict');
let v={x:.5,y:.5,scale:256*2**17};
for(let i=0;i<2000;i++)v=boundedView({...v,scale:v.scale/1.6},640,520);
assert.ok(v.scale>=640);
for(let i=0;i<2000;i++)v=boundedView({...v,scale:v.scale*1.6},640,520);
assert.ok(v.scale<=256*2**19);
for(const raw of [{x:Infinity,y:NaN,scale:0},{x:-1e200,y:1e200,scale:Infinity},{x:2,y:-4,scale:128}]){
 const v=boundedView(raw,640,520),range=tileGeometry(v,640,520);
 assert.ok(Object.values(v).every(Number.isFinite));
 assert.ok(v.x>=0&&v.x<=1&&v.y>=0&&v.y<=1);
 assert.ok(range.tiles.length<=128);
 assert.ok(range.tiles.every(([x,y])=>x>=0&&y>=0&&x<2**range.z&&y<2**range.z));
}
for(const p of [{lat:90,lon:180},{lat:-90,lon:-180},{lat:NaN,lon:Infinity}]){
 assert.ok(merc(p).every(x=>Number.isFinite(x)&&x>=0&&x<=1));
}
const cache=new Map();for(let i=0;i<2000;i++)cacheTile(cache,String(i),{});
assert.ok(cache.size<=256);
'''
    subprocess.run(['node', '-e', helpers + checks], check=True)


def test_failed_tiles_and_photo_keep_selection_usable_without_retry_loop():
    import shutil
    import subprocess
    if not shutil.which('node'):
        pytest.skip('Node is needed to execute network failure handling')
    html = module(ROOT / 'dashboard/embedding_atlas_assets.py').HTML
    script = html.split('<script>')[1].split('</script>')[0]
    setup = r'''
const assert=require('node:assert/strict');
let imageRequests=0,pending=[];
const elements=new Map();
const context=new Proxy({}, {get:()=>()=>{}});
function element(id){if(!elements.has(id))elements.set(id,{clientWidth:640,clientHeight:520,value:'',getContext:()=>context,replaceChildren(){},append(){},removeAttribute(){},setAttribute(){},addEventListener(){}});return elements.get(id)}
const payload={points:[{key:'a',lat:9.1,lon:-79.8,xy:[0,0],rgb:[1,2,3],neighbours:[],image:'https://example.org/photo.jpg',group:'Labelled'}],provenance:{encoder:'test',versions:[],dimensions:3,projection:'PCA',input_count:1,excluded:{},sources:[]}};
element('atlas-data').textContent=JSON.stringify(payload);
global.document={getElementById:element,querySelectorAll:()=>[],createElement:()=>element('button')};
global.devicePixelRatio=1;global.location={hash:''};global.history={replaceState(){}};global.window={addEventListener(){}};
global.requestAnimationFrame=f=>{pending.push(f)};
global.Image=class{set src(v){imageRequests++;this.complete=true;this.naturalWidth=0;if(this.onerror)this.onerror()}};
'''
    checks = r'''
const requestsAfterInitialDraw=imageRequests;
for(let i=0;i<20&&pending.length;i++)pending.shift()();
assert.equal(imageRequests,requestsAfterInitialDraw);
assert.equal(pending.length,0);
assert.match(element('basemapStatus').textContent,/Basemap unavailable/);
assert.equal(element('key').textContent,'a');
element('photo').onerror();
assert.equal(element('photo').hidden,true);
assert.match(element('photoStatus').textContent,/Photo unavailable/);
'''
    subprocess.run(['node', '-e', setup + script + checks], check=True)
