# CLI-First Unified Governance Roadmap

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the CLI-first convergence work so `wsl`、`prod0-main`、`prod2-main` and all tracked host resources, runtime services, public websites, app contracts, app resources, projections, and local repositories can be managed through one formal OP_Linux control surface, with standard onboarding and offboarding for future projects.

**Architecture:** Keep the already-landed CLI-first public domains as the stable outer contract, and spend the next work in five large phases: harden formal contracts, harden app delivery, equalize host governance across the three formal targets, formalize automation and projection follow-through, then standardize project onboarding/offboarding. Do not add new compat-first surfaces. Do not expand review loops inside a phase; each phase closes on focused contract tests, readonly smoke checks, or dry-run plans only.

**Tech Stack:** Python CLI under `ops/cli`, domain handlers under `ops/domain`, tracked host truth in `inventory/servers`, app truth in `inventory/apps` plus app-side `deploy/op/contract.yaml`, runbooks and reference docs in `docs/`, repo self-check in `ops/scripts/internal/repo/self_check.sh`, pytest contract suites.

---

## Summary

Current repository state already proves these surfaces are mostly formalized:

- `host / service / website / projection / app object / app resource` are already CLI-first public surfaces.
- `app delivery` exists, but still lacks rollback-state hard guarantees and still bridges some old substrate.
- `wsl`、`prod0-main`、`prod2-main` are the real formal targets.
- `self_check` is already the stable daily thin gate and should stay thin.
- naming registry, compat retirement, and long-term doc lifecycle metadata exist as docs but are not yet fully enforced.

This roadmap intentionally reduces low-value review:

- No stage-internal broad review.
- No file-by-file approval loop.
- Only one integration acceptance at the end of each phase.
- Only smallest relevant verification for the phase.
- Live production verification stays readonly unless a phase explicitly needs a dry-run or plan output.

## Fixed Parallel Execution Model

Every phase uses the same 12 subagent lanes. Each lane owns one bounded slice and must avoid writing outside that slice unless the phase explicitly says otherwise.

| Lane | Ownership |
| --- | --- |
| Lane 1 | CLI parser, command contracts, shared argparse/help surfaces |
| Lane 2 | `app delivery` formal behavior and rollback-state |
| Lane 3 | `app object` / `app resource` / naming / catalog alignment |
| Lane 4 | `service` registry and runtime inventory alignment |
| Lane 5 | `website` registry / publish / ingress contract alignment |
| Lane 6 | `projection` runtime-env / verification / fixture / ledger |
| Lane 7 | `wsl` host governance |
| Lane 8 | `prod0-main` host governance |
| Lane 9 | `prod2-main` host governance |
| Lane 10 | host-first secrets truth and projection compatibility |
| Lane 11 | docs / reference / compat ledger / self-check |
| Lane 12 | integration tests / acceptance / release notes for the phase |

## Phase 1: Hard-Enforce The Formal Contract Layer

**Outcome:** turn existing reference docs and CLI-first claims into hard repo contracts; remove active compat-default wording; keep self-check thin.

**Files:**
- Modify: `README.md`
- Modify: `docs/reference/compat-retirement-ledger.md`
- Modify: `docs/reference/control-plane-naming-registry.md`
- Modify: `docs/maintainers/control-plane-authoring.md`
- Modify: `docs/runbooks/control-plane-agent-execution-flow.md`
- Modify: `docs/runbooks/app-project-delivery-workflow.md`
- Modify: `docs/runbooks/wsl-host-governance.md`
- Modify: `ops/scripts/internal/repo/self_check.sh`
- Modify: `tests/test_app_onboarding_standard.py`
- Modify: `tests/test_docs_no_legacy_terms.py`
- Modify: `tests/test_repo_snapshot_contracts.py`

- [ ] **Lane 1:** freeze the public CLI surface vocabulary and remove any active-doc wording that still re-promotes compat or legacy object names as defaults.
- [ ] **Lane 2:** add contract tests proving `app delivery validate-contract` is the earliest formal gate for app onboarding invariants, not deploy time.
- [ ] **Lane 3:** encode minimum naming invariants into tests and formal contract expectations for `app_id`、`service_key`、image family、`-prod`、`-dev`.
- [ ] **Lane 4:** verify `service` docs and tests only point to inventory-backed tracked service objects, not raw 1Panel ids.
- [ ] **Lane 5:** verify `website` docs and tests only point to `website` / `website publish` as the formal ingress surface.
- [ ] **Lane 6:** keep `projection` in the thin contract gate only through docs and focused tests; do not add live verification to daily self-check.
- [ ] **Lane 7:** remove active-layer WSL doc duplication and historical path leakage that increases review cost.
- [ ] **Lane 8:** align `prod0-main` active docs with current readonly/precheck posture without reintroducing compat-default wording.
- [ ] **Lane 9:** align `prod2-main` active docs with current active production validation posture without reviving old object surfaces.
- [ ] **Lane 10:** standardize host-first secrets wording so truth lives under `secrets/hosts/<target>/...`, with legacy projections clearly marked as projections only.
- [ ] **Lane 11:** keep `self_check` as the single daily gate and restrict it to stable, fast contract suites.
- [ ] **Lane 12:** run phase acceptance and produce one concise integration summary; do not request another broad review unless acceptance fails.

**Phase Exit Criteria:**
- active docs no longer present compat entrypoints as defaults
- naming registry fields are enforceable by test and ready for CLI validation
- long-lived docs have a standard metadata policy
- `self_check` remains one thin gate

**Minimal Verification:**

```bash
cd /root/work/OP_Linux
uv run pytest tests/test_app_onboarding_standard.py tests/test_docs_no_legacy_terms.py tests/test_repo_snapshot_contracts.py -q
bash ops/scripts/internal/repo/self_check.sh
```

## Phase 2: Harden `app delivery` Into A Real Formal Deployment Surface

**Outcome:** remove the largest remaining non-formal behavior gap by enforcing rollback-state and shifting validation failures earlier.

**Files:**
- Modify: `ops/cli/apps.py`
- Modify: `ops/domain/app/catalog.py`
- Modify: `ops/domain/app/delivery_handlers.py`
- Modify: `ops/domain/app/resource_registry.py`
- Modify: `docs/architecture/op-linux-app-collaboration.md`
- Modify: `docs/runbooks/app-project-delivery-workflow.md`
- Modify: `tests/test_app_cli.py`
- Modify: `tests/test_app_resource_cli.py`

- [ ] **Lane 1:** tighten parser-level action contracts for `validate-contract / deploy / verify / rollback / inventory-refresh / doc-sync`.
- [ ] **Lane 2:** implement rollback-state modeling for deploy cutover, pre-cutover candidate verification, failure rollback, and delayed old-runtime cleanup.
- [ ] **Lane 3:** align `app resource` internal logic with formal naming and catalog/service-key mapping instead of implicit `app_id == service_key`.
- [ ] **Lane 4:** ensure `service` and app runtime projections stay aligned after deploy/rollback without inventing a second runtime control plane.
- [ ] **Lane 5:** ensure website-facing verification hooks consume formal app outputs, not old helper assumptions.
- [ ] **Lane 6:** ensure projection/runtime-env verification continues to work against the hardened delivery outputs.
- [ ] **Lane 7:** prove `wsl` app delivery paths still support dev-only app contracts without production-only assumptions.
- [ ] **Lane 8:** verify `prod0-main` rollback-state behavior supports current production realities and readonly validation posture.
- [ ] **Lane 9:** verify `prod2-main` rollback-state behavior supports active production deployment validation paths.
- [ ] **Lane 10:** ensure secrets and app-resource secret-file scope rules fail in `validate-contract`, not later in deploy.
- [ ] **Lane 11:** update docs so rollback-state, naming, and contract-first validation are described once, not repeated across multiple active docs.
- [ ] **Lane 12:** run focused delivery acceptance and summarize gaps only if tests fail.

**Phase Exit Criteria:**
- rollback-state is formal behavior, not just documentation
- `validate-contract` fails on naming/resource-truth drift before deploy
- `app resource` internals no longer depend on legacy `tenant_*` semantics as the public truth model

**Minimal Verification:**

```bash
cd /root/work/OP_Linux
uv run pytest tests/test_app_cli.py -q -k "validate_contract or deploy or rollback or verify or inventory_refresh or doc_sync or render_runtime"
uv run pytest tests/test_app_resource_cli.py -q
```

## Phase 3: Equalize Host Governance Across `wsl` / `prod0-main` / `prod2-main`

**Outcome:** make the three formal targets governable through one host model with explicit asymmetry only where truly required.

**Files:**
- Modify: `ops/cli/host.py`
- Modify: `ops/cli/inventory.py`
- Modify: `ops/cli/audit.py`
- Modify: `ops/cli/networks.py`
- Modify: `ops/cli/remote.py`
- Modify: `ops/cli/secrets.py`
- Modify: `inventory/servers/wsl/inventory.json`
- Modify: `inventory/servers/prod0-main/inventory.json`
- Modify: `inventory/servers/prod2-main/inventory.json`
- Modify: `docs/runbooks/wsl-host-governance.md`
- Modify: `docs/runbooks/prod0-main-governance.md`
- Modify: `docs/runbooks/prod2-main-1panel-public-access.md`

- [ ] **Lane 1:** keep `host` parser contract explicit about which actions apply to all three formal targets and which remain target-specific.
- [ ] **Lane 2:** ensure app delivery and host governance hand off cleanly on network, remote execution, and live-state verification.
- [ ] **Lane 3:** align app/object/resource projections with host inventory structure across all three formal targets.
- [ ] **Lane 4:** align service truth with host inventory so runtime service summaries are generated consistently across targets.
- [ ] **Lane 5:** align public website truth with host target summaries and remove target-specific drift in public-ingress descriptions.
- [ ] **Lane 6:** align projection ledgers and inventory write-back expectations across all three formal targets.
- [ ] **Lane 7:** extend `wsl` host governance from local baseline-only wording to the same formal host truth vocabulary used for production targets where appropriate.
- [ ] **Lane 8:** expand `prod0-main` audit/inventory/secrets/network documentation and tests so it is not a special undocumented case.
- [ ] **Lane 9:** expand `prod2-main` host audit depth so it is not materially weaker than `prod0-main`.
- [ ] **Lane 10:** finish the host-first secrets model so `secrets/hosts/<target>/...` is the canonical truth for all three formal targets, with legacy paths treated as projections only.
- [ ] **Lane 11:** remove archived-host residue from active docs, inventories, and host-governance contracts so the formal target set stays unambiguous.
- [ ] **Lane 12:** run one focused readonly host acceptance per formal target and record only the acceptance result, not a second review round.

**Phase Exit Criteria:**
- `wsl`、`prod0-main`、`prod2-main` share one explicit host governance model
- audit depth differences are deliberate and documented, not accidental
- host-first secrets truth is canonical across all three formal targets
- archived-host residue no longer appears in the formal target model

**Minimal Verification:**

```bash
cd /root/work/OP_Linux
uv run python -m ops.cli host inventory wsl --repo-root /root/work/OP_Linux
uv run python -m ops.cli host audit wsl --repo-root /root/work/OP_Linux
uv run python -m ops.cli host inventory prod0-main --repo-root /root/work/OP_Linux
uv run python -m ops.cli host audit prod0-main --repo-root /root/work/OP_Linux
uv run python -m ops.cli host network audit prod0-main --repo-root /root/work/OP_Linux
uv run python -m ops.cli host inventory prod2-main --repo-root /root/work/OP_Linux
uv run python -m ops.cli host audit prod2-main --repo-root /root/work/OP_Linux
uv run python -m ops.cli host network audit prod2-main --repo-root /root/work/OP_Linux
```

## Phase 4: Formalize Automation And Projection Follow-Through

**Outcome:** make periodic governance and post-operation projection refresh a first-class formal workflow without bloating the daily gate.

**Files:**
- Modify: `ops/cli/host_automation.py`
- Modify: `ops/cli/projection.py`
- Modify: `ops/scripts/internal/repo/self_check.sh`
- Modify: `inventory/servers/wsl/inventory.json`
- Modify: `inventory/servers/prod0-main/inventory.json`
- Modify: `inventory/servers/prod2-main/inventory.json`
- Modify: `docs/runbooks/onepanel-cli-validation-workflow.md`
- Modify: `docs/runbooks/control-plane-agent-execution-flow.md`
- Modify: `docs/runbooks/wsl-secrets-backup.md`
- Modify: focused projection/automation tests as needed

- [ ] **Lane 1:** keep automation and projection CLI surfaces formal and explicit without adding second entrypoints.
- [ ] **Lane 2:** ensure app delivery post-actions call the right projection/inventory/doc-sync sequence and write evidence once.
- [ ] **Lane 3:** ensure app object/resource ledgers and projection ledger refresh compose correctly after app changes.
- [ ] **Lane 4:** ensure service reconciliation and verification hand off cleanly to projection/ledger refresh where required.
- [ ] **Lane 5:** ensure website publish flows and projection/ledger refresh expectations are aligned and not duplicated in docs.
- [ ] **Lane 6:** keep `projection verification / fixture / ledger` as scenario-specific workflows and do not move them into the daily thin gate.
- [ ] **Lane 7:** keep `wsl` automation as the reference implementation and clean up task truth, schedule truth, and verification wording.
- [ ] **Lane 8:** design and land the minimal formal production-host automation truth model for `prod0-main` where recurring governance is actually needed.
- [ ] **Lane 9:** design and land the minimal formal production-host automation truth model for `prod2-main` where recurring governance is actually needed.
- [ ] **Lane 10:** ensure secrets backup/sync automations consume canonical host-first secrets paths.
- [ ] **Lane 11:** update docs so automation and projection responsibilities are described once and linked from one place.
- [ ] **Lane 12:** run focused automation/projection acceptance using readonly or dry-run commands only where possible.

**Phase Exit Criteria:**
- host automation is no longer effectively WSL-only by accident
- projection write-back flow is formalized but kept out of daily self-check
- docs no longer duplicate automation/projection ownership across multiple active pages

**Minimal Verification:**

```bash
cd /root/work/OP_Linux
bash ops/scripts/internal/repo/self_check.sh
uv run pytest tests/test_cli_entrypoints.py tests/test_projection_validation_cli.py tests/test_projection_runtime_env_cli.py tests/test_onepanel_fixture_manager.py tests/test_onepanel_verification_suite.py tests/test_inventory_generation.py -q
uv run python -m ops.cli host automation search wsl --repo-root /root/work/OP_Linux
```

## Phase 5: Standardize Project Onboarding And Offboarding

**Outcome:** future new projects and removed projects follow one formal lifecycle, and the control plane can absorb or retire them without ad-hoc cleanup work.

**Files:**
- Modify: `inventory/apps/catalog.json`
- Modify: `ops/cli/apps.py`
- Modify: `ops/domain/app/*`
- Modify: `ops/domain/service/*`
- Modify: `ops/domain/website/*`
- Modify: `docs/reference/app-repository-standard.md`
- Modify: `docs/runbooks/app-project-delivery-workflow.md`
- Modify: `docs/architecture/op-linux-app-collaboration.md`
- Create or modify: project lifecycle tests for onboarding/offboarding

- [ ] **Lane 1:** add an explicit formal lifecycle contract for onboarding and offboarding actions, even if phase one only supports dry-run planning for removal.
- [ ] **Lane 2:** ensure app delivery can onboard a new project from contract validation through inventory/doc-sync, and can produce a safe offboarding plan.
- [ ] **Lane 3:** ensure app object/resource truth can be added and removed without leaving orphaned catalog or resource summaries.
- [ ] **Lane 4:** ensure service truth can be added and removed with inventory-safe semantics and no raw-object drift.
- [ ] **Lane 5:** ensure website/public-ingress truth can be added and removed with the same formal lifecycle.
- [ ] **Lane 6:** ensure projection/runtime-env/ledger expectations for onboarding and offboarding are documented and tested.
- [ ] **Lane 7:** ensure `wsl`-only projects can onboard without forcing production-only assumptions.
- [ ] **Lane 8:** ensure `prod0-main` onboarding/offboarding plans work with current production safety constraints.
- [ ] **Lane 9:** ensure `prod2-main` onboarding/offboarding plans work with current active production topology.
- [ ] **Lane 10:** ensure secret allocation and retirement paths are explicit for project add/remove workflows.
- [ ] **Lane 11:** consolidate onboarding/offboarding docs so the standard lives in one reference page plus one active workflow page.
- [ ] **Lane 12:** run one onboarding dry-run and one offboarding dry-run acceptance on sample tracked objects and summarize the outcome.

**Phase Exit Criteria:**
- new project onboarding has one formal path
- project offboarding has one formal path, even if guarded behind dry-run initially
- add/remove flows update catalog, app resource truth, service truth, website truth, inventory, and docs consistently

**Minimal Verification:**

```bash
cd /root/work/OP_Linux
uv run pytest tests/test_app_cli.py tests/test_app_object_cli.py tests/test_app_resource_cli.py tests/test_app_resource_object_cli.py -q
uv run python -m ops.cli app object search --target prod0-main --repo-root /root/work/OP_Linux
uv run python -m ops.cli app delivery validate-contract --target prod0-main --app sub2api --repo-root /root/work/OP_Linux
```

## Final Acceptance

The roadmap is complete only when all of the following are true:

- `wsl`、`prod0-main`、`prod2-main` are the only active formal host targets, with explicit handling for any archived or standby hosts.
- all active resources, applications, websites, and local repository delivery contracts are reachable from one formal CLI-first control plane.
- daily self-check stays thin and fast.
- live verification remains scenario-specific and does not silently creep into daily gatekeeping.
- a new project can be onboarded by the formal workflow.
- an existing project can be removed by the formal workflow without leaving unmanaged tracked truth behind.

## Execution Order

1. Phase 1
2. Phase 2
3. Phase 3
4. Phase 4
5. Phase 5

Do not overlap phases unless the current phase exit criteria are green. Inside a phase, always dispatch all 12 lanes in parallel. Review only the phase acceptance result, not each lane separately.
