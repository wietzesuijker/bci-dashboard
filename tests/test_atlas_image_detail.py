"""Enlarged image detail uses loaded pixels without changing scientific metadata."""

from html.parser import HTMLParser
import json
from pathlib import Path
import runpy

from test_atlas_mission_view import photo, run_atlas
from test_atlas_model_evidence import evidence_fixture, page_photos

ROOT = Path(__file__).resolve().parents[1]


def test_photos_detail_is_independent_centered_and_retained_for_unchanged_query():
    points = [
        photo("query", "a", [[1, .91234], [2, .81234]], source_width=4000, source_height=3000, crop=1280),
        photo("first", "b", source_width=4000, source_height=3000, crop=1280),
        photo("next", "c"),
    ]
    run_atlas(points, r"""
const frozen=JSON.stringify(data),hash=location.hash;function loaded(prefix,w=4000,h=3000){const image=$(prefix+'Image');image.naturalWidth=w;image.naturalHeight=h;image.onload()}
$('workspaceEnlarge').onclick();assert.equal(imageDetails.get('comparisonQuery').mode,'fit');assert.equal($('comparisonQueryViewport').style.overscrollBehavior,'auto');assert.equal($('comparisonQueryActual').disabled,true);assert.match($('comparisonQueryDetailStatus').textContent,/loading/);assert.equal(setImageDetailMode('comparisonQuery','actual'),false);
loaded('comparisonQuery');loaded('comparisonCandidate');assert.equal($('comparisonQueryActual').disabled,false);assert.equal($('comparisonQueryOverlay').getAttribute('hidden'),null);assert.equal($('comparisonQueryOverlay').getAttribute('viewBox'),'0 0 4000 3000');assert.deepEqual(['x','y','width','height'].map(name=>$('comparisonQueryOutline').getAttribute(name)),[1360,860,1280,1280]);
$('comparisonQueryActual').onclick();assert.equal($('comparisonQueryViewport').style.overscrollBehavior,'contain');assert.equal($('comparisonCandidateViewport').style.overscrollBehavior,'auto');assert.equal($('comparisonQueryStage').style.width,'4000px');assert.equal($('comparisonQueryStage').style.height,'3000px');assert.equal($('comparisonQueryImage').style.objectFit,'fill');assert.equal($('comparisonQueryActual').getAttribute('aria-pressed'),'true');assert.equal($('comparisonQueryViewport').scrollLeft,1680);assert.equal($('comparisonQueryViewport').scrollTop,1240);assert.equal($('comparisonCandidateStage').style.width,'100%');assert.equal(imageDetails.get('comparisonCandidate').mode,'fit');assert.equal($('comparisonQueryOverlay').getAttribute('hidden'),null);
$('comparisonQueryViewport').scrollLeft=200;$('comparisonQueryViewport').scrollTop=300;$('comparisonCandidateActual').onclick();$('comparisonCandidateViewport').scrollTop=450;
$('photoComparison').scrollTop=700;const staleLoad=$('comparisonCandidateImage').onload,staleError=$('comparisonCandidateImage').onerror;$('nextComparison').onclick();assert.equal($('photoComparison').scrollTop,700);assert.equal(imageDetails.get('comparisonQuery').mode,'actual');assert.equal($('comparisonQueryViewport').scrollLeft,200);assert.equal($('comparisonQueryViewport').scrollTop,300);assert.equal(imageDetails.get('comparisonCandidate').key,'next');assert.equal(imageDetails.get('comparisonCandidate').mode,'fit');assert.equal(imageDetails.get('comparisonCandidate').phase,'loading');assert.equal($('comparisonCandidateViewport').style.overscrollBehavior,'auto');assert.equal($('comparisonCandidateViewport').scrollTop,0);assert.equal($('comparisonCandidateActual').disabled,true);
const caption=$('comparisonCandidateCrop').textContent,status=$('comparisonCandidateStatus').textContent;staleLoad();staleError();assert.equal(imageDetails.get('comparisonCandidate').phase,'loading');assert.equal($('comparisonCandidateImage').hidden,true);assert.equal($('comparisonCandidateStatus').textContent,status);assert.equal($('comparisonCandidateCrop').textContent,caption);assert.equal($('comparisonCandidateOverlay').getAttribute('hidden'),'');loaded('comparisonCandidate',2000,1500);assert.equal($('comparisonCandidateActual').disabled,false);
$('photoComparison').scrollTop=1200;$('closePhotoComparison').onclick();$('workspaceEnlarge').onclick();assert.equal($('photoComparison').scrollTop,0);assert.equal(imageDetails.get('comparisonQuery').mode,'actual');assert.equal($('comparisonQueryViewport').scrollTop,300);assert.equal(imageDetails.get('comparisonCandidate').phase,'loaded');$('comparisonQueryFit').onclick();assert.equal($('comparisonQueryViewport').style.overscrollBehavior,'auto');assert.equal($('comparisonQueryStage').style.width,'100%');assert.equal($('comparisonQueryStage').style.height,'100%');assert.equal($('comparisonQueryImage').style.objectFit,'contain');assert.equal($('comparisonQueryViewport').scrollTop,0);assert.equal($('comparisonQueryOverlay').getAttribute('hidden'),null);assert.equal(selected,0);assert.equal(location.hash,hash);assert.equal(JSON.stringify(data),frozen);
""")


def test_crop_outline_requires_exact_loaded_dimensions_inline_and_enlarged():
    points = [
        photo("query", "a", [[1, .91234]], source_width=4000, source_height=3000, crop=1280),
        photo("unknown", "b", crop=1280),
    ]
    run_atlas(points, r"""
const frozen=JSON.stringify(data);$('photo').naturalWidth=2000;$('photo').naturalHeight=1500;$('photo').onload();assert.equal($('cropOverlay').getAttribute('hidden'),'');assert.match($('cropCaption').textContent,/2000 × 1500 px; recorded crop source 4000 × 3000 px/);assert.equal(imageDetails.has('selected'),false);assert.equal(imageDetails.has('workspaceCandidate'),false);
$('workspaceEnlarge').onclick();const image=$('comparisonQueryImage');image.naturalWidth=2000;image.naturalHeight=1500;image.onload();assert.equal($('comparisonQueryOverlay').getAttribute('hidden'),'');assert.match($('comparisonQueryCrop').textContent,/2000 × 1500 px; recorded crop source 4000 × 3000 px/);$('comparisonQueryActual').onclick();assert.equal($('comparisonQueryStage').style.width,'2000px');assert.equal($('comparisonQueryStage').style.height,'1500px');assert.equal($('comparisonQueryOverlay').getAttribute('hidden'),'');renderComparisonPhoto('comparisonQuery',0);assert.match($('comparisonQueryCrop').textContent,/2000 × 1500 px; recorded crop source 4000 × 3000 px/);assert.equal(imageDetails.get('comparisonQuery').mode,'actual');
const candidate=$('comparisonCandidateImage');candidate.naturalWidth=4000;candidate.naturalHeight=3000;candidate.onload();assert.equal($('comparisonCandidateOverlay').getAttribute('hidden'),'');assert.match($('comparisonCandidateCrop').textContent,/footprint unknown/);$('comparisonCandidateActual').onclick();assert.equal($('comparisonCandidateStage').style.width,'4000px');const record=reviewRecord(data,photoComparison,'https://example.org/atlas.html','2026-10-15T00:00:00Z');assert.equal(record.query.crop_geometry.width,4000);assert.equal(record.query.crop_geometry.height,3000);assert.equal(record.candidate.crop_geometry,null);assert.equal(record.candidate.crop_record.size_px,1280);assert.equal(record.candidate.crop_record.source_width_px,null);assert.equal(JSON.stringify(data),frozen);
""")


def test_loading_error_zero_and_missing_dimensions_disable_actual_pixels():
    points = [photo("query", "a", [[1, .9], [2, .8]]), photo("zero", "b"), photo("missing", "c", image=None)]
    run_atlas(points, r"""
$('workspaceEnlarge').onclick();const query=$('comparisonQueryImage');query.naturalWidth=4000;query.naturalHeight=3000;query.onload();$('comparisonQueryActual').onclick();query.onerror();assert.equal($('comparisonQueryViewport').style.overscrollBehavior,'auto');assert.equal(imageDetails.get('comparisonQuery').mode,'fit');assert.equal($('comparisonQueryActual').disabled,true);assert.match($('comparisonQueryDetailStatus').textContent,/failed to load/);assert.match($('comparisonQueryStatus').textContent,/Open full image to retry/);assert.equal($('comparisonQueryOriginal').href,'https://example.org/query.jpg');renderComparisonPhoto('comparisonQuery',0);assert.equal(imageDetails.get('comparisonQuery').phase,'error');
beginImageDetail('comparisonQuery','query');assert.equal($('comparisonQueryActual').disabled,true);assert.equal($('comparisonQueryViewport').scrollTop,0);assert.match($('comparisonQueryDetailStatus').textContent,/loading/);query.naturalWidth=300;query.naturalHeight=200;query.onload();$('comparisonQueryActual').onclick();assert.equal($('comparisonQueryViewport').scrollLeft,0);assert.equal($('comparisonQueryViewport').scrollTop,0);
const candidate=$('comparisonCandidateImage');candidate.naturalWidth=0;candidate.naturalHeight=0;candidate.onload();assert.equal(imageDetails.get('comparisonCandidate').phase,'dimensions');assert.equal($('comparisonCandidateActual').disabled,true);assert.match($('comparisonCandidateDetailStatus').textContent,/dimensions are unavailable/);candidate.naturalWidth=undefined;candidate.naturalHeight=undefined;candidate.onload();assert.equal($('comparisonCandidateActual').disabled,true);$('nextComparison').onclick();assert.equal(imageDetails.get('comparisonCandidate').phase,'missing');assert.match($('comparisonCandidateDetailStatus').textContent,/URL is unavailable/);assert.equal($('comparisonCandidateOriginal').hidden,true);assert.equal($('comparisonCandidateActual').disabled,true);
select(1);$('inspectPhoto').onclick();assert.equal(imageDetails.get('comparisonQuery').key,'zero');assert.equal(imageDetails.get('comparisonQuery').phase,'loading');assert.equal(imageDetails.get('comparisonQuery').mode,'fit');assert.equal($('comparisonQueryActual').disabled,true);
""")


def test_shared_detail_keeps_shared_authority_and_photos_state_without_crops():
    checks = "data.comparison=" + json.dumps(evidence_fixture()) + r""";
compareSelection('query');$('workspaceReviewNote').value='Keep note';$('workspaceReviewNote').oninput();const pair=photoPair,hash=location.hash,frozen=JSON.stringify(data);openSharedInspection('query',1,0);function loaded(prefix){$(prefix+'Image').naturalWidth=4000;$(prefix+'Image').naturalHeight=3000;$(prefix+'Image').onload()}
loaded('sharedQuery');loaded('sharedCandidate');assert.equal($('sharedQueryViewport').style.overscrollBehavior,'auto');$('sharedQueryActual').onclick();assert.equal($('sharedQueryViewport').style.overscrollBehavior,'contain');$('sharedQueryViewport').scrollLeft=250;$('sharedQueryViewport').scrollTop=350;assert.equal($('sharedQueryStage').style.width,'4000px');assert.equal($('sharedQueryStage').style.height,'3000px');assert.equal($('sharedQueryViewport').scrollLeft,250);const staleLoad=$('sharedCandidateImage').onload,staleError=$('sharedCandidateImage').onerror;$('sharedCandidateActual').onclick();$('sharedInspectionDialog').scrollTop=600;$('sharedInspectionNext').onclick();assert.equal($('sharedInspectionDialog').scrollTop,600);assert.equal(imageDetails.get('sharedQuery').mode,'actual');assert.equal($('sharedQueryViewport').scrollTop,350);assert.equal(imageDetails.get('sharedCandidate').mode,'fit');assert.equal(imageDetails.get('sharedCandidate').phase,'loading');const status=$('sharedCandidateStatus').textContent;staleLoad();staleError();assert.equal($('sharedCandidateImage').hidden,true);assert.equal($('sharedCandidateStatus').textContent,status);assert.equal(imageDetails.get('sharedCandidate').phase,'loading');loaded('sharedCandidate');assert.equal(sharedInspection.modelIndex,1);assert.equal(sharedInspection.rank,1);assert.equal(sharedInspection.candidates[1].score,.81845);assert.match($('sharedInspectionScore').textContent,/0.818/);assert.match($('sharedQueryLabel').textContent,/Cohort query label/);assert.match($('sharedCandidateLabel').textContent,/No recorded frame label/);$('sharedInspectionDialog').scrollTop=1100;$('sharedInspectionClose').onclick();openSharedInspection('query',1,1);assert.equal($('sharedInspectionDialog').scrollTop,0);assert.equal(imageDetails.get('sharedQuery').mode,'actual');assert.equal($('sharedQueryViewport').scrollTop,350);assert.equal(photoPair,pair);assert.equal(location.hash,hash);assert.equal($('workspaceReviewNote').value,'Keep note');assert.equal(JSON.stringify(data),frozen);
"""
    run_atlas(page_photos(), checks)


def test_only_four_enlarged_panels_have_native_scrollable_detail_stages():
    html = runpy.run_path(ROOT / "dashboard/embedding_atlas_assets.py")["HTML"]
    assert html.count('class="image-detail-controls"') == 4
    assert html.count('class="image-detail-stage"') == 4
    for prefix in ["comparisonQuery", "comparisonCandidate", "sharedQuery", "sharedCandidate"]:
        assert f'id="{prefix}Viewport"' in html
        assert f'id="{prefix}Stage"' in html
        assert f'id="{prefix}Fit" aria-pressed="true"' in html
        assert f'id="{prefix}Actual" aria-pressed="false" disabled' in html
        viewport = html.split(f'id="{prefix}Viewport"')[1].split(">")[0]
        assert 'tabindex="0"' in viewport
        assert 'role="region"' in viewport
        assert "arrow keys to scroll" in viewport
    shared = html.split('<dialog id="sharedInspectionDialog"')[1].split("</dialog>")[0]
    assert "<svg" not in shared
    assert ".image-detail-viewport{overflow:auto;overscroll-behavior:auto;" in html
    assert ".image-detail-stage{position:relative;" in html
    helpers = html.split("// IMAGE_DETAIL_HELPERS_START")[1].split("// IMAGE_DETAIL_HELPERS_END")[0]
    assert "devicePixelRatio" not in helpers
    assert "source_width" not in helpers
    assert "wheel" not in helpers
    assert "preventDefault" not in helpers


def test_image_and_crop_overlay_share_the_dimensioned_stage():
    html = runpy.run_path(ROOT / "dashboard/embedding_atlas_assets.py")["HTML"]

    class StageParents(HTMLParser):
        def __init__(self):
            super().__init__()
            self.divs = []
            self.parents = {}

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "div":
                self.divs.append(attrs.get("id"))
            if tag in ["img", "svg"]:
                self.parents[attrs.get("id")] = self.divs[-1] if self.divs else None

        def handle_endtag(self, tag):
            if tag == "div":
                self.divs.pop()

    parents = StageParents()
    parents.feed(html)
    for prefix in ["comparisonQuery", "comparisonCandidate"]:
        assert parents.parents[prefix + "Image"] == prefix + "Stage"
        assert parents.parents[prefix + "Overlay"] == prefix + "Stage"
    for prefix in ["sharedQuery", "sharedCandidate"]:
        assert parents.parents[prefix + "Image"] == prefix + "Stage"
        assert prefix + "Overlay" not in parents.parents
