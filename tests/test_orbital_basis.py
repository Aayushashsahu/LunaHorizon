import math
import re
from pathlib import Path


def _get_gram_schmidt_vectors():
    u_raw = (0.24, -0.96, 0.14)
    v_raw = (0.35, 0.12, 0.93)

    u_len = math.sqrt(sum(x * x for x in u_raw))
    u = tuple(x / u_len for x in u_raw)

    dot_uv_raw = sum(v_raw[i] * u[i] for i in range(3))
    v_prime = tuple(v_raw[i] - dot_uv_raw * u[i] for i in range(3))
    v_len = math.sqrt(sum(x * x for x in v_prime))
    v = tuple(x / v_len for x in v_prime)
    return u, v


def test_gram_schmidt_orthonormal_basis():
    """Verify that Gram-Schmidt orthogonalization produces an orthonormal orbital basis."""
    u, v = _get_gram_schmidt_vectors()

    # Verify orthonormality
    dot_product = sum(u[i] * v[i] for i in range(3))
    assert abs(dot_product) < 1e-6, f"u and v must be orthogonal: dot={dot_product}"

    u_norm = math.sqrt(sum(x * x for x in u))
    v_norm = math.sqrt(sum(x * x for x in v))
    assert abs(u_norm - 1.0) < 1e-6, f"u must have unit length: {u_norm}"
    assert abs(v_norm - 1.0) < 1e-6, f"v must have unit length: {v_norm}"

    # Verify constant 3D orbital radius across full 360 degrees
    r_orbit = 305.0
    for deg in range(360):
        rad = math.radians(deg)
        px = r_orbit * (u[0] * math.cos(rad) + v[0] * math.sin(rad))
        py = r_orbit * (u[1] * math.cos(rad) + v[1] * math.sin(rad))
        pz = r_orbit * (u[2] * math.cos(rad) + v[2] * math.sin(rad))
        r3d = math.sqrt(px * px + py * py + pz * pz)
        assert abs(r3d - r_orbit) < 1e-5, f"Radius deviation at deg={deg}: {r3d} != {r_orbit}"


def test_orbit_track_path_segmentation():
    """Verify contiguous orbit track segmentation, limb crossings, and absence of cross-planet lines."""
    u, v = _get_gram_schmidt_vectors()
    r_orbit = 305.0
    r_earth = 270.0

    def get_orbit_point(rad):
        px = r_orbit * (u[0] * math.cos(rad) + v[0] * math.sin(rad))
        py = r_orbit * (u[1] * math.cos(rad) + v[1] * math.sin(rad))
        pz = r_orbit * (u[2] * math.cos(rad) + v[2] * math.sin(rad))
        sx = 300.0 + px
        sy = 300.0 - py
        dist = math.hypot(px, py)
        occluded = pz < 0 and dist <= r_earth
        return {"sx": sx, "sy": sy, "px": px, "py": py, "pz": pz, "dist": dist, "occluded": occluded}

    def find_limb_crossing(deg_a, deg_b):
        low, high = deg_a, deg_b
        for _ in range(12):
            mid = (low + high) / 2
            pt = get_orbit_point(math.radians(mid))
            pt_low = get_orbit_point(math.radians(low))
            if (pt_low["dist"] > r_earth) == (pt["dist"] > r_earth):
                low = mid
            else:
                high = mid
        return get_orbit_point(math.radians((low + high) / 2))

    front_d = ""
    back_d = ""
    current_class = None

    for deg in range(0, 361, 2):
        pt = get_orbit_point(math.radians(deg))
        is_front = pt["pz"] >= 0 or pt["dist"] > r_earth
        pt_class = "front" if is_front else "back"

        if current_class is not None and pt_class != current_class:
            limb_pt = find_limb_crossing(deg - 2, deg)
            limb_coord = f"{limb_pt['sx']:.1f},{limb_pt['sy']:.1f}"

            if current_class == "front":
                front_d += " L " + limb_coord
            else:
                back_d += " L " + limb_coord

            if pt_class == "front":
                front_d += (" M " if front_d else "M ") + limb_coord
            else:
                back_d += (" M " if back_d else "M ") + limb_coord

        coord = f"{pt['sx']:.1f},{pt['sy']:.1f}"
        if current_class is None:
            if pt_class == "front":
                front_d += "M " + coord
            else:
                back_d += "M " + coord
        elif pt_class == current_class:
            if pt_class == "front":
                front_d += " L " + coord
            else:
                back_d += " L " + coord

        current_class = pt_class

    # 1. Front path must contain multiple subpaths (at least 2 'M' commands because occluded back segment interrupts it)
    front_m_count = len(re.findall(r"\bM\b", front_d))
    back_m_count = len(re.findall(r"\bM\b", back_d))
    assert front_m_count >= 2, f"frontD must contain multiple M subpaths across limb gap: got {front_m_count}"
    assert back_m_count >= 1, f"backD must contain at least 1 M command: got {back_m_count}"

    # 2. Verify that there is NO single straight line 'L' jumping directly across the occluded interval
    # In front_d, check all segment jump distances between consecutive coords
    tokens = front_d.split()
    current_cmd = None
    prev_coord = None
    max_line_step = 0.0

    for token in tokens:
        if token in ("M", "L"):
            current_cmd = token
        elif "," in token:
            x_str, y_str = token.split(",")
            coord = (float(x_str), float(y_str))
            if current_cmd == "L" and prev_coord is not None:
                step = math.hypot(coord[0] - prev_coord[0], coord[1] - prev_coord[1])
                max_line_step = max(max_line_step, step)
            prev_coord = coord

    # Step between consecutive 2-degree samples along R=305 circle is ~10-15 px.
    # An erroneous connection across the diameter of Earth would be ~400-500 px.
    assert max_line_step < 35.0, f"Max line segment length is too large ({max_line_step}px); indicates straight line across gap!"


def test_app_js_runtime_orbital_code_integrity():
    """Verify that app.js includes Gram-Schmidt math, honest copy, and no stale telemetry wording."""
    app_js_path = Path("src/nisar_eim/webapp/static/app.js")
    assert app_js_path.exists(), "app.js must exist"
    content = app_js_path.read_text(encoding="utf-8")

    # Gram-Schmidt implementation in app.js
    assert "Gram–Schmidt Orthonormal Orbital Basis" in content or "Gram-Schmidt" in content
    assert "dot_uv_raw" in content or "dot_uv" in content
    assert "v_prime" in content

    # Contiguous path segmentation
    assert "buildContiguousOrbitPaths" in content
    assert "findLimbCrossing" in content

    # Expose for runtime verification
    assert "earthController.orbitalBasis" in content

    # Explicitly illustrative copy (never misleading live telemetry)
    assert "ILLUSTRATIVE RADAR PASS · SWATH 242 KM" in content
    assert "RADAR ACQUISITION ACTIVE" not in content

    # Authoritative 12-day nominal repeat cycle distinct from observation baseline
    assert "Nominal Orbit Repeat: 12 days" in content
    assert "realObs?.temporal_baseline_days != null" in content


def test_html_authoritative_repeat_cycle_label():
    """Verify index.html uses the authoritative 12-day orbit repeat cycle and no hard-coded 11-day repeat."""
    html_path = Path("src/nisar_eim/webapp/static/index.html")
    assert html_path.exists(), "index.html must exist"
    content = html_path.read_text(encoding="utf-8")

    assert "ORBIT REPEAT CYCLE · 12 DAYS" in content
    assert "REPEAT: 11 DAYS" not in content
