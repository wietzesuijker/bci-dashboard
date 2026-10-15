"""Shared-model photo evidence never borrows full-pool scores or crop geometry."""

from html.parser import HTMLParser
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess

import pytest

from test_atlas_mission_view import photo, run_atlas

ROOT = Path(__file__).resolve().parents[1]


def evidence_fixture(labelled=True):
    cohort = [["query", "Cohort query label" if labelled else None]] + [
        ["candidate-" + str(i), "Cohort taxon " + str(i) if i % 2 else None]
        for i in range(1, 19)
    ]
    rankings = [
        [[i, round(.91234 - rank * .005, 5)] for rank, i in enumerate(range(1, 13))],
        [[i, round(.82345 - rank * .005, 5)] for rank, i in enumerate(range(7, 19))],
    ]
    return {
        "cohort": cohort,
        "frames": [[6, [[6, 2 if labelled else None, rankings[0]], [6, 1 if labelled else None, rankings[1]]]]],
        "models": ["Model A exact checkpoint", "Model B exact checkpoint"],
        "k": 12,
        "cohort_size": len(cohort),
        "labelled_cohort_support": 10 if labelled else 9,
        "labels_available": True,
        "method": "Independent full-vector cosine on the shared cohort.",
        "label_boundary": "Frame records, not verified crown identities.",
        "invalid_common_keys": [],
        "unshared_counts": [0, 2],
        "sources": [{"file": "shared-source.npz", "sha256": "shared-hash"}],
    }


def page_photos():
    return [
        photo("query", "mission-a", [[16, .99999]], other_mission_neighbours=[[17, .88888]], label="Page label distractor", source_width=4000, source_height=3000, crop=1280),
        *[photo("candidate-" + str(i), "mission-b", label="Wrong page taxon " + str(i), image="javascript:alert(1)" if i == 1 else "https://example.org/" + str(i) + ".jpg") for i in range(1, 18)],
    ]


def test_contact_sheets_show_all_ranks_using_cohort_labels_and_key_intersection():
    comparison = json.dumps(evidence_fixture())
    checks = "data.comparison=" + comparison + r""";
compareSelection('query');showAtlasView('models');
assert.match($('modelComparisonQueryLabel').textContent,/Cohort query label/);assert.doesNotMatch($('modelComparisonQueryLabel').textContent,/Page label distractor/);assert.match($('comparisonSummary').textContent,/6 of 12 nearest frames shared/);assert.match($('comparisonProvenance').textContent,/shared-source.npz: shared-hash/);
const sheets=$('comparisonModels').children;assert.equal(sheets.length,2);assert.equal(sheets[0].className,'shared-model-sheet');assert.equal(sheets[0].children[2].children.length,12);assert.equal(sheets[1].children[2].children.length,12);
function cards(sheet){return sheet.children[2].children.map(item=>item.children[0])}
for(const [model,sheet] of sheets.entries()){const buttons=cards(sheet);assert.equal(buttons.filter(button=>button.children.some(child=>child.className==='shared-overlap')).length,6);for(const [rank,button] of buttons.entries()){assert.match(button.children[0].textContent,new RegExp('Inspect rank '+(rank+1)+'$'));assert.match(button['aria-label'],new RegExp('Model '+(model===0?'A':'B')+' exact checkpoint'));assert.match(button.children[3].textContent,/Cosine within this model/);assert.doesNotMatch(button.children[2].textContent,/Wrong page taxon/)} }
const first=cards(sheets[0])[0];assert.match(first.children[2].textContent,/Cohort taxon 1/);assert.match(first.children[3].textContent,/0.912/);assert.equal(first.children[1].children.length,1);assert.equal(first.children[1].children[0].textContent,'Image unavailable');
const lazy=cards(sheets[0])[1].children[1].children[1];assert.equal(lazy.loading,'lazy');assert.equal(lazy.src,'https://example.org/2.jpg');lazy.onerror();assert.equal(lazy.hidden,true);
const priorSheets=$('comparisonModels').children,priorSummary=$('comparisonSummary').textContent;$('similarMissionMode').value='other';$('similarMissionMode').onchange();assert.equal($('comparisonModels').children,priorSheets);assert.equal($('comparisonSummary').textContent,priorSummary);
"""
    run_atlas(page_photos(), checks)


def test_shared_inspection_is_fixed_to_its_model_and_does_not_change_photos_state():
    checks = "data.comparison=" + json.dumps(evidence_fixture()) + r""";
compareSelection('query');showAtlasView('models');$('workspaceReviewNote').value='Keep primary note';$('workspaceReviewNote').oninput();
const original={pair:photoPair,query:selected,rank:photoPair.rank,mode:neighborMode,hash:location.hash,view:{...view},note:$('workspaceReviewNote').value,rows:$('results').children};
const card=$('comparisonModels').children[1].children[2].children[0].children[0];card.focus();card.onclick();assert.equal($('sharedInspectionDialog').open,true);assert.equal(sharedInspection.modelIndex,1);assert.equal(sharedInspection.queryKey,'query');assert.equal(sharedInspection.rank,0);assert.equal(sharedInspection.candidates[0].key,'candidate-7');assert.equal(sharedInspection.candidates[0].score,.82345);assert.match($('sharedInspectionTitle').textContent,/Model B exact checkpoint/);assert.match($('sharedInspectionCohort').textContent,/Shared cohort: 19 frames. All missions/);assert.match($('sharedInspectionContext').textContent,/same 19 frames.*across all missions.*separate from Photos/);assert.match($('sharedQueryLabel').textContent,/Cohort query label/);assert.match($('sharedCandidateLabel').textContent,/Cohort taxon 7/);assert.equal($('sharedCandidateImage').src,'https://example.org/7.jpg');assert.match($('sharedInspectionScore').textContent,/0.823.*not calibrated across models/);assert.equal($('sharedInspectionPrevious').disabled,true);
$('sharedInspectionNext').focus();for(let i=0;i<14;i++)$('sharedInspectionNext').onclick();assert.equal(document.activeElement,$('sharedInspectionRank'));assert.equal(sharedInspection.rank,11);assert.match($('sharedInspectionRank').textContent,/Rank 12 of 12/);assert.equal($('sharedInspectionNext').disabled,true);assert.equal($('sharedInspectionChoose').disabled,true);assert.equal($('sharedCandidateKey').textContent,'candidate-18');assert.match($('sharedCandidateStatus').textContent,/Image unavailable in this atlas/);assert.equal($('sharedCandidateOriginal').hidden,true);assert.equal($('sharedCandidateImage').src,undefined);
assert.equal(photoPair,original.pair);assert.equal(photoPair.rank,original.rank);assert.equal(selected,original.query);assert.equal(neighborMode,original.mode);assert.equal(location.hash,original.hash);assert.deepEqual(view,original.view);assert.equal($('workspaceReviewNote').value,original.note);assert.equal($('results').children,original.rows);
$('sharedInspectionClose').onclick();assert.equal(sharedInspection,null);assert.equal(document.activeElement,card);card.onclick();$('sharedCandidateImage').onerror();assert.match($('sharedCandidateStatus').textContent,/Open full image to retry/);assert.equal($('sharedCandidateOriginal').href,'https://example.org/7.jpg');$('sharedInspectionChoose').onclick();assert.equal(selected,7);assert.equal(location.hash,'#frame=candidate-7');assert.equal(document.activeElement,$('modelComparisonQueryKey'));assert.equal($('sharedInspectionDialog').open,false);
"""
    run_atlas(page_photos(), checks)


def test_unlabelled_outside_and_missing_comparison_states_do_not_substitute_query():
    checks = "data.comparison=" + json.dumps(evidence_fixture(labelled=False)) + r""";
compareSelection('query');assert.match($('modelComparisonQueryLabel').textContent,/No recorded frame label/);assert.doesNotMatch($('modelComparisonQueryLabel').textContent,/Page label distractor/);
for(const sheet of $('comparisonModels').children){assert.match(sheet.children[1].textContent,/Query has no recorded frame label; same-label agreement is unavailable/);assert.doesNotMatch(sheet.children[1].textContent,/0 of/)}
data.comparison.labels_available=false;compareSelection('query');for(const sheet of $('comparisonModels').children)assert.match(sheet.children[1].textContent,/labels and same-label agreement are unavailable/);
const hash=location.hash,pair=photoPair;compareSelection('outside-request');assert.match($('modelComparisonQueryKey').textContent,/outside-request/);assert.match($('comparisonSummary').textContent,/outside the shared comparison cohort.*Both models need an embedding for the same photo/);assert.equal($('comparisonModels').children.length,0);assert.equal(openSharedInspection('outside-request',0,0),false);assert.equal(selected,0);assert.equal(photoPair,pair);assert.equal(location.hash,hash);
delete data.comparison;compareSelection('query');showAtlasView('models');assert.equal($('comparison').hidden,true);assert.equal($('modelComparisonUnavailable').hidden,false);assert.equal($('comparisonModels').children.length,0);assert.equal(openSharedInspection('query',0,0),false);
"""
    run_atlas(page_photos(), checks)


def test_shared_inspection_markup_has_no_crop_or_single_model_export_controls():
    html = runpy.run_path(ROOT / "dashboard/embedding_atlas_assets.py")["HTML"]
    dialog = html.split('<dialog id="sharedInspectionDialog"')[1].split("</dialog>")[0]
    assert "<svg" not in dialog
    assert "download" not in dialog.lower()
    assert "reviewNote" not in dialog
    assert "Full frames shown. Model input footprints may differ; Crownfirst footprint is unavailable." in dialog
    assert 'id="sharedInspectionChoose"' in dialog
    assert 'id="sharedInspectionClose" autofocus' in dialog
    css = html.split("<style>")[1].split("</style>")[0]
    assert "#comparisonModels{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr)" in css
    assert "#comparisonModels{grid-template-columns:1fr}" in css
    assert ".shared-card-image img{width:100%;height:100%;object-fit:contain}" in css
    assert ".shared-inspection-chrome{position:sticky;top:0" in css
    assert "#sharedInspectionDialog .photo-dialog-top{display:grid;grid-template-columns:minmax(0,1fr) auto" in css
    assert "top:60px" not in css

    class ChromeStructure(HTMLParser):
        def __init__(self):
            super().__init__()
            self.divs = []
            self.sticky_controls = []

        def handle_starttag(self, tag, attrs):
            attributes = dict(attrs)
            if tag == "div":
                self.divs.append(attributes.get("class", ""))
            if attributes.get("id") in ["sharedInspectionClose", "sharedInspectionPrevious", "sharedInspectionRank", "sharedInspectionNext", "sharedInspectionChoose"]:
                self.sticky_controls.append("shared-inspection-chrome" in self.divs)

        def handle_endtag(self, tag):
            if tag == "div":
                self.divs.pop()

    chrome = ChromeStructure()
    chrome.feed(dialog)
    assert chrome.sticky_controls == [True] * 5
    assert dialog.index('id="sharedInspectionContext"') > dialog.index('id="sharedCandidateImage"')



def test_real_shared_fixture_overlap_and_null_agreement():
    directory = Path(os.environ.get("BCI_ATLAS_FIXTURES", ROOT / "build"))
    fixture = directory / "embedding-comparison.json"
    if not fixture.exists():
        pytest.skip("Real atlas fixture not present; set BCI_ATLAS_FIXTURES to its build directory")
    if not shutil.which("node"):
        pytest.skip("Node is needed to execute real shared-cohort helpers")
    html = runpy.run_path(ROOT / "dashboard/embedding_atlas_assets.py")["HTML"]
    helpers = html.split("// SHARED_MODEL_HELPERS_START")[1].split("// SHARED_MODEL_HELPERS_END")[0]
    checks = r"""
const assert=require('node:assert/strict'),comparison=JSON.parse(require('node:fs').readFileSync(__FIXTURE__,'utf8'));
const labelled='comb_DJI_20240912084803_0002_V_3138zoom.JPG',unlabelled='comb_DJI_20240911144943_0004_V_1474zoom.JPG',outside='comb_DJI_20251009090859_0041_V_10603zoom.JPG';
assert.equal(sharedOverlapKeys(comparison,labelled).size,6);assert.equal(sharedOverlapKeys(comparison,unlabelled).size,5);assert.equal(sharedModelCandidates(comparison,labelled,0).length,12);assert.equal(sharedModelCandidates(comparison,labelled,1).length,12);assert.equal(sharedModelCandidates(comparison,outside,0).length,0);
const row=comparison.frames[comparison.cohort.findIndex(record=>record[0]===unlabelled)];assert.equal(row[1][0][1],null);assert.equal(row[1][1][1],null);assert.equal(sharedModelCandidates(comparison,labelled,0)[0].score,.81755);assert.equal(sharedModelCandidates(comparison,labelled,1)[0].score,.83064);
""".replace("__FIXTURE__", json.dumps(str(fixture)))
    subprocess.run(["node", "-e", helpers + checks], check=True)
