"""Build the self-contained spatial representation explorer, using stdlib only."""

import argparse
import json
import runpy
from pathlib import Path


def build(source, output):
    data = json.loads(Path(source).read_text())
    template = runpy.run_path(str(Path(__file__).with_name("embedding_atlas_assets.py")))["HTML"]
    payload = json.dumps(data, separators=(",", ":"), allow_nan=False).replace(
        "<", "\\u003c"
    )
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(template.replace("__ATLAS_DATA__", payload))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="build/embedding-atlas.json")
    parser.add_argument("--output", default="build/embedding-atlas.html")
    args = parser.parse_args()
    build(args.input, args.output)
