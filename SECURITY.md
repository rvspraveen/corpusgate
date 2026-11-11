# Security policy

## Reporting a vulnerability

Please report vulnerabilities privately using GitHub's **Report a vulnerability** button (Security tab). Please don't open a public issue. We aim to reply within 5 working days.

## Scope notes

- corpusgate reads local files and never makes network calls at runtime.
- Contracts are parsed with `yaml.safe_load`. Regex patterns in contracts are run by polars' Rust regex engine, which avoids catastrophic backtracking.
- CI runs bandit, pip-audit and CodeQL, and pins third-party actions to commit SHAs.
