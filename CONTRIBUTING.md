# Contributing to OpsPortal

Thank you for your interest in contributing to OpsPortal! This guide covers everything you need to get started.

## Development Setup

Clone all repositories into a shared parent directory:

```bash
mkdir opsportal-dev && cd opsportal-dev
git clone https://github.com/polprog-tech/OpsPortal.git
git clone https://github.com/polprog-tech/ReleasePilot.git
git clone https://github.com/polprog-tech/ReleaseBoard.git

pip3 install -e "./ReleasePilot[all]"
pip3 install -e ./ReleaseBoard
pip3 install -e ./OpsPortal
```

Verify the installation:

```bash
opsportal version
```

### Pre-commit hook

```bash
cd OpsPortal
cp scripts/pre-commit .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
```

## Running Tests

```bash
pytest                                    # all tests
pytest -v                                 # verbose
pytest tests/test_security.py             # specific file
pytest tests/test_security.py::TestCSP    # specific class
```

Tests follow the **GIVEN/WHEN/THEN** docstring pattern (see existing tests for examples).

## Code Quality

```bash
ruff check src/ tests/
```

## How to Contribute

### Reporting Bugs

Include: expected vs actual behavior, `opsportal.yaml` (redacted), Python/OS version, steps to reproduce.

### Pull Requests

1. Branch from `main`
2. Make changes + add tests
3. Run `pytest` and `ruff check src/ tests/`
4. Open PR with clear description

## Commit Convention

[Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`

## License

See [LICENSE](LICENSE).
