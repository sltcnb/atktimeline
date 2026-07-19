# Contributing

Thanks for your interest in improving ATK Timeline.

## Development setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt ruff pytest
export FLASK_APP=app.py SECRET_KEY=dev SESSION_COOKIE_SECURE=0
flask init-db
flask create-user --username admin --email admin@example.com --password changeme
flask run
```

## Before opening a pull request

- Run the linter: `ruff check .`
- Run the formatter: `ruff format .`
- Run the tests: `pytest`
- Install the git hooks once with `pre-commit install` so checks run automatically.

## Guidelines

- Keep changes focused and describe the motivation in the PR body.
- Follow [Conventional Commits](https://www.conventionalcommits.org/) for commit messages.
- Never commit secrets. `.env` and `config.json` are gitignored; use `.env.example` as a template.
- Add or update tests when you change behaviour.
