import math
from pathlib import Path


def test_gram_schmidt_orthonormal_basis():
    """Verify that Gram-Schmidt orthogonalization produces an orthonormal orbital basis."""
    u_raw = (0.24, -0.96, 0.14)
    v_raw = (0.35, 0.12, 0.93)

    # 1. Normalize u
    u_len = math.sqrt(sum(x * x for x in u_raw))
    u = tuple(x / u_len for x in u_raw)

    # 2. Subtract projection onto u from v, then normalize
    dot_uv_raw = sum(v_raw[i] * u[i] for i in range(3))
    v_prime = tuple(v_raw[i] - dot_uv_raw * u[i] for i in range(3))
    v_len = math.sqrt(sum(x * x for x in v_prime))
    v = tuple(x / v_len for x in v_prime)

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


def test_app_js_runtime_orbital_code_integrity():
    """Verify that app.js includes Gram-Schmidt math, honest copy, and no stale telemetry wording."""
    app_js_path = Path("src/nisar_eim/webapp/static/app.js")
    assert app_js_path.exists(), "app.js must exist"
    content = app_js_path.read_text(encoding="utf-8")

    # Gram-Schmidt implementation in app.js
    assert "Gram–Schmidt Orthonormal Orbital Basis" in content or "Gram-Schmidt" in content
    assert "dot_uv_raw" in content or "dot_uv" in content
    assert "v_prime" in content

    # Expose for runtime verification
    assert "earthController.orbitalBasis" in content

    # Explicitly illustrative copy (never misleading live telemetry)
    assert "ILLUSTRATIVE RADAR PASS · SWATH 242 KM" in content
    assert "RADAR ACQUISITION ACTIVE" not in content
