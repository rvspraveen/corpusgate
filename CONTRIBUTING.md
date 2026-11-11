# Contributing

Thanks for helping! Small, focused PRs are easiest to review.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
ruff check . && ruff format --check .
pytest                      # coverage must stay >= 90%
bandit -q -r src
```

**Adding a check**
1. Write a factory in `src/corpusgate/checks.py` that returns `Probe` objects (a narwhals expression that counts violations).
2. Register it in `CHECKS` with its required and optional parameters.
3. Add a clean-passes / dirty-fails case to `tests/test_checks.py`.
4. Document it in the README check table and `CHANGELOG.md`.

Checks are executed through wimsey's public `wimsey.test` API, so a check factory must return a `Probe` whose expression is a narwhals aggregate and whose `max_violations` acts as the pass/fail budget.

Sample data must stay synthetic. Regenerate it with `python examples/make_samples.py`.
