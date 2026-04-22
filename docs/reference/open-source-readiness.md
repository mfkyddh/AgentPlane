# Open Source Readiness

This repository is being shaped as a one-checkout, cross-platform open source control plane template.

## Baseline Requirements

- A single checkout works on macOS, Linux, and Windows.
- Windows can use WSL as a backend without requiring a second source checkout.
- No active docs, templates, inventory, or skills depend on maintainer-local paths.
- Default tests are offline and deterministic.
- Live WSL, Docker, SSH, and provider validation is explicit.
- Real secrets stay out of Git.
- Contributor, security, support, license, and test architecture documents are present at the repository root or under `docs/reference/`.

## Remaining Hard-Cut Work

- Retire remaining compatibility-only provider helpers once the formal CLI fully covers their use cases.
- Split the largest historical test modules into smaller domain files as behavior changes.
- Add hosted CI once the public repository is created.
- Publish a release process and versioning policy after the first public tag.

