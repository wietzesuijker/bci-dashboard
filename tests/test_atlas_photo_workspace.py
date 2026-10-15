"""The primary photo pair remains authoritative across views and handoffs."""

from html.parser import HTMLParser
from pathlib import Path
import runpy

from test_atlas_mission_view import photo, run_atlas

ROOT = Path(__file__).resolve().parents[1]


def workspace_points():
    return [
        photo("query", "flight-a", [[1, .7]]),
        photo("requested", "flight-a", [[2, .94321], [3, .81234]], other_mission_neighbours=[[3, .81234]]),
        photo("candidate-same", "flight-a", [[1, .94321]]),
        photo("candidate-other", "flight-b", [[1, .81234]], other_mission_neighbours=[[1, .81234]], label="Luehea"),
        *[photo("extra-" + str(i), "flight-a") for i in range(155)],
    ]


def test_primary_pair_defaults_from_deep_link_and_survives_navigation_and_browsing():
    run_atlas(workspace_points(), r"""
assert.equal(atlasView,'photos');assert.equal($('photosView').hidden,false);assert.equal($('locationsView').hidden,true);assert.equal($('modelComparisonView').hidden,true);assert.equal(photoComparison,null);
assert.equal(selected,1);assert.equal(photoPair.query,1);assert.equal(photoPair.rank,0);assert.equal($('photo').src,'https://example.org/requested.jpg');assert.equal($('workspaceCandidateImage').src,'https://example.org/candidate-same.jpg');assert.match($('botanistLabel').textContent,/Recorded frame label: Fabaceae/);assert.match($('workspaceCandidateLabel').textContent,/Fabaceae/);
const query={key:P[selected].key,image:$('photo').src,label:$('botanistLabel').textContent,hash:location.hash,view:{...view},visible,rows:$('results').children};
$('workspaceReviewNote').value='First pair';$('workspaceReviewNote').oninput();$('workspaceNextCandidate').onclick();assert.equal(photoPair.rank,1);assert.match($('workspaceCandidateLabel').textContent,/Luehea/);assert.equal($('workspaceReviewNote').value,'');$('workspaceReviewNote').value='Second pair, unverified';$('workspaceReviewNote').oninput();
assert.equal(P[selected].key,query.key);assert.equal($('photo').src,query.image);assert.equal($('botanistLabel').textContent,query.label);assert.equal(location.hash,query.hash);assert.deepEqual(view,query.view);assert.equal(visible,query.visible);assert.equal($('results').children,query.rows);assert.equal(photoComparison,null);
$('workspaceNextCandidate').onclick();assert.equal(photoPair.rank,1);assert.equal($('workspaceNextCandidate').disabled,true);
moveBrowsePage(1);assert.equal(browsePage,1);const browsed=$('results').children;
for(const name of ['locations','models','photos'])showAtlasView(name);
assert.equal(atlasView,'photos');assert.equal(photoPair.rank,1);assert.equal(photoPair.mode,'all');assert.equal(browsePage,1);assert.equal($('results').children,browsed);assert.equal($('workspaceReviewNote').value,'Second pair, unverified');assert.equal(location.hash,query.hash);
$('workspaceEnlarge').onclick();assert.equal(photoComparison,photoPair);assert.equal($('reviewNote').value,'Second pair, unverified');$('reviewNote').value='From enlargement';$('reviewNote').oninput();assert.equal($('workspaceReviewNote').value,'From enlargement');$('previousComparison').onclick();assert.equal(photoPair.rank,0);assert.equal($('workspaceCandidateImage').src,'https://example.org/candidate-same.jpg');assert.equal($('workspaceReviewNote').value,'First pair');$('closePhotoComparison').onclick();assert.equal(photoPair.rank,0);assert.equal(photoComparison,null);
$('neighbors').children[1].children[0].onclick();assert.equal(photoPair.rank,1);assert.equal($('workspaceReviewNote').value,'From enlargement');assert.equal(selected,1);
$('search').focus();$('search').value='candidate';filter();assert.equal(document.activeElement,$('search'));assert.equal($('browsePhotos').open,true);assert.equal(photoPair.rank,1);assert.equal(selected,1);assert.equal(location.hash,query.hash);assert.deepEqual(visible,[2,3]);assert.match($('selectionStatus').textContent,/outside the current filter/);
$('similarMissionMode').value='other';$('similarMissionMode').onchange();assert.equal(selected,1);assert.equal(photoPair.mode,'other');assert.equal(photoPair.candidates[0][0],3);assert.equal($('workspaceReviewNote').value,'');$('workspaceReviewNote').value='Other mission note';$('workspaceReviewNote').oninput();showAtlasView('locations');showAtlasView('photos');assert.equal($('workspaceReviewNote').value,'Other mission note');assert.equal(location.hash,query.hash);
$('workspaceChooseCandidate').onclick();assert.equal(selected,3);assert.equal(location.hash,'#frame=candidate-other');assert.equal(photoPair.mode,'other');assert.equal(photoPair.query,3);assert.equal(photoPair.candidates[0][0],1);
""", initial_hash="#frame=requested")


def test_primary_download_uses_displayed_pair_and_shared_comparison_keeps_its_cohort():
    run_atlas(workspace_points(), r"""
(async()=>{
const shared={method:'Shared-cohort full vector cosine',label_boundary:'Frame label records.',invalid_common_keys:[],unshared_counts:[2,3],sources:[{file:'shared-cohort.json',sha256:'cohort-hash'}],cohort:[['requested','Fabaceae'],['candidate-other','Luehea']],frames:[[1,[[1,0,[[1,.12345]]],[1,0,[[1,.23456]]]]]],k:1,cohort_size:2,labelled_cohort_support:2,models:['Model A','Model B'],labels_available:true};
data.comparison=shared;compareSelection(P[selected].key);showAtlasView('models');assert.match($('modelComparisonQueryKey').textContent,/requested/);assert.match($('modelComparisonQueryLabel').textContent,/Fabaceae/);assert.match($('comparisonSummary').textContent,/Both encoders rank the same 2 frames.*Agreement is not accuracy/);assert.match($('comparisonProvenance').textContent,/shared-cohort.json: cohort-hash/);
const cohortButton=$('comparisonModels').children[0].children[2].children[0].children[0];assert.match(cohortButton.textContent,/Select this photo:.*candidate-other.*Shared-cohort cosine 0.123/);assert.equal(photoPair.candidates[0][1],.94321);
showAtlasView('photos');setWorkspaceCandidate(1);$('workspaceReviewNote').value='Primary pair 🌳\nNo label change';$('workspaceReviewNote').oninput();
let blob,removed=false,clicked=false;const revoke=[],timers=[];URL.createObjectURL=value=>{blob=value;return 'blob:workspace'};URL.revokeObjectURL=url=>revoke.push(url);global.setTimeout=fn=>timers.push(fn);document.body={append(){}};const create=document.createElement;document.createElement=tag=>{const node=create(tag);node.click=()=>{clicked=true};node.remove=()=>{removed=true};return node};location.href='https://example.org/crownfirst-atlas.html#frame=requested';
const oldSelected=selected;selected=0;neighborMode='other';$('workspaceDownloadReview').onclick();assert.equal(clicked,true);assert.equal(removed,true);const record=JSON.parse(await blob.text());assert.equal(record.query.key,'requested');assert.equal(record.candidate.key,'candidate-other');assert.equal(record.relationship.mode,'all');assert.equal(record.relationship.score,.81234);assert.equal(record.relationship.rank_1_based,2);assert.equal(record.review_note.text,'Primary pair 🌳\nNo label change');assert.match(record.scope,/Single-model photo review.*not the shared-cohort/);assert.notEqual(record.relationship.score,.12345);timers.shift()();assert.deepEqual(revoke,['blob:workspace']);selected=oldSelected;neighborMode='all';
showAtlasView('models');cohortButton.focus();assert.equal(document.activeElement,cohortButton);cohortButton.onclick();assert.equal(document.activeElement,$('modelComparisonQueryKey'));assert.match($('modelComparisonQueryKey').textContent,/candidate-other/);assert.equal(selected,3);assert.equal(location.hash,'#frame=candidate-other');assert.equal(photoPair.query,3);assert.equal(photoPair.candidates[0][1],.81234);
$('search').focus();compareSelection(P[selected].key);assert.equal(document.activeElement,$('search'));select(0);assert.equal(document.activeElement,$('search'));assert.match($('modelComparisonQueryKey').textContent,/query/);assert.match($('modelComparisonQueryLabel').textContent,/Fabaceae/);assert.match($('comparisonSummary').textContent,/outside the shared comparison cohort/);
})().catch(error=>{console.error(error);process.exitCode=1});
""", initial_hash="#frame=requested")


def test_missing_request_warning_is_global_and_empty_retrieval_keeps_selected_usable():
    run_atlas([photo("query", None, image="https://example.org/retry.jpg", other_mission_neighbours=None)], r"""
assert.equal(atlasView,'photos');assert.equal(requestedFrameKey,'missing-request');assert.match($('linkStatus').textContent,/unavailable in this model/);assert.equal(photoPair.rank,null);assert.equal($('workspaceCandidatePanel').hidden,true);assert.match($('workspaceCandidateEmpty').textContent,/No stored similar photos/);assert.equal($('workspaceChooseCandidate').disabled,true);
$('photo').onerror();assert.equal($('photo').hidden,true);assert.match($('photoStatus').textContent,/Photo unavailable/);assert.match($('botanistLabel').textContent,/Fabaceae/);assert.equal($('original').href,'https://example.org/retry.jpg');assert.equal($('key').textContent,'query');assert.match($('cropCaption').textContent,/unknown/);
$('similarMissionMode').value='other';$('similarMissionMode').onchange();assert.match($('workspaceCandidateEmpty').textContent,/no recorded mission ID/);assert.equal($('workspaceEnlarge').disabled,true);$('inspectPhoto').onclick();assert.equal(photoComparison.rank,null);assert.equal($('photoComparison').open,true);$('closePhotoComparison').onclick();assert.match($('linkStatus').textContent,/unavailable in this model/);
""", initial_hash="#frame=missing-request")


def test_workspace_markup_has_unique_ids_global_warning_and_selected_first_mobile_flow():
    html = runpy.run_path(ROOT / "dashboard/embedding_atlas_assets.py")["HTML"]

    class Elements(HTMLParser):
        def __init__(self):
            super().__init__()
            self.ids = []

        def handle_starttag(self, tag, attrs):
            attributes = dict(attrs)
            if "id" in attributes:
                self.ids.append(attributes["id"])

    elements = Elements()
    elements.feed(html)
    assert len(elements.ids) == len(set(elements.ids))
    assert html.index('id="linkStatus"') < html.index('id="photosView"')
    assert html.index('id="photoFrame"') < html.index('id="workspaceCandidateFrame"')
    assert 'aria-label="Atlas workspace"' in html
    assert 'aria-label="Model"' in html
    assert 'id="workspaceDownloadReview"' in html
    assert 'id="modelComparisonQueryKey"' in html
    css = html.split("<style>")[1].split("</style>")[0]
    assert "height:clamp(360px,42vh,560px)" in css
    assert ".primary-panel[aria-labelledby=selectedPhotoHeading]{order:1}" in css
    assert ".candidate-controls{order:2}" in css
    assert ".primary-panel[aria-labelledby=workspaceCandidateHeading]{order:3}" in css
