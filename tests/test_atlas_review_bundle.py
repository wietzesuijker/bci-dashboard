"""One local handoff preserves every noted Photos context without shared-model data."""

from pathlib import Path
import runpy

from test_atlas_mission_view import photo, run_atlas
from test_atlas_review_record import run_node

ROOT = Path(__file__).resolve().parents[1]


def test_review_bundle_resolves_original_rankings_and_exact_note_text():
    html = runpy.run_path(ROOT / "dashboard/embedding_atlas_assets.py")["HTML"]
    helpers = "\n".join(
        html.split("// " + marker + "_START")[1].split("// " + marker + "_END")[0]
        for marker in ["CROP_HELPERS", "SIMILAR_PHOTO_HELPERS", "PHOTO_COMPARISON_HELPERS", "MISSION_VIEW_HELPERS", "REVIEW_RECORD_HELPERS", "REVIEW_BUNDLE_HELPERS"]
    )
    run_node(helpers + r"""
const assert=require('node:assert/strict');
const atlas={points:[{key:'query',label:'Fabaceae',mission:' flight-a ',version:null,image:'https://example.org/q.jpg',neighbours:[[1,.91234],[2,.82345]],other_mission_neighbours:[[2,.82345]],source_width:4000,source_height:3000,crop:1280,vector:['never include raw vectors']},{key:'same',mission:'flight-a',version:null,neighbours:[[0,.91234],[3,.73456]],other_mission_neighbours:[[3,.73456]]},{key:'other',mission:'flight-b',version:null,neighbours:[[0,.82345]],other_mission_neighbours:[[0,.82345]]},{key:'another',mission:'flight-c',crop:1280,neighbours:[[1,.73456]],other_mission_neighbours:[[1,.73456]]}],provenance:{encoder:'Frozen supplied encoder',encoder_identity:{name_basis:'supplied_at_import',version_source:'not_recorded'},versions:[],dimensions:768,sources:[{file:'frozen-vectors.json',sha256:'frozen-sha'}]}};
Object.defineProperty(atlas,'comparison',{get(){throw new Error('Never read shared-cohort comparison')}});
const notes=new Map([['[0,1,"all"]','  First pair 🌳\n<img src=x onerror=alert(1)>  '],['[0,2,"all"]','Second pair'],['[0,2,"other"]','Other missions'],['[1,3,"all"]','Another query'],['[0,null,"all"]','Query only, all'],['[0,null,"other"]','Query only, other'],['[2,0,"all"]',' \t\n '],['not valid JSON','']]);
const clock='2026-10-16T04:31:02.003Z',bundle=reviewNoteBundle(atlas,notes,'https://example.org/crownfirst-atlas.html#frame=distractor',clock);
assert.equal(bundle.schema_version,1);assert.equal(bundle.purpose,'visual_review_handoff_collection');assert.equal(bundle.record_count,6);assert.equal(bundle.records.length,6);assert.equal(bundle.exported_at_utc,clock);assert.match(bundle.scope,/Photos notes only.*shared-cohort.*excluded.*unverified.*do not update labels/);
const byContext=new Map(bundle.records.map(record=>[JSON.stringify([record.query.key,record.candidate?.key??null,record.photos_mission_mode]),record]));assert.equal(byContext.size,6);
const first=byContext.get('["query","same","all"]'),second=byContext.get('["query","other","all"]'),other=byContext.get('["query","other","other"]'),another=byContext.get('["same","another","all"]');
assert.equal(first.review_note.text,notes.get('[0,1,"all"]'));assert.equal(JSON.parse(JSON.stringify(first)).review_note.text,notes.get('[0,1,"all"]'));assert.equal(first.relationship.score,.91234);assert.equal(first.relationship.rank_1_based,1);assert.equal(second.relationship.score,.82345);assert.equal(second.relationship.rank_1_based,2);assert.equal(second.relationship.stored_candidate_count,2);assert.equal(second.relationship.eligible_pool_support,3);assert.equal(other.relationship.score,.82345);assert.equal(other.relationship.rank_1_based,1);assert.equal(other.relationship.stored_candidate_count,1);assert.equal(other.relationship.eligible_pool_support,2);assert.equal(another.relationship.score,.73456);assert.equal(another.relationship.rank_1_based,2);
for(const mode of ['all','other']){const only=byContext.get(JSON.stringify(['query',null,mode]));assert.equal(only.relationship,null);assert.equal(only.candidate,null);assert.equal(only.photos_mission_mode,mode)}
for(const record of bundle.records){assert.equal(record.exported_at_utc,clock);assert.equal(record.purpose,'visual_review_handoff');assert.equal(record.atlas.encoder,'Frozen supplied encoder');assert.deepEqual(record.atlas.versions,[]);assert.equal(record.atlas.encoder_identity.version_source,'not_recorded');assert.equal(record.atlas.sources[0].sha256,'frozen-sha');assert.equal(record.review_note.verified,false);assert.ok(!JSON.stringify(record).includes('never include raw vectors'));assert.match(record.limitations.join(' '),/not a computational reproducibility package.*do not restore this pair/)}
assert.equal(first.query.version,null);assert.equal(first.query.mission,' flight-a ');assert.equal(first.query.crop_geometry.source_encoder,'Frozen supplied encoder');assert.equal(another.candidate.version,null);assert.equal(another.candidate.crop_geometry,null);assert.equal(another.candidate.crop_record.size_px,1280);
notes.set('[0,1,"all"]','Edited exactly \n ');notes.set('[0,2,"all"]','  ');const edited=reviewNoteBundle(atlas,notes,'https://example.org/atlas.html',clock);assert.equal(edited.record_count,5);assert.ok(!edited.records.some(record=>record.query.key==='query'&&record.candidate?.key==='other'&&record.photos_mission_mode==='all'));assert.equal(edited.records.filter(record=>record.query.key==='query'&&record.candidate?.key==='same').length,1);assert.equal(edited.records.find(record=>record.candidate?.key==='same').review_note.text,'Edited exactly \n ');
for(const badKey of ['bad json','[99,null,"all"]','[0,3,"all"]','[0,1,"unsupported"]']){const invalid=new Map(notes);invalid.set(badKey,'Meaningful unresolved note');assert.throws(()=>reviewNoteBundle(atlas,invalid,'https://example.org/atlas.html',clock),/No notes were exported/)}
const duplicate=JSON.parse(JSON.stringify({points:atlas.points,provenance:atlas.provenance}));duplicate.points[0].neighbours.push([1,.5]);assert.throws(()=>reviewNoteBundle(duplicate,new Map([['[0,1,"all"]','Ambiguous rank']]),'https://example.org/atlas.html',clock),/No notes were exported/);
atlas.provenance.sources[0].sha256='mutated';assert.equal(first.atlas.sources[0].sha256,'frozen-sha');
""")


def test_live_bundle_flushes_editors_modal_wins_and_download_preserves_state():
    points = [
        photo("query", "flight-a", [[1, .91234], [2, .82345]], other_mission_neighbours=[[2, .82345]], version=None, crop=1280),
        photo("same", "flight-a", [[0, .91234], [3, .73456]], other_mission_neighbours=[[3, .73456]], version=None),
        photo("other", "flight-b", [[0, .82345]], other_mission_neighbours=[[0, .82345]], version=None),
        photo("another", "flight-c", [[1, .73456]], other_mission_neighbours=[[1, .73456]], version=None),
    ]
    run_atlas(points, r"""
(async()=>{
assert.equal($('workspaceDownloadAllNotes').disabled,true);assert.equal($('downloadAllReviewNotes').textContent,'Download all notes (0)');
$('workspaceReviewNote').value='First pair';$('workspaceReviewNote').oninput();setWorkspaceCandidate(1);$('workspaceReviewNote').value='Second pair';$('workspaceReviewNote').oninput();$('similarMissionMode').value='other';$('similarMissionMode').onchange();$('workspaceReviewNote').value='Other-mode pair';$('workspaceReviewNote').oninput();
select(1);$('similarMissionMode').value='all';$('similarMissionMode').onchange();setWorkspaceCandidate(1);$('workspaceReviewNote').value='Another query';$('workspaceReviewNote').oninput();select(0);setWorkspaceCandidate(0);
assert.equal($('workspaceDownloadAllNotes').textContent,'Download all notes (4)');assert.equal($('downloadAllReviewNotes').disabled,false);
$('workspaceEnlarge').onclick();$('workspaceReviewNote').value='Stale primary editor';$('reviewNote').value='  Modal wins 🌳\n<script>data only</script>  ';
let blob,clicks=0;const urls=[],timers=[];URL.createObjectURL=value=>{blob=value;return 'blob:all-notes'};URL.revokeObjectURL=url=>urls.push(url);global.setTimeout=fn=>timers.push(fn);document.body={append(){}};const create=document.createElement;document.createElement=tag=>{const node=create(tag);node.click=()=>clicks++;node.remove=()=>{};return node};location.href='https://example.org/crownfirst-atlas.html#frame=query';global.fetch=()=>{throw new Error('No network')};Object.defineProperty(global,'localStorage',{get(){throw new Error('No persistence')}});
const before={pair:photoPair,rank:photoPair.rank,mode:neighborMode,selected,hash:location.hash,note:$('reviewNote').value,focus:document.activeElement};
sharedInspection={queryKey:'wrong-shared-query',candidates:[{score:999}]};data.comparison={wrong:'not source authority'};selected=3;neighborMode='other';$('downloadAllReviewNotes').onclick();
assert.equal(clicks,1);const bundle=JSON.parse(await blob.text());assert.equal(bundle.record_count,4);assert.equal(bundle.records.find(record=>record.query.key==='query'&&record.candidate?.key==='same').review_note.text,before.note);assert.equal(bundle.records.find(record=>record.query.key==='query'&&record.candidate?.key==='same').relationship.score,.91234);assert.equal(bundle.records.find(record=>record.query.key==='same'&&record.candidate?.key==='another').relationship.rank_1_based,2);assert.equal(photoPair,before.pair);assert.equal(photoPair.rank,before.rank);assert.equal(selected,3);assert.equal(neighborMode,'other');assert.equal(location.hash,before.hash);assert.equal(document.activeElement,before.focus);assert.equal($('reviewNote').value,before.note);assert.equal(new Set(bundle.records.map(record=>record.exported_at_utc)).size,1);timers.shift()();assert.deepEqual(urls,['blob:all-notes']);
selected=before.selected;neighborMode=before.mode;delete data.comparison;sharedInspection=null;$('closePhotoComparison').onclick();$('inspectPhoto').onclick();$('reviewNote').value='Query-only pending, no input event';$('downloadAllReviewNotes').onclick();const withOnly=JSON.parse(await blob.text());assert.equal(withOnly.record_count,5);const queryOnly=withOnly.records.find(record=>record.candidate===null);assert.equal(queryOnly.photos_mission_mode,'all');assert.equal(queryOnly.relationship,null);assert.equal(queryOnly.review_note.text,'Query-only pending, no input event');timers.shift()();
$('reviewNote').value=' \n\t ';$('reviewNote').oninput();assert.equal($('downloadAllReviewNotes').textContent,'Download all notes (4)');$('closePhotoComparison').onclick();$('workspaceReviewNote').value='';$('workspaceReviewNote').oninput();assert.equal($('workspaceDownloadAllNotes').textContent,'Download all notes (3)');
reviewNotes.set('[0,3,"all"]','Unresolvable, must abort');const priorClicks=clicks;$('workspaceDownloadAllNotes').onclick();assert.equal(clicks,priorClicks);assert.match($('workspaceDownloadStatus').textContent,/Could not prepare all notes.*No notes were exported/);assert.equal(reviewNotes.get('[0,3,"all"]'),'Unresolvable, must abort');reviewNotes.delete('[0,3,"all"]');
for(const key of reviewNotes.keys())reviewNotes.set(key,'');$('workspaceReviewNote').value=' \n ';saveWorkspaceReviewNote();assert.equal($('workspaceDownloadAllNotes').disabled,true);$('workspaceDownloadAllNotes').onclick();assert.equal(clicks,priorClicks);assert.match($('workspaceDownloadStatus').textContent,/Add a review note before downloading all notes/);
})().catch(error=>{console.error(error);process.exitCode=1});
""")


def test_bundle_actions_have_responsive_containers_and_do_not_share_grid_cells():
    html = runpy.run_path(ROOT / "dashboard/embedding_atlas_assets.py")["HTML"]
    assert '<div class="review-download-actions"><button id="workspaceDownloadReview"' in html
    assert '<div class="review-download-actions"><button id="downloadReviewRecord"' in html
    assert 'id="workspaceDownloadAllNotes" disabled' in html
    assert 'id="downloadAllReviewNotes" disabled' in html
    css = html.split("<style>")[1].split("</style>")[0]
    assert ".workspace-review .review-download-actions{grid-column:2;grid-row:3;flex-direction:column}" in css
    assert ".workspace-review textarea,.workspace-review .review-download-actions{grid-column:1;grid-row:auto}" in css
    assert ".workspace-review button{grid-column:2;grid-row:3}" not in css
    assert ".review-download-actions{display:flex;flex-wrap:wrap" in css
