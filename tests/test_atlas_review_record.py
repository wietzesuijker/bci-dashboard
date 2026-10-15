"""Local review handoffs preserve modal identity and recorded evidence boundaries."""

from pathlib import Path
import json
import runpy
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def atlas_html():
    return runpy.run_path(ROOT / "dashboard/embedding_atlas_assets.py")["HTML"]


def run_node(script):
    if not shutil.which("node"):
        pytest.skip("Node is needed to execute review record behavior")
    subprocess.run(["node", "-e", script], check=True)


def test_pure_review_record_uses_modal_identity_and_preserves_recorded_provenance():
    html = atlas_html()
    helpers = "\n".join(
        html.split("// " + marker + "_START")[1].split("// " + marker + "_END")[0]
        for marker in ["CROP_HELPERS", "SIMILAR_PHOTO_HELPERS", "MISSION_VIEW_HELPERS", "REVIEW_RECORD_HELPERS"]
    )
    run_node(helpers + r"""
const assert=require('node:assert/strict');
const atlas={points:[{key:'irrelevant-selection',mission:'flight-a',vector:['never export raw vectors']},{key:'query ä & /?.JPG',label:'Fabaceae',mission:' flight-b ',image:'https://example.org/query.jpg',version:'recorded-v1',source_width:4000,source_height:3000,crop:1280,other_mission_neighbours:[[2,.81234],[3,.76543]]},{key:'candidate',label:'Luehea',mission:'flight-c',image:'https://example.org/candidate.jpg',version:'recorded-v2',crop:1280},{key:'unknown',mission:null,image:'javascript:alert(1)'}],provenance:{encoder:'actual-page-encoder',versions:['recorded-v1','recorded-v2'],dimensions:1024,sources:[{file:'frozen.npz',sha256:'abc',details:{kind:'embedding'}}]}};
Object.defineProperty(atlas,'comparison',{get(){throw new Error('Shared-cohort comparison must not be read')}});
const state={query:1,candidates:[[2,.81234],[3,.76543]],rank:0,mode:'other'},note='观察 <img src=x onerror=alert(1)>\nSecond line 🌳',clock='2026-10-16T04:01:02.003Z';
const record=reviewRecord(atlas,state,'https://example.org/crownfirst-atlas.html?cached=1#frame=wrong',clock,note);
assert.equal(record.schema_version,1);assert.equal(record.purpose,'visual_review_handoff');assert.equal(record.exported_at_utc,clock);assert.match(record.scope,/Single-model.*not the shared-cohort/);
assert.deepEqual(record.atlas,{page_url:'https://example.org/crownfirst-atlas.html?cached=1',encoder:'actual-page-encoder',encoder_identity:null,versions:['recorded-v1','recorded-v2'],dimensions:1024,pool_size:4,sources:atlas.provenance.sources});
assert.deepEqual(record.relationship,{method:'cosine_on_l2_normalized_full_vectors',mode:'other',eligible_pool_support:2,score:.81234,rank_1_based:1,stored_candidate_count:2});
assert.equal(record.query.key,'query ä & /?.JPG');assert.equal(record.candidate.key,'candidate');assert.equal(record.query.recorded_taxon,'Fabaceae');assert.equal(record.candidate.recorded_taxon,'Luehea');assert.equal(record.query.mission,' flight-b ');assert.equal(record.query.version,'recorded-v1');assert.equal(record.candidate.version,'recorded-v2');assert.equal(record.query.image_url,'https://example.org/query.jpg');
assert.deepEqual(record.query.crop_geometry,{width:4000,height:3000,x:1360,y:860,side:1280,source_encoder:'actual-page-encoder'});assert.equal(record.candidate.crop_geometry,null);assert.deepEqual(record.candidate.crop_record,{size_px:1280,source_width_px:null,source_height_px:null,source_encoder:'actual-page-encoder'});
for(const frame of [record.query,record.candidate]){const link=new URL(frame.reopen_url);assert.equal(link.pathname,'/crownfirst-atlas.html');assert.equal(link.search,'?cached=1');assert.equal(new URLSearchParams(link.hash.slice(1)).get('frame'),frame.key)}
assert.deepEqual(record.review_note,{text:note,verified:false});assert.equal(JSON.parse(JSON.stringify(record)).review_note.text,note);assert.match(record.limitations.join(' '),/not an identification probability.*independent trees.*species, genus or family.*not a computational reproducibility package.*do not restore this pair/);
const serialized=JSON.stringify(record);assert.ok(!serialized.includes('never export raw vectors'));assert.ok(!serialized.includes('reviewer'));assert.ok(!serialized.includes('status'));
atlas.provenance.sources[0].sha256='changed';atlas.provenance.sources[0].details.kind='changed';atlas.provenance.versions.push('changed');state.candidates[0][1]=.1;assert.equal(record.atlas.sources[0].sha256,'abc');assert.equal(record.atlas.sources[0].details.kind,'embedding');assert.deepEqual(record.atlas.versions,['recorded-v1','recorded-v2']);assert.equal(record.relationship.score,.81234);
const only=reviewRecord(atlas,{query:3,rank:null,mode:'all'},'https://example.org/embedding-atlas.html#frame=wrong',clock,'');assert.equal(only.candidate,null);assert.equal(only.relationship,null);assert.equal(only.query.key,'unknown');assert.equal(only.query.recorded_taxon,null);assert.equal(only.query.mission,null);assert.equal(only.query.image_url,null);assert.equal(only.query.crop_geometry,null);assert.equal(only.query.version,null);
const all=reviewRecord(atlas,{query:1,candidates:[[2,.81234]],rank:0,mode:'all'},'https://example.org/embedding-atlas.html',clock);assert.equal(all.relationship.eligible_pool_support,3);
assert.throws(()=>reviewRecord(atlas,null,'https://example.org/',clock),/No photo/);assert.throws(()=>reviewRecord(atlas,{...state,rank:9},'https://example.org/',clock),/No valid candidate/);assert.throws(()=>reviewRecord(atlas,{...state,mode:'unsupported'},'https://example.org/',clock),/Unknown similar-photo view/);
""")


def test_review_record_copies_identity_and_preserves_unknown_external_versions():
    html = atlas_html()
    helpers = "\n".join(
        html.split("// " + marker + "_START")[1].split("// " + marker + "_END")[0]
        for marker in ["CROP_HELPERS", "SIMILAR_PHOTO_HELPERS", "MISSION_VIEW_HELPERS", "REVIEW_RECORD_HELPERS"]
    )
    run_node(helpers + r"""
const assert=require('node:assert/strict');
const external={points:[{key:'query',version:null}],provenance:{encoder:'Supplied display name',versions:[],encoder_identity:{name_basis:'supplied_at_import',version_source:'not_recorded'}}};
const state={query:0,rank:null,mode:'all'},clock='2026-10-16T04:01:02.003Z';
const record=reviewRecord(external,state,'https://example.org/atlas.html',clock);
assert.deepEqual(record.atlas.encoder_identity,{name_basis:'supplied_at_import',version_source:'not_recorded'});assert.notEqual(record.atlas.encoder_identity,external.provenance.encoder_identity);assert.deepEqual(record.atlas.versions,[]);assert.equal(record.query.version,null);
external.provenance.encoder_identity.name_basis='mutated';assert.equal(record.atlas.encoder_identity.name_basis,'supplied_at_import');
external.provenance.encoder_identity={name_basis:'endpoint_label',version_source:'cached_response',details:{source:'response'}};external.provenance.versions=['actual-api-version'];external.points[0].version='actual-api-version';
const api=reviewRecord(external,state,'https://example.org/atlas.html',clock);external.provenance.encoder_identity.details.source='mutated';assert.equal(api.atlas.encoder_identity.details.source,'response');assert.equal(api.atlas.encoder_identity.version_source,'cached_response');assert.deepEqual(api.atlas.versions,['actual-api-version']);assert.equal(api.query.version,'actual-api-version');
delete external.provenance.encoder_identity;const legacy=reviewRecord(external,state,'https://example.org/crownfirst-atlas.html',clock);assert.equal(legacy.atlas.encoder_identity,null);assert.deepEqual(legacy.atlas.versions,['actual-api-version']);assert.equal(legacy.query.version,'actual-api-version');
""")


def test_model_version_context_reports_basis_without_name_inference():
    from test_atlas_mission_view import photo, run_atlas

    helpers = atlas_html().split("// ENCODER_IDENTITY_HELPERS_START")[1].split("// ENCODER_IDENTITY_HELPERS_END")[0]
    run_node(helpers + r"""
const assert=require('node:assert/strict');
const external={encoder:'Supplied display name',versions:[],encoder_identity:{name_basis:'supplied_at_import',version_source:'not_recorded'}};
assert.equal(encoderVersionStatus(external),'Model version not recorded');assert.match(encoderIdentityNote(external),/Display name provided at import.*SHA-256 identifies the vector file.*does not record a checkpoint or preprocessing run/);
const api={encoder:'Endpoint label',versions:['recorded-v7'],encoder_identity:{name_basis:'endpoint_label',version_source:'cached_response'}};
assert.equal(encoderVersionStatus(api),'Cached API version: recorded-v7');assert.match(encoderIdentityNote(api),/endpoint label.*cached responses.*do not establish checkpoint weights or a complete preprocessing run/);
for(const encoder of ['Crownfirst','Pl@ntNet /v2/embeddings','arbitrary display name']){const legacy={encoder,versions:['legacy-v1']};assert.equal(encoderVersionStatus(legacy),'Version metadata: legacy-v1');assert.match(encoderIdentityNote(legacy),/basis are not recorded/);assert.equal(encoderVersionStatus({...legacy,versions:[]}),'Model version not recorded in this atlas');}
""")
    run_atlas([photo("query", "flight-a")], r"""
assert.match($('similarModel').textContent,/Model version not recorded in this atlas/);assert.match($('provenance').textContent,/Model name and version basis are not recorded/);assert.ok(!$('provenance').textContent.includes(', ,'));
data.provenance.encoder='Supplied display name';data.provenance.versions=[];data.provenance.encoder_identity={name_basis:'supplied_at_import',version_source:'not_recorded'};renderSimilarPhotos();assert.equal($('similarModel').textContent,'Model: Supplied display name · Model version not recorded');$('inspectPhoto').onclick();assert.match($('photoComparisonContext').textContent,/Supplied display name · Model version not recorded/);$('closePhotoComparison').onclick();
data.provenance.encoder='Endpoint label';data.provenance.versions=['recorded-v7'];data.provenance.encoder_identity={name_basis:'endpoint_label',version_source:'cached_response'};renderSimilarPhotos();assert.equal($('similarModel').textContent,'Model: Endpoint label · Cached API version: recorded-v7');$('inspectPhoto').onclick();assert.match($('photoComparisonContext').textContent,/Cached API version: recorded-v7/);$('closePhotoComparison').onclick();
""")


@pytest.mark.parametrize(
    "identity,version_status,basis_note",
    [
        (None, "Version metadata: actual-v1", "Model name and version basis are not recorded"),
        (
            {"name_basis": "supplied_at_import", "version_source": "not_recorded"},
            "Model version not recorded",
            "Display name provided at import",
        ),
        (
            {"name_basis": "endpoint_label", "version_source": "cached_response"},
            "Cached API version: actual-v1",
            "Model name is the endpoint label; versions come from cached responses",
        ),
    ],
)
def test_dialog_notes_follow_the_pair_and_download_releases_blob_url(identity, version_status, basis_note):
    script = atlas_html().split("<script>")[1].split("</script>")[0]
    setup = r"""
const assert=require('node:assert/strict'),elements=new Map(),timers=[],revoked=[],downloads=[];let latestBlob;
const context=new Proxy({}, {get:()=>()=>{}});
function make(){return {children:[],attributes:{},isConnected:true,clientWidth:640,clientHeight:520,value:'',style:{},contains(target){return target===this||this.children.some(child=>child.contains?.(target))},focus(){document.activeElement=this},scrollIntoView(){},getContext:()=>context,replaceChildren(...v){this.children=v},append(...v){this.children.push(...v)},getAttribute(name){return this.attributes[name]??null},removeAttribute(name){delete this[name]},setAttribute(name,value){this[name]=value;this.attributes[name]=value},addEventListener(){},showModal(){this.open=true},close(){this.open=false;this.onclose?.()},click(){downloads.push({href:this.href,filename:this.download,node:this})},remove(){this.removed=true}}}
function element(id){if(!elements.has(id))elements.set(id,make());return elements.get(id)}
const shared={lat:9.1,lon:-79.8,xy:[0,0],rgb:[1,2,3],group:'pool',mission:'flight-a',version:'actual-v1'};
const payload={points:[{...shared,key:'query',image:'https://example.org/a.jpg',neighbours:[[1,.91234],[2,.82345]],other_mission_neighbours:[[2,.82345]]},{...shared,key:'same',neighbours:[[0,.91234]],image:'https://example.org/b.jpg'},{...shared,key:'other',mission:'flight-b',neighbours:[[0,.82345]],image:'https://example.org/c.jpg'}],provenance:{encoder:'actual-encoder',versions:['actual-v1'],dimensions:3,projection:'PCA',input_count:3,excluded:{},sources:[{file:'actual.npz',sha256:'abc'}]}};
const identity=__IDENTITY__;if(identity)payload.provenance.encoder_identity=identity;if(identity?.version_source==='not_recorded'){payload.provenance.versions=[];for(const point of payload.points)point.version=null}
element('atlas-data').textContent=JSON.stringify(payload);
global.document={body:make(),getElementById:element,querySelector:()=>element('inspector'),querySelectorAll:()=>[],createElement:make};global.devicePixelRatio=1;global.location={hash:'#frame=query',href:'https://example.org/crownfirst-atlas.html#frame=query'};global.history={replaceState(_,__,hash){location.hash=hash}};global.window={addEventListener(){},matchMedia:()=>({matches:false})};global.requestAnimationFrame=()=>{};global.Image=class{};
URL.createObjectURL=blob=>{latestBlob=blob;return 'blob:local-review'};URL.revokeObjectURL=url=>revoked.push(url);global.setTimeout=(fn,delay)=>timers.push({fn,delay});global.fetch=()=>{throw new Error('No network during review export')};Object.defineProperty(global,'localStorage',{get(){throw new Error('Notes must not persist to local storage')}});
""".replace("__IDENTITY__", json.dumps(identity))
    rendered_checks = (
        "assert.ok($('similarModel').textContent.includes(" + json.dumps(version_status) + "));"
        "assert.ok($('provenance').textContent.includes(" + json.dumps(version_status) + "));"
        "assert.ok($('provenance').textContent.includes(" + json.dumps(basis_note) + "));"
        "assert.ok(!$('provenance').textContent.includes(', ,'));"
    )
    checks = r"""
(async()=>{
const opener=$('workspaceEnlarge');opener.focus();opener.onclick();assert.equal($('reviewNote').value,'');assert.match($('photoComparisonScore').textContent,/0.912/);assert.doesNotMatch($('photoComparisonScore').textContent,/0.91234/);
const firstNote='First pair 🌳\n<img src=x onerror=alert(1)>';$('reviewNote').value=firstNote;$('reviewNote').oninput();$('nextComparison').onclick();assert.equal($('reviewNote').value,'');$('reviewNote').value='Second pair';$('previousComparison').onclick();assert.equal($('reviewNote').value,firstNote);$('nextComparison').onclick();assert.equal($('reviewNote').value,'Second pair');
selected=1;neighborMode='other';data.comparison={frames:['wrong shared-cohort data'],sources:[{file:'wrong.npz'}]};$('downloadReviewRecord').onclick();
assert.equal(downloads.length,1);assert.equal(downloads[0].href,'blob:local-review');assert.match(downloads[0].filename,/^canopy-review-.*\.json$/);assert.equal(downloads[0].node.removed,true);assert.equal(latestBlob.type,'application/json;charset=utf-8');const exported=JSON.parse(await latestBlob.text());
assert.equal(exported.query.key,'query');assert.equal(exported.candidate.key,'other');assert.equal(exported.relationship.mode,'all');assert.equal(exported.relationship.rank_1_based,2);assert.equal(exported.relationship.score,.82345);assert.equal(exported.relationship.stored_candidate_count,2);assert.equal(exported.relationship.eligible_pool_support,2);assert.equal(exported.atlas.encoder,'actual-encoder');assert.equal(exported.atlas.sources[0].file,'actual.npz');assert.equal(exported.review_note.text,'Second pair');assert.match($('photoComparisonScore').textContent,/0.823/);assert.doesNotMatch($('photoComparisonScore').textContent,/0.82345/);assert.equal(location.hash,'#frame=query');
assert.equal(revoked.length,0);assert.equal(timers.length,1);timers.shift().fn();assert.deepEqual(revoked,['blob:local-review']);assert.match($('reviewDownloadStatus').textContent,/prepared for download.*Labels unchanged/);
photoComparison.mode='other';renderPhotoComparison();assert.equal($('reviewNote').value,'');$('reviewNote').value='Other-mode note';$('reviewNote').oninput();photoComparison.mode='all';renderPhotoComparison();assert.equal($('reviewNote').value,'Second pair');
$('closePhotoComparison').onclick();assert.equal(document.activeElement,opener);selected=0;neighborMode='all';opener.onclick();assert.equal($('reviewNote').value,'Second pair');$('closePhotoComparison').onclick();setWorkspaceCandidate(0);opener.onclick();assert.equal($('reviewNote').value,firstNote);$('closePhotoComparison').onclick();
$('inspectPhoto').onclick();$('reviewNote').value='Query only';$('downloadReviewRecord').onclick();const queryOnly=JSON.parse(await latestBlob.text());assert.equal(queryOnly.candidate,null);assert.equal(queryOnly.relationship,null);assert.equal(queryOnly.review_note.text,'Query only');timers.shift().fn();$('closePhotoComparison').onclick();
const before=downloads.length;$('downloadReviewRecord').onclick();assert.equal(downloads.length,before);
$('inspectPhoto').onclick();const originalCreate=document.createElement;document.createElement=()=>{throw new Error('Cannot create a download link')};$('downloadReviewRecord').onclick();assert.match($('reviewDownloadStatus').textContent,/Could not prepare/);assert.equal(timers.length,1);timers.shift().fn();assert.equal(revoked.length,3);document.createElement=originalCreate;$('closePhotoComparison').onclick();
delete data.comparison;openPhotoComparison(0);assert.equal($('reviewNote').value,firstNote);$('reviewNote').value='Undownloaded selection note';$('chooseComparison').onclick();assert.equal(selected,1);select(0);openPhotoComparison(0);assert.equal($('reviewNote').value,'Undownloaded selection note');$('reviewNote').value='Undownloaded Escape note';$('photoComparison').close();openPhotoComparison(0);assert.equal($('reviewNote').value,'Undownloaded Escape note');$('closePhotoComparison').onclick();
$('inspectPhoto').onclick();assert.equal($('reviewNote').value,'Query only');$('closePhotoComparison').onclick();neighborMode='other';openPhotoComparison(0);assert.equal($('reviewNote').value,'Other-mode note');$('closePhotoComparison').onclick();
})().catch(error=>{console.error(error);process.exitCode=1});
"""
    run_node(setup + script + rendered_checks + checks)
