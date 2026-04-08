# Contributing to FinXCloud

## Development Setup

```bash
git clone https://github.com/rajivdasgupta/my-first-kiro.git
cd my-first-kiro
pip install -e ".[dev,web,azure,gcp,pdf]"
```

## Running Tests

```bash
pytest
```

## Running the Linter

```bash
ruff check .
ruff format --check .
```

## Workflow

1. Create a feature branch from `main`
2. Make your changes with clear, focused commits
3. Run tests and linter before pushing
4. Open a pull request against `main`
5. Wait for review and address feedback

## Commit Messages

Use imperative mood: "Add feature" not "Added feature".
