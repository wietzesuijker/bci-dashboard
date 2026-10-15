"""Query selection composes browse scopes without changing retrieval evidence."""

from html.parser import HTMLParser
import json
from pathlib import Path
import runpy

from test_atlas_mission_view import photo, run_atlas

ROOT = Path(__file__).resolve().parents[1]
OUTSIDE_KEY = "comb_DJI_20251009090859_0041_V_10603zoom.JPG"


def gallery_fixture():
    points = [photo(OUTSIDE_KEY, "mission-b", [[1, .91], [2, .82]], other_mission_neighbours=[[2, .82]])] + [
        photo("frame-" + str(i).zfill(3), "mission-a", label="Fabaceae" if i % 2 == 0 else None, image="javascript:invalid" if i == 10 else "https://example.org/" + str(i) + ".jpg")
        for i in range(1, 207)
    ]
    cohort = [[points[i]["key"], points[i]["label"]] for i in range(10, 181)]
    frames = []
    for index, (_, label) in enumerate(cohort):
        neighbor = (index + 1) % len(cohort)
        support = int(bool(cohort[neighbor][1]))
        same = int(label == cohort[neighbor][1]) if label else None
        frames.append([1, [[support, same, [[neighbor, .61234]]], [support, same, [[neighbor, .72345]]]]])
    comparison = {"cohort": cohort, "frames": frames, "models": ["Model A", "Model B"], "k": 1, "cohort_size": len(cohort), "labelled_cohort_support": sum(bool(record[1]) for record in cohort), "labels_available": True, "method": "Shared-cohort cosine", "label_boundary": "Recorded frame labels", "invalid_common_keys": [], "unshared_counts": [0, 36], "sources": []}
    return points, comparison


def test_shared_scope_composes_filters_without_mutating_selected_pair_or_notes():
    points, comparison = gallery_fixture()
    checks = "data.comparison=" + json.dumps(comparison) + r""";
compareSelection(P[selected].key);list();assert.equal($('browsePhotos').open,undefined);assert.equal($('sharedBrowseScope').disabled,false);
$('similarMissionMode').value='other';$('similarMissionMode').onchange();$('workspaceReviewNote').value='Keep outside-query note';$('workspaceReviewNote').oninput();
const prior={selected,hash:location.hash,pair:photoPair,rank:photoPair.rank,mode:neighborMode,note:$('workspaceReviewNote').value,view:{...view},sheets:$('comparisonModels').children};
$('sharedBrowseScope').focus();$('sharedBrowseScope').checked=true;$('sharedBrowseScope').onchange();
assert.equal(document.activeElement,$('sharedBrowseScope'));assert.equal(browseSharedOnly,true);assert.equal(visible.length,171);assert.equal(selected,prior.selected);assert.equal(location.hash,prior.hash);assert.equal(photoPair,prior.pair);assert.equal(photoPair.rank,prior.rank);assert.equal(neighborMode,prior.mode);assert.equal($('workspaceReviewNote').value,prior.note);assert.deepEqual(view,prior.view);assert.equal($('comparisonModels').children,prior.sheets);
assert.equal($('results').children[0]['data-frame'],P[0].key);assert.match($('results').children[0]['aria-label'],/outside current filter/);assert.match($('browseCount').textContent,/171 of 171 photos match.*207 total.*outside these matches/);assert.match($('browseScopeStatus').textContent,/Available in both models/i);assert.match($('sharedBrowseScopeHelp').textContent,/query choices only, not similar-photo rankings/);
$('search').value='frame-1';$('group').value='With recorded label';$('search').focus();$('search').oninput();assert.equal(document.activeElement,$('search'));assert.deepEqual(visible,P.map((p,i)=>i).filter(i=>i>=10&&i<=180&&P[i].key.includes('frame-1')&&Boolean(P[i].label)));
$('search').value='no-result';$('search').oninput();assert.equal(visible.length,0);assert.equal($('results').children.length,1);assert.equal($('browseEmpty').hidden,false);assert.equal($('nextBrowsePage').disabled,true);assert.equal($('sharedBrowseScope').checked,true);assert.equal(photoPair,prior.pair);assert.equal(location.hash,prior.hash);
$('clearBrowseFilters').onclick();assert.equal(browseSharedOnly,false);assert.equal($('sharedBrowseScope').checked,false);assert.equal($('search').value,'');assert.equal($('group').value,'All frames');assert.equal(visible.length,207);assert.equal(browsePage,0);assert.equal(photoPair,prior.pair);assert.equal($('workspaceReviewNote').value,prior.note);
"""
    run_atlas(points, checks, initial_hash="#frame=" + OUTSIDE_KEY)


def test_outside_recovery_opens_comparable_gallery_and_only_explicit_selection_changes_query():
    points, comparison = gallery_fixture()
    checks = "data.comparison=" + json.dumps(comparison) + r""";
compareSelection(P[selected].key);list();showAtlasView('models');assert.equal($('browseComparablePhotos').hidden,false);assert.equal($('browseComparablePhotos').disabled,false);assert.equal($('comparisonModels').children.length,0);
$('workspaceReviewNote').value='Undownloaded outside note';$('workspaceReviewNote').oninput();const prior={hash:location.hash,pair:photoPair,note:$('workspaceReviewNote').value};$('search').value='opaque impossible search';$('group').value='Without recorded label';
$('browseComparablePhotos').onclick();assert.equal($('search').value,'');assert.equal($('group').value,'All frames');assert.equal($('sharedBrowseScope').checked,true);assert.equal(browseSharedOnly,true);assert.equal(visible.length,171);assert.equal(selected,0);assert.equal(location.hash,prior.hash);assert.equal(photoPair,prior.pair);assert.equal($('workspaceReviewNote').value,prior.note);assert.equal($('browsePhotos').open,true);assert.equal(document.activeElement,$('browsePhotosSummary'));assert.equal($('results').children[0]['data-frame'],P[0].key);
moveBrowsePage(1);assert.equal(browsePage,1);const card=$('results').children[1],chosenKey=card['data-frame'];assert.match(card['aria-label'],/^Select this photo/);card.focus();card.onclick();
assert.equal(P[selected].key,chosenKey);assert.equal(location.hash,frameHash(chosenKey));assert.equal($('browsePhotos').open,false);assert.equal($('showBrowsePhotos')['aria-expanded'],'false');assert.equal(atlasView,'models');assert.equal(document.activeElement,$('modelComparisonQueryKey'));assert.equal(browseSharedOnly,true);assert.equal(browsePage,1);assert.equal($('sharedBrowseScope').checked,true);
showAtlasView('models');assert.equal($('comparisonModels').children.length,2);assert.equal($('browseComparablePhotos').hidden,true);assert.match($('modelComparisonQueryKey').textContent,new RegExp(chosenKey));
$('showBrowsePhotos').onclick();assert.equal($('browsePhotos').open,true);assert.equal(browsePage,1);assert.equal(browseSharedOnly,true);assert.equal($('results').children[0]['data-frame'],chosenKey);
selectGalleryPhoto(0);assert.equal($('workspaceReviewNote').value,'Undownloaded outside note');assert.equal(atlasView,'models');assert.equal(document.activeElement,$('modelComparisonQueryKey'));
"""
    run_atlas(points, checks, initial_hash="#frame=" + OUTSIDE_KEY)


def test_gallery_preview_preserves_full_frame_and_missing_photo_identity():
    run_atlas([photo("query", None), photo("missing", None, label=None, image="javascript:invalid")], r"""
const button=$('results').children[0],preview=button.children[0],image=preview.children[0],status=preview.children[1];assert.equal(image.loading,'lazy');assert.equal(image.width,400);assert.equal(image.height,300);assert.equal(image.alt,'');assert.equal(status.hidden,true);image.onerror();assert.equal(image.hidden,true);assert.equal(status.hidden,false);assert.match(button['aria-label'],/Frame query/);
const missing=$('results').children[1];assert.equal(missing.children[0].children[0].textContent,'Photo unavailable');assert.match(missing['aria-label'],/^Select this photo.*No recorded frame label.*Frame missing/);assert.match(missing.children[1].children[2].textContent,/missing.*Mission unavailable/);missing.onclick();assert.equal(selected,1);assert.equal(document.activeElement,$('selectedPhotoHeading'));assert.equal($('browsePhotos').open,false);assert.equal($('key').textContent,'missing');assert.match($('photoStatus').textContent,/unavailable/);
""")


def test_unavailable_shared_scope_does_not_fall_back_when_checked():
    run_atlas([photo("query", "mission", [[1, .9]]), photo("other", "mission")], r"""
assert.equal($('sharedBrowseScope').disabled,true);assert.equal($('browseComparablePhotos').disabled,true);assert.match($('sharedBrowseScopeHelp').textContent,/Shared model comparison unavailable/);const prior={pair:photoPair,hash:location.hash};$('browseComparablePhotos').onclick();assert.equal(visible.length,2);assert.equal($('browsePhotos').open,undefined);
$('sharedBrowseScope').checked=true;$('sharedBrowseScope').onchange();assert.equal(browseSharedOnly,true);assert.equal(visible.length,0);assert.equal($('sharedBrowseScope').checked,true);assert.equal($('results').children.length,1);assert.equal($('browseEmpty').hidden,false);assert.equal(photoPair,prior.pair);assert.equal(location.hash,prior.hash);$('clearBrowseFilters').onclick();assert.equal(visible.length,2);assert.equal($('sharedBrowseScope').checked,false);
""")


def test_gallery_markup_keeps_primary_closed_default_and_large_uncropped_previews():
    html = runpy.run_path(ROOT / "dashboard/embedding_atlas_assets.py")["HTML"]

    class Elements(HTMLParser):
        def __init__(self):
            super().__init__()
            self.ids = {}

        def handle_starttag(self, tag, attrs):
            attributes = dict(attrs)
            if "id" in attributes:
                assert attributes["id"] not in self.ids
                self.ids[attributes["id"]] = (tag, attributes)

    elements = Elements()
    elements.feed(html)
    assert "open" not in elements.ids["browsePhotos"][1]
    assert elements.ids["sharedBrowseScope"][1]["type"] == "checkbox"
    assert elements.ids["results"][1]["aria-label"] == "Choose the selected query photo"
    assert elements.ids["selectedPhotoHeading"][1]["tabindex"] == "-1"
    css = html.split("<style>")[1].split("</style>")[0]
    assert ".browse-preview img{width:100%;height:100%;object-fit:contain}" in css
    assert "max-height:clamp(340px,58svh,640px)" in css
    assert "#results{grid-template-columns:1fr}" in css
    assert "height:clamp(360px,42vh,560px)" in css


def test_gallery_cancel_and_reopen_follow_active_workspace_without_stale_destination():
    points, comparison = gallery_fixture()
    checks = "data.comparison=" + json.dumps(comparison) + r""";
compareSelection(P[selected].key);list();$('similarMissionMode').value='other';$('similarMissionMode').onchange();$('workspaceReviewNote').value='Retain this note';$('workspaceReviewNote').oninput();
const prior={selected,hash:location.hash,pair:photoPair,rank:photoPair.rank,mode:neighborMode,note:$('workspaceReviewNote').value};
showAtlasView('models');$('browseComparablePhotos').onclick();moveBrowsePage(1);assert.equal($('closeBrowsePhotos').textContent,'Back to model comparison');$('closeBrowsePhotos').onclick();
assert.equal(atlasView,'models');assert.equal(document.activeElement,$('modelComparisonQueryKey'));assert.equal($('browsePhotos').open,false);assert.equal(browsePage,1);assert.equal(browseSharedOnly,true);assert.equal(selected,prior.selected);assert.equal(location.hash,prior.hash);assert.equal(photoPair,prior.pair);assert.equal(photoPair.rank,prior.rank);assert.equal(neighborMode,prior.mode);assert.equal($('workspaceReviewNote').value,prior.note);
showAtlasView('photos');$('showBrowsePhotos').onclick();assert.equal($('closeBrowsePhotos').textContent,'Back to selected photo');assert.equal(browseSharedOnly,true);assert.equal(browsePage,1);$('results').children[1].onclick();assert.equal(atlasView,'photos');assert.equal(document.activeElement,$('selectedPhotoHeading'));assert.equal(browseSharedOnly,true);assert.equal(browsePage,1);
showAtlasView('models');$('showBrowsePhotos').onclick();assert.equal($('closeBrowsePhotos').textContent,'Back to model comparison');$('browsePhotos').open=false;$('browsePhotos').ontoggle();assert.equal($('showBrowsePhotos')['aria-expanded'],'false');
showAtlasView('photos');$('showBrowsePhotos').onclick();assert.equal($('closeBrowsePhotos').textContent,'Back to selected photo');$('closeBrowsePhotos').onclick();assert.equal(atlasView,'photos');assert.equal(document.activeElement,$('selectedPhotoHeading'));
showAtlasView('models');$('showBrowsePhotos').onclick();showAtlasView('photos');assert.equal($('closeBrowsePhotos').textContent,'Back to selected photo');$('closeBrowsePhotos').onclick();assert.equal(atlasView,'photos');
showAtlasView('locations');$('showBrowsePhotos').onclick();assert.equal($('closeBrowsePhotos').textContent,'Back to selected photo');$('results').children[0].onclick();assert.equal(atlasView,'photos');assert.equal(document.activeElement,$('selectedPhotoHeading'));
"""
    run_atlas(points, checks, initial_hash="#frame=" + OUTSIDE_KEY)
