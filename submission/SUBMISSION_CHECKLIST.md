# Submission Checklist — NISAR // Earth in Motion

**Challenge:** NASA Space Apps Challenge 2026 — Dancing with the SARs  
**Repository:** <https://github.com/Aayushashsahu/LunaHorizon>

> **Note:** The official 2026 submission window and portal URL should be verified at <https://www.spaceappschallenge.org/>. The checklist below reflects requirements typical of NASA Space Apps Challenge submissions; verify against the current official requirements before final submission.

---

## Category: Repository Requirements

| Item | Status | Notes |
|---|---|---|
| Public GitHub repository | ✅ Complete | <https://github.com/Aayushashsahu/LunaHorizon> |
| Repository is public (not private) | ✅ Verified | Accessible without authentication |
| Open-source license | ✅ MIT | `LICENSE` — GitHub detects as `mit` |
| Third-party attribution | ✅ Complete | `THIRD_PARTY_NOTICES.md` |
| No committed secrets or credentials | ✅ Verified | `.gitignore` excludes `.env`, `.netrc`, `*.pem`, `*.key` |
| No committed raw HDF5 data | ✅ Verified | `data/raw/` is gitignored |
| Working application (offline) | ✅ Verified | `python -m nisar_eim serve --port 8000` |
| Reproducible installation | ✅ Verified | `pip install -e ".[dev]"; pytest -v` (93 tests pass) |

---

## Category: Project Documentation

| Item | Status | Notes |
|---|---|---|
| README with project description | ✅ Complete | Root `README.md` |
| Architecture documentation | ✅ Complete | `docs/ARCHITECTURE.md` |
| Scientific methodology | ✅ Complete | `docs/SCIENTIFIC_METHOD.md` |
| Data validation records | ✅ Complete | `docs/DATA_VALIDATION.md` |
| Contributing guide | ✅ Complete | `CONTRIBUTING.md` |
| Security policy | ✅ Complete | `SECURITY.md` |
| Citation file | ✅ Complete | `CITATION.cff` (CFF 1.2.0 format) |
| Release notes | ✅ Complete | `docs/RELEASE_NOTES_v0.1.0.md` |
| Final audit report | ✅ Complete | `docs/FINAL_COMPLETION_AUDIT.md` |

---

## Category: Submission Materials

| Item | Status | Notes |
|---|---|---|
| Project submission narrative | ✅ Complete | `submission/PROJECT_SUBMISSION.md` |
| Demo video script | ✅ Complete | `submission/DEMO_VIDEO_SCRIPT.md` |
| Judge quickstart guide | ✅ Complete | `submission/JUDGE_QUICKSTART.md` |
| Submission checklist | ✅ This file | `submission/SUBMISSION_CHECKLIST.md` |
| Demo video recording | ⚠️ Pending | Script prepared; recording requires manual capture |
| YouTube / video URL | ⚠️ Pending | To be completed when video is recorded |
| Screenshots (≥3) | ✅ Available | `docs/images/` (4 screenshots committed) |

---

## Category: Scientific Integrity

| Item | Status | Notes |
|---|---|---|
| Phase displayed in radians (not displacement) | ✅ Verified | All UI labels and reports use radians |
| Coherence not described as damage | ✅ Verified | UI uses "measurement quality" language |
| `scientific_interpretation_validated = false` | ✅ Verified | Confirmed in `data/processed/venezuela/metadata.json` |
| NASA comparison documented | ✅ Complete | `research/NASA_VENEZUELA_REFERENCE_ANALYSIS.md` |
| Earthquake events from USGS | ✅ Verified | ComCat event IDs `us6000t7zc` and `us6000t7zp` |
| Sample dataset clearly labeled | ✅ Verified | `sample_demo` explicitly tagged as pre-launch sample |

---

## Category: CI and Quality

| Item | Status | Notes |
|---|---|---|
| GitHub Actions CI | ✅ Green | Python 3.11 and 3.12 matrix |
| Ruff lint (mandatory, not `continue-on-error`) | ✅ Fixed | `ci.yml` updated 2026-11-01 |
| Ruff: all checks passed | ✅ Verified | Exit code 0 locally |
| 93 pytest tests passing | ✅ Verified | Python 3.11 locally, Python 3.11 + 3.12 on CI |
| JS syntax check | ✅ Added to CI | `node --check app.js; node --check scripts/*.mjs` |
| Dependabot enabled | ✅ Active | `.github/dependabot.yml` |
| Dependabot PRs merged | ✅ Complete | `actions/setup-python@v7`, `actions/checkout@v7` |
| `*.egg-info/` removed from git | ✅ Fixed | Also added to `.gitignore` |

---

## Category: GitHub Release

| Item | Status | Notes |
|---|---|---|
| Release tag exists | ✅ `v0.1.0` | <https://github.com/Aayushashsahu/LunaHorizon/releases/tag/v0.1.0> |
| Release marked as prerelease | ✅ Fixed | `isPrerelease: true` |
| Release name matches status | ✅ | "v0.1.0 — NASA Space Apps 2026 Release Candidate" |
| Release notes exist | ✅ | `docs/RELEASE_NOTES_v0.1.0.md` |

---

## Category: Manual Actions Remaining

These items require direct action by the submitter and cannot be automated:

| Action | Priority | Description |
|---|---|---|
| Record demo video | **HIGH** | Follow `submission/DEMO_VIDEO_SCRIPT.md`; record with OBS Studio or QuickTime |
| Upload video to YouTube | **HIGH** | Set as Unlisted; paste URL in submission portal |
| Complete submission portal | **HIGH** | Log in to <https://www.spaceappschallenge.org/> and fill in all required fields |
| Verify current submission deadline | **HIGH** | Confirm the exact submission window from the official site |
| Add team members | If applicable | Add any additional team members to the submission |
| Submit to portal | **FINAL** | Click submit on the Space Apps portal before the deadline |

---

## Final Repository SHA

The repository commit at the time this checklist was last updated:

To obtain the current SHA:
```bash
git rev-parse HEAD
```

Update this field with the SHA at final submission time.

---

## Submission Portal Checklist (Standard Space Apps Fields)

These are the fields typically required in the NASA Space Apps submission portal. Verify against the current portal UI:

- [ ] Project title: `NISAR // Earth in Motion`
- [ ] Short description (150–300 characters)
- [ ] Challenge: `Dancing with the SARs`
- [ ] Project URL (GitHub): `https://github.com/Aayushashsahu/LunaHorizon`
- [ ] Demo video URL (YouTube)
- [ ] Team / participant name(s)
- [ ] Location / country
- [ ] Project description (long form)
- [ ] Data sources used
- [ ] Tools and technologies
- [ ] Screenshots (up to 5)
- [ ] Team profile(s)

---

*Last updated: 2026-11-01*
