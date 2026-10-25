"""End-to-end browser verification (headless Chrome + Node, no npm installs).

Runs ``scripts/browser_smoke.mjs`` against a locally started server and a
temporary copy of the processed data inventory.  Skipped automatically when
Chrome, Node or processed observations are unavailable, so the unit suite stays
fast and offline-safe.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

from nisar_eim.webapp.server import create_server

REPO = Path(__file__).resolve().parents[1]
PROCESSED_ROOT = REPO / "data" / "processed"
SMOKE_SCRIPT = REPO / "scripts" / "browser_smoke.mjs"

CHROME_CANDIDATES = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)


def _chrome() -> str | None:
    import os

    for candidate in (os.environ.get("CHROME_PATH"), *CHROME_CANDIDATES):
        if candidate and Path(candidate).exists():
            return candidate
    return None


def _ready() -> tuple[bool, str]:
    if shutil.which("node") is None:
        return False, "node not on PATH"
    if _chrome() is None:
        return False, "no Chrome/Chromium found"
    if not SMOKE_SCRIPT.exists():
        return False, "scripts/browser_smoke.mjs missing"
    if not (PROCESSED_ROOT / "venezuela" / "metadata.json").exists():
        return False, "processed venezuela observation missing (run `python -m nisar_eim process`)"
    return True, ""


@pytest.mark.skipif(not _ready()[0], reason=_ready()[1])
def test_browser_smoke(tmp_path):
    observations = sorted(p.parent.name for p in PROCESSED_ROOT.glob("*/metadata.json"))
    assert len(observations) >= 1

    server = create_server("127.0.0.1", 0, PROCESSED_ROOT)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    shot = tmp_path / "explorer.png"
    try:
        proc = subprocess.run(
            ["node", str(SMOKE_SCRIPT), base, str(shot)],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,  # the return code is asserted below with full output
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        assert proc.returncode == 0, f"browser smoke failed:\n{output}"
        assert "checks passed" in output
        assert shot.exists() and shot.stat().st_size > 1000
        # every reported check must have passed
        assert "FAIL" not in output, output
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.skipif(not (PROCESSED_ROOT / "venezuela" / "metadata.json").exists(),
                    reason="processed venezuela observation missing")
def test_index_endpoint_shape_matches_frontend_expectations():
    """The exact response shape app.js consumes from /api/index."""
    server = create_server("127.0.0.1", 0, PROCESSED_ROOT)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    import urllib.request

    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urllib.request.urlopen(f"{base}/api/index", timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert isinstance(payload.get("observations"), list) and payload["observations"]
        for observation in payload["observations"]:
            # every field app.js reads without optional chaining
            assert observation["observation_id"]
            assert observation["phase"]["coverage_percent"] is not None
            assert observation["coherence"]["median"] is not None
            assert isinstance(observation["validation_states"], list)
            assert observation["validation_states"], "states must never be faked empty"
        ids = {o["observation_id"] for o in payload["observations"]}
        assert "venezuela" in ids
        assert "sample_demo" in ids
        assert isinstance(payload.get("reference_events"), list)
        assert payload.get("layer_descriptions", {}).get("phase", {}).get("units")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
