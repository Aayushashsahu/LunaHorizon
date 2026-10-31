# Contributing to NISAR // Earth in Motion

Thank you for your interest in contributing to **NISAR // Earth in Motion**! This project was created for the NASA International Space Apps Challenge 2026 (*Dancing with the SARs*) to turn complex synthetic aperture radar (SAR) interferometry products into accessible, scientifically honest Earth observation tools.

---

## Code of Conduct

We are committed to providing a welcoming, inclusive, and harassment-free environment for everyone. Please treat all contributors with respect, patience, and consideration.

---

## Development Setup

### 1. Prerequisites
- Python 3.11 or higher
- Git
- Node.js 18+ (optional, only needed for headless browser smoke tests)

### 2. Fork and Clone
```bash
git clone https://github.com/Aayushashsahu/LunaHorizon.git
cd LunaHorizon
```

### 3. Virtual Environment
**Windows PowerShell:**
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

**macOS / Linux:**
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

---

## Running Tests

Before submitting any code changes, ensure all automated tests and linters pass:

```bash
# Run full pytest suite (93 unit & regression tests)
pytest -v

# Run the Ruff linter
ruff check src tests

# Run browser E2E smoke tests (requires Node.js and Google Chrome)
node scripts/browser_smoke.mjs http://127.0.0.1:8000
```

---

## Scientific Guidelines

1. **Units & Terminology:**
   * Unwrapped phase must always be documented in **radians**.
   * Coherence must be treated as an interferometric quality and correlation metric (0.0 to 1.0), never as a displacement measurement.
   * Do not implement arbitrary phase-to-displacement conversions without formal sign-convention documentation, incidence angles, and independent ground-truth validation.

2. **Geospatial Integrity:**
   * Always resolve coordinate vectors from attached HDF5 dimension scales rather than file-wide basename lookups.
   * Coordinate reference systems (CRS) must be extracted from the product's own grid mapping metadata (`EPSG:32619`, etc.).

3. **No Fabricated Data:**
   * Never invent mock data or claim earthquake causation without peer-reviewed ground-truth evidence.

---

## Pull Request Process

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Write clean, readable code with descriptive commit messages.
3. Add unit tests for new functionality under `tests/`.
4. Ensure all tests pass (`pytest` and `ruff check`).
5. Open a Pull Request targeting `main` with a clear explanation of what changed and why.
