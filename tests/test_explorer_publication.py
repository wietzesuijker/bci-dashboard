"""The offline publication path includes the catalogue browser, not its raw data."""

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_publication_copies_explorer_and_promotes_it_without_raw_exports(tmp_path):
    (tmp_path / "bin").mkdir()
    (tmp_path / "dashboard").mkdir()
    build = tmp_path / "build"
    build.mkdir()
    shutil.copy2(ROOT / "bin/publish_pages.sh", tmp_path / "bin/publish_pages.sh")
    shutil.copy2(ROOT / "dashboard/build_index.py", tmp_path / "dashboard/build_index.py")
    pages = ["model_health_dashboard.html", "label_queue_dashboard.html",
             "label_queue_team.html", "explorer.html", "crownfirst-atlas.html"]
    for name in pages:
        (build / name).write_text("<!doctype html><h1>" + name + "</h1>")
    (build / "explorer.json").write_text('{"raw":true}')
    (build / "embeddings.npz").write_bytes(b"raw matrix fixture")

    subprocess.run(["bash", str(tmp_path / "bin/publish_pages.sh")], check=True,
                   capture_output=True, text=True)

    docs = tmp_path / "docs"
    for name in pages:
        assert (docs / name).read_bytes() == (build / name).read_bytes()
    assert not (docs / "explorer.json").exists()
    assert not (docs / "embeddings.npz").exists()
    index = (docs / "index.html").read_text()
    assert index.index('href="explorer.html"') < index.index('href="model_health_dashboard.html"')
