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

    if not shutil.which("node"):
        pytest.skip("Node is needed to execute map geometry helpers")
    html = module(ROOT / "dashboard/embedding_atlas_assets.py").HTML
    helpers = html.split("// MAP_HELPERS_START")[1].split("// MAP_HELPERS_END")[0]
    checks = r"""
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
"""
    subprocess.run(["node", "-e", helpers + checks], check=True)


def test_failed_tiles_and_photo_keep_selection_usable_without_retry_loop():
    import shutil
    import subprocess

    if not shutil.which("node"):
        pytest.skip("Node is needed to execute network failure handling")
    html = module(ROOT / "dashboard/embedding_atlas_assets.py").HTML
    script = html.split("<script>")[1].split("</script>")[0]
    setup = r"""
const assert=require('node:assert/strict');
let imageRequests=0,pending=[];
const elements=new Map();
const context=new Proxy({}, {get:()=>()=>{}});
function element(id){if(!elements.has(id))elements.set(id,{children:[],clientWidth:640,clientHeight:520,value:'',style:{},focus(options){this.focused=true;this.focusOptions=options},scrollIntoView(options){this.scroll=options},getContext:()=>context,replaceChildren(...v){this.children=v},append(...v){this.children.push(...v)},removeAttribute(){},setAttribute(name,value){this[name]=value},getAttribute(name){return this[name]??null},addEventListener(){}});return elements.get(id)}
const payload={points:[{key:'a',lat:9.1,lon:-79.8,xy:[0,0],rgb:[1,2,3],neighbours:[],image:'https://example.org/photo.jpg',group:'Labelled'}],provenance:{encoder:'test',versions:[],dimensions:3,projection:'PCA',input_count:1,excluded:{},sources:[]}};
element('atlas-data').textContent=JSON.stringify(payload);
global.document={getElementById:element,querySelectorAll:()=>[],createElement:()=>element('button')};
global.devicePixelRatio=1;global.location={hash:''};global.history={replaceState(){}};global.window={addEventListener(){},matchMedia:q=>({matches:q==='(prefers-reduced-motion: reduce)'})};
global.requestAnimationFrame=f=>{pending.push(f)};
global.Image=class{set src(v){imageRequests++;this.complete=true;this.naturalWidth=0;if(this.onerror)this.onerror()}};
"""
    checks = r"""
const requestsAfterInitialDraw=imageRequests;
for(let i=0;i<20&&pending.length;i++)pending.shift()();
assert.equal(imageRequests,requestsAfterInitialDraw);
assert.equal(pending.length,0);
assert.match(element('basemapStatus').textContent,/Basemap unavailable/);
assert.equal(element('key').textContent,'a');
element('photo').onerror();
assert.equal(element('photo').hidden,true);
assert.match(element('photoStatus').textContent,/Photo unavailable/);
const initialRequests=imageRequests;
$('basemap').value='map';$('basemap').onchange();
assert.ok(imageRequests>initialRequests);
assert.ok([...tiles.keys()].some(key=>key.startsWith('satellite/')));
assert.ok([...tiles.keys()].some(key=>key.startsWith('map/')));
assert.match($('attributionSource').textContent,/OpenStreetMap/);
assert.equal($('basemapNote').hidden,true);
const satelliteRequests=imageRequests;
for(let i=0;i<40&&pending.length;i++)pending.shift()();
assert.equal(imageRequests,satelliteRequests);
assert.equal(pending.length,0);
assert.match($('basemapStatus').textContent,/Basemap unavailable/);
$('basemap').value='satellite';$('basemap').onchange();
assert.equal(imageRequests,satelliteRequests);
assert.match($('attributionSource').textContent,/Esri, Vantor/);
assert.equal($('basemapNote').hidden,false);
assert.equal(element('key').textContent,'a');
$('plotView').hidden=true;mapHits=[];
$('togglePlot').onclick();assert.equal($('plotView').hidden,false);
assert.equal($('togglePlot')['aria-expanded'],'true');assert.ok(mapHits.length>0);assert.equal($('plotView').focused,true);assert.equal($('plotView').scroll.behavior,'auto');
$('togglePlot').onclick();assert.equal($('plotView').hidden,true);
assert.equal($('togglePlot')['aria-expanded'],'false');assert.equal($('mapView').focused,true);
"""
    subprocess.run(["node", "-e", setup + script + checks], check=True)


def test_recorded_crop_geometry_and_unknown_external_footprint():
    import shutil
    import subprocess

    if not shutil.which("node"):
        pytest.skip("Node is needed to execute recorded crop geometry")
    html = module(ROOT / "dashboard/embedding_atlas_assets.py").HTML
    helpers = html.split("// CROP_HELPERS_START")[1].split("// CROP_HELPERS_END")[0]
    checks = r"""
const assert=require('node:assert/strict');
assert.deepEqual(recordedCrop({source_width:4000,source_height:3000,crop:1280}),{width:4000,height:3000,x:1360,y:860,side:1280});
assert.deepEqual(recordedCrop({source_width:2001,source_height:1501,crop:1000}),{width:2001,height:1501,x:500,y:250,side:1000});
assert.equal(recordedCrop({}),null);
assert.equal(recordedCrop({source_width:4000,source_height:3000,crop:5000}),null);
assert.equal(recordedCrop({source_width:NaN,source_height:3000,crop:1280}),null);
"""
    subprocess.run(["node", "-e", helpers + checks], check=True)


def test_comparison_requires_matching_embedding_and_label_sources(tmp_path):
    validate = module(ROOT / "dashboard/build_embedding_atlas.py").validate_comparison
    sources = [
        {"file": "embeddings_labelled/embeddings.npz", "sha256": "a"},
        {"file": "plantclef.json", "sha256": "b"},
        {"file": "gt_dominant_taxon.csv", "sha256": "c"},
    ]
    comparison = {"sources": sources, "labels_available": True}
    for embedding in sources[:2]:
        atlas = {
            "provenance": {
                "sources": [embedding, sources[2]],
                "labels": {"available": True},
            }
        }
        validate(atlas, comparison)
        for wrong in [
            {"sources": sources[1:], "labels_available": True},
            {
                "sources": [dict(s, sha256="wrong") for s in sources],
                "labels_available": True,
            },
        ]:
            if (
                embedding["file"] == "plantclef.json"
                and wrong["sources"] == sources[1:]
            ):
                continue
            with pytest.raises(ValueError, match="source"):
                validate(atlas, wrong)
    atlas = {
        "provenance": {"sources": [sources[0], dict(sources[2], sha256="new-labels")]}
    }
    with pytest.raises(ValueError, match="hash mismatch.*gt_dominant_taxon"):
        validate(atlas, comparison)


def test_export_preserves_recorded_dimensions_without_defaults(tmp_path):
    fixture_pool(tmp_path)
    cache = tmp_path / "embeddings_labelled/cache/a.json"
    cache.write_text(
        json.dumps(
            {
                "version": "test-encoder",
                "orig_width": 3001,
                "orig_height": 2001,
                "crop_size": 1111,
            }
        )
    )
    result = module(ROOT / "labelling/export_embedding_atlas.py").export(tmp_path)
    assert {
        k: result["points"][0][k] for k in ["source_width", "source_height", "crop"]
    } == {"source_width": 3001, "source_height": 2001, "crop": 1111}
    assert result["points"][1]["source_width"] is None


def test_selected_neighbor_outside_filter_stays_plotted_listed_and_locatable():
    import shutil
    import subprocess

    if not shutil.which("node"):
        pytest.skip("Node is needed to execute selection and filter behavior")
    html = module(ROOT / "dashboard/embedding_atlas_assets.py").HTML
    script = html.split("<script>")[1].split("</script>")[0]
    setup = r"""
const assert=require('node:assert/strict'),elements=new Map();
const context=new Proxy({}, {get:()=>()=>{}});
function make(){return {children:[],contains(target){return target===this||this.children.some(child=>child.contains?.(target))},clientWidth:640,clientHeight:520,value:'',style:{},focus(options){this.focused=true;this.focusOptions=options},scrollIntoView(options){this.scroll=options},getContext:()=>context,replaceChildren(...v){this.children=v},append(...v){this.children.push(...v)},removeAttribute(){},setAttribute(name,value){this[name]=value},addEventListener(){}}}
function element(id){if(!elements.has(id))elements.set(id,make());return elements.get(id)}
const payload={points:[{key:'a',label:'Species A',lat:9.1,lon:-79.8,xy:[0,0],rgb:[1,2,3],neighbours:[[1,.9]],image:'https://example.org/a.jpg',group:'Crownfirst pool'},{key:'b',label:null,lat:9.2,lon:-79.9,xy:[1,1],rgb:[3,2,1],neighbours:[[0,.9]],image:'https://example.org/b.jpg',group:'Crownfirst pool'}],provenance:{encoder:'test',versions:[],dimensions:3,projection:'PCA',input_count:2,excluded:{},sources:[]}};
element('atlas-data').textContent=JSON.stringify(payload);
global.document={getElementById:element,querySelector:()=>element('inspector'),querySelectorAll:()=>[],createElement:make};global.devicePixelRatio=1;global.location={hash:''};global.history={replaceState(){}};global.window={addEventListener(){},matchMedia:q=>({matches:q==='(prefers-reduced-motion: reduce)'})};global.requestAnimationFrame=()=>{};global.Image=class{};
"""
    checks = r"""
assert.equal($('basemap').value,'satellite');assert.deepEqual([view.x,view.y],geo[0]);assert.ok(view.scale>=256*2**17);assert.equal(visible.length,2);
$('search').value='Species A';filter();assert.deepEqual(visible,[0]);
const oldButton=$('results').children[0];document.activeElement=oldButton;select(1);assert.equal(selected,1);assert.equal($('results').children[0].focused,true);assert.deepEqual($('results').children[0].focusOptions,{preventScroll:true});assert.equal(atlasView,'photos');select(1);assert.equal(atlasView,'photos');
window.matchMedia=q=>({matches:q==='(max-width: 900px)'||q==='(prefers-reduced-motion: reduce)'});
select(0);assert.equal(atlasView,'photos');assert.equal($('photosView').scroll,undefined);
const selectionBeforeReturn=selected;$('returnToMap').onclick();assert.equal(selected,selectionBeforeReturn);assert.deepEqual($('mapView').scroll,{behavior:'auto',block:'start'});
window.matchMedia=q=>({matches:q==='(prefers-reduced-motion: reduce)'});select(1);
assert.deepEqual(visible,[0]);assert.ok(mapHits.some(p=>p[2]===1));assert.ok(plotHits.some(p=>p[2]===1));
assert.match($('results').children[0]['aria-label'],/outside current filter.*Frame b/);
assert.match($('status').textContent,/1 of 2 frames match/);
$('locate').onclick();assert.deepEqual([view.x,view.y],geo[1]);
assert.ok(mapHits.some(p=>p[2]===1&&p[0]===320&&p[1]===260));
$('search').value='no matches';filter();assert.equal(visible.length,0);assert.equal(mapHits.length,1);assert.equal(plotHits.length,1);assert.equal($('results').children.length,1);
$('search').value='';$('group').value='With recorded label';filter();assert.deepEqual(visible,[0]);
$('group').value='Without recorded label';filter();assert.deepEqual(visible,[1]);
$('reset').onclick();assert.equal(visible.length,2);assert.equal($('search').value,'');assert.ok(view.scale<256*2**17);
const modelLinks=['crownfirst-atlas.html','embedding-atlas.html'].map(href=>({href,getAttribute(){return this.href},setAttribute(name,value){this[name]=value}}));document.querySelectorAll=()=>modelLinks;
location.hash=frameHash('crown-only');readSelection();assert.equal(selected,0);assert.equal($('key').textContent,'a');assert.match($('linkStatus').textContent,/unavailable in this model/);
assert.equal(requestedFrameKey,'crown-only');assert.ok(modelLinks.every(link=>link.href.endsWith(frameHash('crown-only'))));
const returnHash=modelLinks[0].href.slice(modelLinks[0].href.indexOf('#'));assert.deepEqual(frameFromHash(returnHash,[{key:'crown-only'}]),{index:0,missing:false});
select(1);assert.equal(requestedFrameKey,null);assert.ok(modelLinks.every(link=>link.href.endsWith(frameHash('b'))));assert.equal($('linkStatus').textContent,'');
"""
    subprocess.run(["node", "-e", setup + script + checks], check=True)


def test_basemap_url_order_and_cache_identity():
    import shutil
    import subprocess

    if not shutil.which("node"):
        pytest.skip("Node is needed to execute basemap URL logic")
    html = module(ROOT / "dashboard/embedding_atlas_assets.py").HTML
    helpers = html.split("// BASEMAP_HELPERS_START")[1].split("// BASEMAP_HELPERS_END")[
        0
    ]
    checks = r"""
const assert=require('node:assert/strict');
const map=tileRequest(basemapSpec('map'),17,36465,62204),satellite=tileRequest(basemapSpec('satellite'),17,36465,62204);
assert.equal(map.url,'https://tile.openstreetmap.org/17/36465/62204.png');
assert.equal(satellite.url,'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/17/62204/36465');
assert.notEqual(map.key,satellite.key);
assert.equal(basemapSpec('unknown').id,'map');
assert.match(basemapSpec('satellite').attribution,/Esri, Vantor, Earthstar Geographics/);
"""
    subprocess.run(["node", "-e", helpers + checks], check=True)


def test_photo_first_local_navigation_and_secondary_exploration():
    from html.parser import HTMLParser

    html = module(ROOT / "dashboard/embedding_atlas_assets.py").HTML

    class Elements(HTMLParser):
        def __init__(self):
            super().__init__()
            self.tags = []

        def handle_starttag(self, tag, attrs):
            self.tags.append((tag, dict(attrs)))

    elements = Elements()
    elements.feed(html)
    by_id = {attrs["id"]: (tag, attrs) for tag, attrs in elements.tags if "id" in attrs}
    assert "hidden" in by_id["plotView"][1]
    assert by_id["togglePlot"][1]["aria-expanded"] == "false"
    assert by_id["togglePlot"][1]["aria-controls"] == "plotView"
    assert "open" not in by_id["advanced"][1]
    assert "Panama · Forest canopy explorer" in html
    assert "Barro Colorado Island" in html
    assert not any(
        attrs.get("href", "").startswith("https://wietzesuijker.github.io/what-to-id/")
        for _, attrs in elements.tags
    )
    assert "country-nav" not in html
    assert (
        html.index('id="photosView"') < html.index('id="locationsView"') < html.index('id="plotView"')
    )
    advanced = html.split('<details id="advanced">')[1].split("</details>")[0]
    assert 'id="group"' in html and "model_health_dashboard.html" in advanced
    assert 'hidden' not in by_id['photosView'][1]
    assert 'hidden' in by_id['locationsView'][1]
    assert 'hidden' in by_id['modelComparisonView'][1]
    assert by_id['showPhotosView'][1]['aria-pressed'] == 'true'


def test_similar_photo_thumbnails_are_real_lazy_safe_and_clickable():
    import shutil
    import subprocess

    if not shutil.which("node"):
        pytest.skip("Node is needed to execute similar photo rendering")
    html = module(ROOT / "dashboard/embedding_atlas_assets.py").HTML
    helpers = html.split("// SIMILAR_PHOTO_HELPERS_START")[1].split(
        "// SIMILAR_PHOTO_HELPERS_END"
    )[0]
    checks = r"""
const assert=require('node:assert/strict');
const document={createElement:tag=>({tag,children:[],setAttribute(n,v){this[n]=v},append(...v){this.children.push(...v)}})};
let chosen=false;const image='https://example.org/original.JPG';
const button=similarPhotoButton({key:'comb_DJI_a.JPG',label:'Species A',image},.91234,()=>chosen=true);
const thumbnail=button.children[0];assert.equal(thumbnail.tag,'img');assert.equal(thumbnail.src,image);assert.equal(thumbnail.loading,'lazy');assert.equal(thumbnail.decoding,'async');assert.equal(thumbnail.alt,'');assert.equal(thumbnail.width,64);assert.equal(thumbnail.height,48);
assert.match(button['aria-label'],/Species A.*comb_DJI_a.JPG.*0.912/);
thumbnail.onerror();assert.equal(thumbnail.hidden,true);button.onclick();assert.equal(chosen,true);
const unknown=similarPhotoButton({key:'b',image:'javascript:alert(1)'},.2,()=>{});
assert.equal(unknown.children.length,1);assert.equal(unknown.children[0].children[0].textContent,'No recorded frame label');
"""
    subprocess.run(["node", "-e", helpers + checks], check=True)


def test_selecting_offscreen_photo_recenters_without_changing_zoom():
    import shutil
    import subprocess

    if not shutil.which("node"):
        pytest.skip("Node is needed to execute conditional selection centering")
    html = module(ROOT / "dashboard/embedding_atlas_assets.py").HTML
    helpers = html.split("// MAP_HELPERS_START")[1].split("// MAP_HELPERS_END")[0]
    checks = r"""
const assert=require('node:assert/strict'),v={x:.5,y:.5,scale:1000};
assert.equal(selectionView(v,[.6,.6],640,520),v);
assert.equal(selectionView(v,[.796,.5],640,520),v);
assert.deepEqual(selectionView(v,[.797,.5],640,520),{x:.797,y:.5,scale:1000});
assert.deepEqual(selectionView(v,[.5,.8],640,520),{x:.5,y:.8,scale:1000});
"""
    subprocess.run(["node", "-e", helpers + checks], check=True)


def test_primary_photo_pair_is_large_with_secondary_metadata_collapsed():
    from html.parser import HTMLParser

    html = module(ROOT / "dashboard/embedding_atlas_assets.py").HTML

    class Elements(HTMLParser):
        def __init__(self):
            super().__init__()
            self.tags = []

        def handle_starttag(self, tag, attrs):
            self.tags.append((tag, dict(attrs)))

    elements = Elements()
    elements.feed(html)
    by_id = {attrs["id"]: (tag, attrs) for tag, attrs in elements.tags if "id" in attrs}
    assert "hidden" not in by_id["photosView"][1]
    assert "hidden" in by_id["locationsView"][1]
    for identifier in ["photoDetails", "browsePhotos"]:
        assert "open" not in by_id[identifier][1]
    details = html.split('id="photoDetails"')[1].split("</details>")[0]
    assert all('id="' + identifier + '"' in details for identifier in ["key", "detail", "cropCaption"])
    css = html.split("<style>")[1].split("</style>")[0]
    assert ".primary-pair{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr)" in css
    assert "height:clamp(360px,42vh,560px)" in css
    assert ".primary-pair{display:flex;flex-direction:column" in css
    assert "object-fit:contain" in css
    assert "aside{" not in css


def test_photo_comparison_preserves_query_until_explicit_selection():
    import shutil
    import subprocess

    if not shutil.which("node"):
        pytest.skip("Node is needed to execute photo comparison state")
    html = module(ROOT / "dashboard/embedding_atlas_assets.py").HTML
    script = html.split("<script>")[1].split("</script>")[0]
    setup = r"""
const assert=require('node:assert/strict'),elements=new Map();
const context=new Proxy({}, {get:()=>()=>{}});
function make(){return {children:[],attributes:{},isConnected:true,clientWidth:640,clientHeight:520,value:'',style:{},contains(target){return target===this||this.children.some(child=>child.contains?.(target))},focus(){document.activeElement=this},scrollIntoView(){},getContext:()=>context,replaceChildren(...v){this.children=v},append(...v){this.children.push(...v)},getAttribute(name){return this.attributes[name]??null},removeAttribute(name){delete this[name];delete this.attributes[name]},setAttribute(name,value){this[name]=value;this.attributes[name]=value},addEventListener(){},showModal(){this.open=true},close(){this.open=false;this.onclose?.()}}}
function element(id){if(!elements.has(id)){const node=make();if(id.endsWith('Overlay'))node.attributes.hidden='';elements.set(id,node)}return elements.get(id)}
const shared={lat:9.1,lon:-79.8,xy:[0,0],rgb:[1,2,3],group:'pool'};
const payload={points:[{...shared,key:'a',label:'Luehea seemannii',mission:'flight-a',image:'https://example.org/a.jpg',source_width:4000,source_height:3000,crop:1280,neighbours:[[1,.9],[2,.8]]},{...shared,key:'b',label:'Luehea',mission:'flight-b',image:'https://example.org/b.jpg',neighbours:[[0,.9]]},{...shared,key:'c',image:'javascript:alert(1)',neighbours:[]}],provenance:{labels:{available:true},encoder:'test',versions:[],dimensions:3,projection:'PCA',input_count:3,excluded:{},sources:[]}};
element('atlas-data').textContent=JSON.stringify(payload);
global.document={getElementById:element,querySelector:()=>element('inspector'),querySelectorAll:()=>[],createElement:make};
global.devicePixelRatio=1;global.location={hash:'#frame=a'};global.history={replaceState(_,__,hash){location.hash=hash}};global.window={addEventListener(){},matchMedia:()=>({matches:false})};global.requestAnimationFrame=()=>{};global.Image=class{};
"""
    checks = r"""
const opener=$('workspaceEnlarge'),queryImage=$('photo').src,queryNeighbors=$('neighbors').children,queryView={...view};
opener.focus();opener.onclick();
assert.equal($('photoComparison').open,true);assert.equal(selected,0);assert.equal(location.hash,'#frame=a');
assert.equal($('photo').src,queryImage);assert.equal($('neighbors').children,queryNeighbors);assert.deepEqual(view,queryView);
assert.equal($('comparisonQueryImage').src,'https://example.org/a.jpg');assert.equal($('comparisonCandidateImage').src,'https://example.org/b.jpg');
assert.match($('comparisonQueryLabel').textContent,/Luehea seemannii/);assert.match($('comparisonCandidateLabel').textContent,/Recorded frame label: Luehea$/);
assert.match($('comparisonCandidateKey').textContent,/flight-b/);assert.match($('photoComparisonScore').textContent,/not identification probability/);
assert.match($('comparisonCandidateCrop').textContent,/unknown/);$('comparisonQueryImage').naturalWidth=4000;$('comparisonQueryImage').naturalHeight=3000;$('comparisonQueryImage').onload();assert.equal($('comparisonQueryOverlay').getAttribute('hidden'),null);
assert.equal($('previousComparison').disabled,true);assert.equal($('nextComparison').disabled,false);
$('nextComparison').onclick();assert.equal(selected,0);assert.equal(location.hash,'#frame=a');assert.equal($('nextComparison').disabled,true);
assert.equal($('comparisonCandidateImage').src,undefined);assert.equal($('comparisonCandidateOriginal').href,undefined);assert.equal($('comparisonCandidateOriginal').hidden,true);
assert.match($('comparisonCandidateStatus').textContent,/unavailable/);assert.match($('comparisonCandidateLabel').textContent,/No recorded frame label/);
$('nextComparison').onclick();assert.match($('photoComparisonRank').textContent,/Candidate 2 of 2/);
$('previousComparison').onclick();$('comparisonCandidateImage').onerror();assert.equal($('comparisonCandidateImage').hidden,true);assert.match($('comparisonCandidateStatus').textContent,/unavailable/);
$('closePhotoComparison').onclick();assert.equal(selected,0);assert.equal(location.hash,'#frame=a');assert.equal(document.activeElement,opener);assert.equal(photoComparison,null);
opener.onclick();$('chooseComparison').onclick();assert.equal(selected,1);assert.equal(location.hash,'#frame=b');assert.equal($('photoComparison').open,false);assert.equal(photoComparison,null);
select(2);$('inspectPhoto').onclick();assert.equal($('comparisonCandidate').hidden,true);assert.equal($('photoComparisonActions').hidden,true);assert.match($('comparisonQueryStatus').textContent,/unavailable/);assert.equal(selected,2);
$('closePhotoComparison').onclick();assert.equal(document.activeElement,$('inspectPhoto'));assert.equal(openPhotoComparison(0),false);
assert.deepEqual(storedPhotoCandidates([{neighbours:[[1,.9],[0,.8],[8,.7],[1,NaN]]},{}],0),[[1,.9]]);
"""
    subprocess.run(["node", "-e", setup + script + checks], check=True)


def test_photo_browser_reaches_all_matches_with_pinned_selection_and_stable_focus():
    import shutil
    import subprocess

    if not shutil.which("node"):
        pytest.skip("Node is needed to execute photo browser state")
    html = module(ROOT / "dashboard/embedding_atlas_assets.py").HTML
    script = html.split("<script>")[1].split("</script>")[0]
    setup = r"""
const assert=require('node:assert/strict'),elements=new Map();
const context=new Proxy({}, {get:()=>()=>{}});
function make(){return {children:[],attributes:{},clientWidth:640,clientHeight:520,value:'',style:{},contains(target){return target===this||this.children.some(child=>child.contains?.(target))},focus(options){document.activeElement=this;this.focusOptions=options},scrollIntoView(){this.scrollCalls=(this.scrollCalls||0)+1},getContext:()=>context,replaceChildren(...v){this.children=v},append(...v){this.children.push(...v)},removeAttribute(name){delete this[name]},setAttribute(name,value){this[name]=value;this.attributes[name]=value},addEventListener(){}}}
function element(id){if(!elements.has(id))elements.set(id,make());return elements.get(id)}
const points=Array.from({length:207},(_,i)=>({key:'frame-'+String(i).padStart(3,'0'),label:i%2===0?'Fabaceae':null,mission:'flight',image:'https://example.org/'+i+'.jpg',lat:9.1,lon:-79.8,xy:[0,0],rgb:[1,2,3],group:'pool',neighbours:[]}));
const payload={points,provenance:{labels:{available:true},encoder:'test',versions:[],dimensions:3,projection:'PCA',input_count:points.length,excluded:{},sources:[]}};
element('atlas-data').textContent=JSON.stringify(payload);
global.document={getElementById:element,querySelector:()=>element('inspector'),querySelectorAll:()=>[],createElement:make};global.devicePixelRatio=1;global.location={hash:'#frame=frame-000'};global.history={replaceState(_,__,hash){location.hash=hash}};global.window={addEventListener(){},matchMedia:()=>({matches:false})};global.requestAnimationFrame=()=>{};global.Image=class{};
"""
    checks = r"""
assert.equal($('browsePhotos').open,undefined);assert.equal($('results').children.length,51);
const initialView={...view},initialHash=location.hash,seen=new Set();
function recordPage(){const rows=$('results').children;assert.ok(rows.length<=51);assert.equal(rows.filter(row=>row['aria-pressed']==='true').length,1);assert.equal(rows[0]['data-frame'],'frame-000');assert.equal(new Set(rows.map(row=>row['data-frame'])).size,rows.length);for(const row of rows)seen.add(row['data-frame'])}
recordPage();assert.equal($('previousBrowsePage').disabled,true);moveBrowsePage(-1);assert.equal(browsePage,0);
$('showBrowsePhotos').onclick();assert.equal($('browsePhotos').open,true);assert.equal(document.activeElement,$('browsePhotosSummary'));assert.equal($('browsePhotosSummary').scrollCalls,1);
while(!$('nextBrowsePage').disabled){$('nextBrowsePage').focus();$('nextBrowsePage').onclick();recordPage();assert.equal(selected,0);assert.equal(location.hash,initialHash);assert.deepEqual(view,initialView)}
assert.equal(seen.size,207);assert.ok(seen.has('frame-206'));assert.match($('browseRange').textContent,/201 to 206 of 206.*Page 5 of 5/);assert.equal(document.activeElement,$('browseRange'));assert.deepEqual($('browseRange').focusOptions,{preventScroll:true});moveBrowsePage(1);assert.equal(browsePage,4);
while(!$('previousBrowsePage').disabled){$('previousBrowsePage').focus();$('previousBrowsePage').onclick()}
assert.equal(browsePage,0);assert.equal(document.activeElement,$('browseRange'));
const thumbnail=$('results').children[0].children[0].children[0];assert.equal(thumbnail.src,'https://example.org/0.jpg');assert.equal(thumbnail.loading,'lazy');assert.equal(thumbnail.alt,'');thumbnail.onerror();assert.equal(thumbnail.hidden,true);
$('browsePhotos').open=false;$('browsePhotos').ontoggle();assert.equal($('showBrowsePhotos')['aria-expanded'],'false');
$('search').focus();$('search').value='frame-206';$('search').oninput();assert.equal($('browsePhotos').open,true);assert.equal(document.activeElement,$('search'));assert.equal($('browsePhotosSummary').scrollCalls,1);assert.equal(selected,0);assert.deepEqual(visible,[206]);assert.equal($('results').children.length,2);assert.equal($('previousBrowsePage').disabled,true);assert.equal($('nextBrowsePage').disabled,true);assert.match($('browseCount').textContent,/1 of 207 photos match.*outside these matches/);assert.match($('browseRange').textContent,/Matches 1 to 1 of 1/);
$('results').children[1].onclick();assert.equal(selected,206);assert.equal(location.hash,'#frame=frame-206');assert.equal($('results').children.length,1);assert.equal($('results').children[0]['data-frame'],'frame-206');assert.match($('browseRange').textContent,/Only the selected photo matches/);
$('search').focus();$('search').value='no-matches';$('search').oninput();assert.equal(visible.length,0);assert.equal(selected,206);assert.equal($('results').children.length,1);assert.equal($('browseEmpty').hidden,false);assert.match($('browseRange').textContent,/No matching photos/);assert.equal(document.activeElement,$('search'));assert.equal($('nextBrowsePage').disabled,true);
$('search').value='';$('group').value='Without recorded label';$('group').focus();$('group').onchange();assert.equal(visible.length,103);assert.equal(document.activeElement,$('group'));assert.equal(browsePage,0);assert.match($('selectionStatus').textContent,/outside the current filter/);
$('reset').onclick();assert.equal(visible.length,207);assert.equal(browsePage,0);assert.equal(selected,206);assert.equal($('search').value,'');assert.equal($('group').value,'All frames');assert.equal($('browseEmpty').hidden,true);assert.equal($('results').children[0]['data-frame'],'frame-206');assert.match($('browseCount').textContent,/207 of 207 photos match/);assert.equal($('nextBrowsePage').disabled,false);
const unavailable=browsePhotoButton({key:'unsafe',image:'javascript:alert(1)'},false,false,()=>{});assert.equal(unavailable.children[0].children[0].textContent,'Photo unavailable');
assert.match(unavailable['aria-label'],/Recorded frame labels unavailable/);
const noLabel=browsePhotoButton({key:'known-source'},false,false,()=>{},true);assert.match(noLabel['aria-label'],/No recorded frame label/);
"""
    subprocess.run(["node", "-e", setup + script + checks], check=True)
