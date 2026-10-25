"""Static frontend regression tests.

These guard the actual bug that broke the Observation Explorer: an id
(``open-explorer``) that was *used* by ``app.js`` but never looked up, so the
first ``addEventListener`` threw and every later binding - tabs, select,
threshold, map, ``/api/index`` - silently never ran.  The page then stayed on
the static "connecting…" pill with no observation cards.

No browser is required here; ``tests/test_browser_smoke.py`` exercises the real
controls in headless Chrome when it is available.
"""

from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "src" / "nisar_eim" / "webapp" / "static"


def _html() -> str:
    return (STATIC / "index.html").read_text(encoding="utf-8")


def _js() -> str:
    return (STATIC / "app.js").read_text(encoding="utf-8")


def _css() -> str:
    return (STATIC / "styles.css").read_text(encoding="utf-8")


def _html_ids() -> set[str]:
    return set(re.findall(r'\bid="([^"]+)"', _html()))


def _js_referenced_ids() -> set[str]:
    js = _js()
    ids: set[str] = set()
    block = re.search(r"const ELEMENT_IDS = \[(.*?)\];", js, re.DOTALL)
    assert block, "app.js must declare its ELEMENT_IDS lookup list"
    ids.update(re.findall(r'"([^"]+)"', block.group(1)))
    ids.update(re.findall(r'getElementById\(\s*"([^"]+)"\s*\)', js))
    ids.update(re.findall(r'querySelector\(\s*"#([A-Za-z][\w-]*)"', js))
    return ids


def test_every_id_used_by_app_js_exists_in_index_html():
    """The exact recurrence of the original bug: used-but-never-looked-up id."""
    html_ids = _html_ids()
    missing = sorted(_js_referenced_ids() - html_ids)
    assert not missing, f"app.js references ids that do not exist in index.html: {missing}"


def test_els_references_are_all_registered_at_boot():
    """``els["x"]`` is undefined unless "x" is in ELEMENT_IDS — the exact
    shape of the original crash (els["open-explorer"] was never looked up)."""
    js = _js()
    block = re.search(r"const ELEMENT_IDS = \[(.*?)\];", js, re.DOTALL).group(1)
    registered = set(re.findall(r'"([^"]+)"', block))
    used = set(re.findall(r'els\["([^"]+)"\]', js))
    missing = sorted(used - registered)
    assert not missing, (
        f"app.js reads els[...] for ids that ELEMENT_IDS never looks up: {missing}"
    )


def test_critical_controls_are_registered():
    block = re.search(r"const ELEMENT_IDS = \[(.*?)\];", _js(), re.DOTALL).group(1)
    registered = set(re.findall(r'"([^"]+)"', block))
    for control in ("server-status", "observation-cards", "open-explorer", "map-canvas"):
        assert control in registered, f"#{control} must be registered during boot"


def test_navigation_binds_before_any_network_call():
    js = _js()
    boot = re.search(r"document\.addEventListener\(\s*\"DOMContentLoaded\",(.*?)\n\}\);", js, re.DOTALL)
    assert boot, "app.js must initialize on DOMContentLoaded"
    body = boot.group(1)
    assert "bindNavigation()" in body
    assert body.index("bindNavigation()") < body.index("loadIndex()"), (
        "navigation must be wired before the first API request so a failing "
        "network call cannot disable the view switch"
    )
    # isolated binding steps so one failure cannot abort the whole boot
    assert "for (const [name, bind] of steps)" in body
    assert 'console.error(`[boot] missing control #${id}' in body


def test_navigation_controls_exist_and_are_buttons():
    html = _html()
    tabs = re.findall(r'<button class="view-tab[^"]*" data-view="(\w+)"', html)
    assert tabs == ["dashboard", "explorer"]
    # native buttons give keyboard activation (Enter/Space) for free
    assert 'id="open-explorer"' in html
    assert re.search(r'<button class="button primary" id="open-explorer">', html)
    for tab in re.findall(r"<button[^>]*class=\"view-tab[^\"]*\"[^>]*>", html):
        assert "<button" in tab and 'role="tab"' in tab


def test_status_indicator_has_all_three_states():
    html = _html()
    js = _js()
    assert 'id="server-status"' in html
    assert 'data-state="connecting"' in html  # honest default before the check runs
    assert "function setServerStatus(state" in js
    for state in ("connecting", "connected", "unavailable"):
        assert f'"{state}"' in js, f"status state '{state}' is not implemented"
    # "connected" may only be set after /api/index resolved successfully
    load_index = re.search(r"async function loadIndex\(\) \{(.*?)\n\}", js, re.DOTALL).group(1)
    assert load_index.index('setServerStatus("connected")') > load_index.index("await api(")
    assert 'setServerStatus("unavailable")' in load_index


def test_api_failure_path_is_recoverable():
    js = _js()
    assert "function renderIndexError(error)" in js
    assert "[data-retry]" in js and "Retry connection" in js
    # an unreachable API must still leave the empty/error state visible
    assert 'setServerStatus("unavailable")' in js


def test_missing_observation_reports_an_understandable_error():
    js = _js()
    open_observation = re.search(r"async function openObservation\(.*?\n\}", js, re.DOTALL).group(0)
    assert "catch (error)" in open_observation
    assert "Could not open" in open_observation
    assert "setMapHint(" in open_observation


def test_toast_cannot_block_clicks():
    """An overlay must never swallow clicks meant for the page underneath."""
    css = _css()
    toast = re.search(r"\.toast \{(.*?)\}", css, re.DOTALL).group(1)
    assert "pointer-events: none" in toast
    hint = re.search(r"\.map-hint \{(.*?)\}", css, re.DOTALL).group(1)
    assert "pointer-events: none" in hint


def test_observation_cards_render_responsive_and_badge_semantics():
    """Verify that observation cards have responsive grid styling, copy actions, and distinct badges."""
    js = _js()
    css = _css()

    # Cards layout uses modern responsive auto-fit grid
    assert "repeat(auto-fit, minmax(min(100%," in css
    assert "min-width: 0" in css

    # Badges for REAL and SAMPLE are distinctly rendered in observationCard
    assert "badge-real" in js and "badge-sample" in js
    assert "REAL NISAR" in js and "SAMPLE DATA" in js

    # Card includes date hero strip, metrics grid, and granule box
    assert "card-dates-hero" in js
    assert "card-metrics-grid" in js
    assert "card-granule-box" in js

    # Copy ID action exists and is keyboard accessible button
    assert "data-copy-granule" in js
    assert "Copy ID" in js
    assert "copyToClipboard" in js
    assert "btn-copy" in css
    assert ".granule-id-text" in css

    # Long identifier wrap safety
    assert "word-break: break-all" in css
    assert "overflow-wrap: anywhere" in css

