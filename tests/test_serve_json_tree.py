"""Regression test for the JSON tree renderer in serve/static/app.js.

The renderer is browser JS, so we drive it through Node.js with a minimal
DOM stub (see tests/serve_static/test_json_tree.js). The pytest wrapper
shells out to `node` and asserts the driver exits cleanly. If `node` is
not available, the test is skipped — production CI is expected to provide
it.
"""

import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
DRIVER = REPO_ROOT / "tests" / "serve_static" / "test_json_tree.js"


@pytest.mark.skipif(
    shutil.which("node") is None,
    reason="node is not installed; skipping browser-JS regression test",
)
def test_json_tree_renderer_behavior():
    assert DRIVER.exists(), f"driver script missing: {DRIVER}"
    result = subprocess.run(
        ["node", str(DRIVER)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        pytest.fail(
            "json-tree renderer regression test failed.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    assert "All json-tree assertions passed" in result.stdout


def test_json_tree_css_classes_present_in_stylesheet():
    css_path = REPO_ROOT / "src" / "vibeval" / "serve" / "static" / "style.css"
    css = css_path.read_text(encoding="utf-8")
    for cls in (
        ".json-tree",
        ".jt-coll",
        ".jt-header",
        ".jt-toggle",
        ".jt-body",
        ".jt-row",
        ".jt-key",
        ".jt-str",
        ".jt-multiline",
        ".jt-num",
        ".jt-bool",
        ".jt-null",
    ):
        assert cls in css, f"missing CSS class definition: {cls}"
