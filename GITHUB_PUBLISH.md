# Publish to GitHub (`aircraft-companion-evacuation-sim`)

## PUBLISH BOUNDARY (read first)

**ONLY** this folder may be published to GitHub:

`01_research/aircraft_passenger_simulation/`

| Rule | Detail |
|------|--------|
| **NEVER** run `git` or `gh` from `personal_cloud/` root | Root has no `.git` by design; a mistaken init there would risk the whole monorepo. |
| **ONLY** use git inside this folder | Isolated `.git` lives here, not in the parent workspace. |
| **Run scope check before every push** | `python scripts/verify_publish_scope.py` (or rely on the pre-push hook below). |
| **Pre-push hook (local, once per clone)** | `git config core.hooksPath .githooks` (do **not** set globally). |

### Excluded by design (never publish)

Career, mail, reviews, finance, family, knowledge base, other research modules, patents, implementations, teaching, grants, and any secrets:

- `10_knowledge_base/`, `20_mails/`, `03_reviews/`, `90_finance/`, `91_family/`
- `00_career_management/`, `04_papers/`, `06_projects/`, `09_implementations/`, …
- `.env`, `.venv/`, credentials, local-only debug artifacts

The guard script `scripts/verify_publish_scope.py` blocks paths containing these segments or any `../` escape from this repo root.

---

Standalone public repository for the simulation code. Do **not** publish the whole `personal_cloud/` monorepo: it contains private career, mail, and review material unrelated to this study.

## Why a separate repo (not a monorepo subfolder)

- Self-contained: `requirements.txt`, portable `scripts/_paths.py` (repo root via `__file__`), default CSV outputs in `tables/`.
- No secrets: only `.env.example` (optional; no required env vars).
- Reviewers and Zenodo consumers expect a single-purpose software repo with MIT + `CITATION.cff`.

## Prerequisites (this machine, 2026-07-15)

- [Git for Windows](https://git-scm.com/download/win)
- [GitHub CLI](https://cli.github.com/)
- Then: `gh auth login` (HTTPS or SSH).

Replace `GITHUB_USER` with your GitHub username (or org).

## One-time: enable publish guard (local)

Open PowerShell **in this folder only**:

`personal_cloud/01_research/aircraft_passenger_simulation/`

```powershell
git config core.hooksPath .githooks
python scripts/verify_publish_scope.py
python scripts/verify_publish_scope.py --staged
```

The pre-push hook runs `verify_publish_scope.py` automatically. Re-run the script manually before any push if hooks are disabled.

## One-time: init from workspace copy

```powershell
# Confirm .venv is NOT tracked
git status

git add .gitignore LICENSE CITATION.cff README.md GITHUB_PUBLISH.md requirements.txt .env.example
git add scripts .githooks tables figures
# data/ is optional (empty placeholder); add if you create inputs later

python scripts/verify_publish_scope.py --staged
git commit -m "Initial public release: aircraft cabin evacuation simulation v0.1.0"
python scripts/verify_publish_scope.py
```

Verify before commit:

```powershell
git status
# must NOT list .venv/, .env, __pycache__/
Select-String -Path scripts\*.py -Pattern "C:\\Users","OneDrive" -SimpleMatch
# expect no matches
```

## Create GitHub repo and push

```powershell
python scripts/verify_publish_scope.py
gh repo create aircraft-companion-evacuation-sim --public --source=. --remote=origin --push --description "Agent-based narrow-body cabin evacuation: companion separation scenarios (v0)"
```

If the repo already exists on GitHub (empty):

```powershell
python scripts/verify_publish_scope.py
git remote add origin https://github.com/GITHUB_USER/aircraft-companion-evacuation-sim.git
git branch -M main
git push -u origin main
```

## After push: metadata sync

1. Set `repository-code` in `CITATION.cff` to the real URL (e.g. `https://github.com/GITHUB_USER/aircraft-companion-evacuation-sim`).
2. Commit and push: `python scripts/verify_publish_scope.py --staged` then `git add CITATION.cff && git commit -m "Set repository-code in CITATION.cff" && python scripts/verify_publish_scope.py && git push`.
3. Update the companion paper:
   - `04_papers/journal_articles/2026/separate_passengers_aircraft_safety/presubmission/processed/data_availability_draft.md`
   - `04_papers/journal_articles/2026/separate_passengers_aircraft_safety/README.md` (code link section)

## Suggested release tag

```powershell
python scripts/verify_publish_scope.py
git tag -a v0.1.0 -m "Default experiment set, seed 1, tables bundled"
git push origin v0.1.0
```

## Reproduce headline results (reviewers)

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python scripts\run_all.py --seed 1 --plots
.\.venv\Scripts\python scripts\run_sensitivity.py --seed 1
```

Bundled CSVs in `tables/` match seed base 1 from the companion manuscript draft.
