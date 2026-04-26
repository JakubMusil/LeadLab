# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 2.x | ✅ Yes |
| 1.x | ⚠️ Critical fixes only |
| < 1.0 | ❌ No |

## Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Report security issues by email to **security@leadlab.io**. You can expect an acknowledgement within **48 hours** and a triage decision within **5 business days**.

Please include:
- A description of the vulnerability and its potential impact
- Steps to reproduce or proof-of-concept code
- Any suggested mitigations

## Disclosure policy

We follow responsible disclosure:

1. You report the issue privately.
2. We confirm receipt and begin investigation.
3. We develop and test a fix.
4. We coordinate a release date with you.
5. We publish a security advisory and credit you (unless you prefer to remain anonymous).

## Security best practices for self-hosters

- Set `DEBUG = False` in production
- Use a strong, unique `SECRET_KEY`
- Keep `ALLOWED_HOSTS` restricted
- Enable HTTPS and set `SECURE_SSL_REDIRECT = True`
- Rotate database credentials regularly
- Keep dependencies up to date (`pip install -U -r requirements.txt`)
