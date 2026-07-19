# Security Policy

## Reporting a vulnerability

Please report security issues privately rather than opening a public issue.
Use GitHub's [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
for this repository, or contact the maintainers directly.

We aim to acknowledge reports within a few days and will coordinate a fix and
disclosure timeline with you.

## Deployment hardening checklist

- Set a strong, unique `SECRET_KEY` (e.g. `python -c "import secrets; print(secrets.token_hex(32))"`).
- Never commit `.env` or `config.json`; both are gitignored.
- Serve the app over HTTPS. `SESSION_COOKIE_SECURE` is enabled by default and
  should only be disabled (`SESSION_COOKIE_SECURE=0`) for local plain-HTTP dev.
- Registration is disabled by design; create accounts only via the
  `flask create-user` CLI command.
- Keep dependencies patched.
