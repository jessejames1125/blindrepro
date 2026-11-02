# Contributing

1. `uv pip install -e ".[dev]"`, then `pytest`. Tests use no model and no key.
2. Keep the core free of dependencies. Packages belong in the environments the guard runs.
3. A change that touches blinding needs a test that fails without it. See `tests/test_pipeline.py`.
4. New results go in `evals/` with the rerun command, including the ones that fail.
