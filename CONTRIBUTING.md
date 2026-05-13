# Contributing

Thanks for considering a contribution!

## Quick dev setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# run the app (auto-reload)
uvicorn backend.main:app --reload --port 8000

# run the test suite
pytest -q
ruff check backend tests scripts
```

## Workflow

1. Open an issue describing the change before sending a large PR.
2. Branch off `main`. Keep PRs focused — one concern per branch.
3. Add or update tests for any behavior change. New endpoints need API tests.
4. Run `pytest` + `ruff check` locally; CI must be green.
5. Update `README.md` if you change behavior, env vars, or the API.

## Code style

- Python: ruff (settings in `pyproject.toml`), built-in typing aliases, `from __future__ import annotations`.
- JS: ES2019, no build step. Keep modules small and named — `app.js`, `i18n.js`, `visualizers.js`.
- CSS: single design-system file; reuse the `--*` custom properties rather than hard-coding colors.
- Korean strings live in `frontend/js/i18n.js` only; English strings live there too.
- Never log raw filenames or audio bytes; use the request_id.

## Security & data handling

- We never persist user audio. Any new code path that writes a file must add it to a `finally` cleanup or a `BackgroundTasks` task.
- Don't add new external network calls without a clear reason and CSP update.
- Don't widen CORS without an env-var-driven config.

## Reporting security issues

Please email security concerns privately to the repo owner instead of opening a public issue.
