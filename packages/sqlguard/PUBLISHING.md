# Publishing sqlguard to PyPI

The package is build-verified and `twine check`-clean. Publishing needs **your**
PyPI account/token — I can't upload under your identity. Budget ~5 minutes.

## 0 — one-time: PyPI account + token
1. Create an account at **pypi.org** (and, to rehearse safely, **test.pypi.org**).
2. Account → **API tokens** → *Add API token* → scope "Entire account" (you can
   re-scope to just `sqlguard` after the first upload). Copy the `pypi-…` token.

## 1 — build (from packages/sqlguard/)
```bash
cd packages/sqlguard
python -m pip install --upgrade build twine
rm -rf dist
python -m build            # -> dist/sqlguard-0.1.0-py3-none-any.whl + .tar.gz
twine check dist/*         # must say PASSED for both
```

## 2 — (recommended) rehearse on TestPyPI
```bash
twine upload --repository testpypi dist/*
# username: __token__   password: <your test.pypi.org token>
pip install --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ sqlguard   # sqlglot from real PyPI
sqlguard check "DROP TABLE users"    # ✗ BLOCK, exit 1  -> works
```

## 3 — publish to real PyPI
```bash
twine upload dist/*
# username: __token__   password: <your pypi.org token>
```
Then verify:
```bash
pip install sqlguard
python -c "import sqlguard; print(sqlguard.__version__)"
```
`https://pypi.org/project/sqlguard/` is now live.

## After publishing — swap NexusBI off the git pin (roadmap 0.3)

NexusBI currently installs `sqlguard` from a **git tag** (so it works before PyPI
exists). Once `pip install sqlguard` works, make it a real dependency. This is
mechanical — the two spots are already commented in the code:

1. **`backend/requirements.txt`** — replace the git line with the PyPI pin:
   ```diff
   - sqlguard @ git+https://github.com/krish2105/sqlguard@v0.1.0
   + sqlguard==0.1.0
   ```
2. **`backend/Dockerfile`** — `git` was installed *only* to fetch that git pin.
   With the PyPI pin it's no longer needed; drop it from the `apt-get install` line
   (smaller image). Its comment already flags this.
3. Rebuild + verify: `docker build -t nexus-test backend && docker run --rm nexus-test`
   boots and serves `/health`; run `python -m pytest -q` to confirm the guard still
   resolves to the installed package (the dogfooding test pins this).
4. Announce with the copy in [`LAUNCH.md`](./LAUNCH.md) (HN / dev.to / X / Reddit),
   after confirming `pip install sqlguard` works in a clean venv.

## Releasing a new version
1. Bump `version` in `pyproject.toml` **and** `__version__` in `src/sqlguard/__init__.py`.
2. `python -m pytest -q` (must pass, incl. the 100%-adversarial-blocked eval).
3. `rm -rf dist && python -m build && twine check dist/*`
4. `twine upload dist/*`. PyPI versions are immutable — never reuse a number.

## Tips
- Put the token in `~/.pypirc` or `TWINE_USERNAME=__token__ TWINE_PASSWORD=pypi-…`
  so you don't paste it interactively.
- For hands-off releases later, wire **PyPI Trusted Publishing (OIDC)** to a
  GitHub Actions release workflow — no token stored anywhere.
- The name `sqlguard` was confirmed available on PyPI at build time; if someone
  claims it first, bump to `sqlguard-ai` in `pyproject.toml`'s `name` (import path
  stays `sqlguard`).
