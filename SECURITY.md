# Security Policy

## Supported Versions

Security fixes target the current `main` branch until formal releases are introduced.

## Reporting A Vulnerability

Please avoid publishing sensitive details before maintainers have a chance to investigate. Open a private security advisory when the hosting platform supports it, or contact the maintainers through the repository's published contact channel.

Never include real credentials, private keys, production hostnames, or live target inventory in a public report. Use redacted examples and attach exact reproduction steps.

## Secret Handling

AgentPlane treats `secrets/` as local-only material. Public examples belong under `templates/`; tests should generate temporary secrets instead of committing real values.

