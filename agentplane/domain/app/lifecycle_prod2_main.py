from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any

PRODUCTION_TARGET = 'prod2-main'
_HOST_INVENTORY = Path('inventory') / 'servers' / PRODUCTION_TARGET / 'inventory.json'
_RUNBOOK_DOC = 'docs/runbooks/prod2-main-1panel-public-access.md'
_PUBLIC_INGRESS_CONFIG = Path('secrets/services/onepanel-public-ingress.prod2.env')
_CLOUDFLARE_ENV = Path('secrets/env/prod-jump.env')


def _load_inventory(repo_root: Path) -> dict[str, Any]:
    inventory_file = (repo_root / _HOST_INVENTORY).resolve()
    if not inventory_file.is_file():
        raise FileNotFoundError(f'missing prod2-main inventory: {inventory_file}')
    payload = json.loads(inventory_file.read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        raise ValueError(f'inventory must be an object: {inventory_file}')
    return payload


def _normalize_services(raw_services: dict[str, Any]) -> list[dict[str, Any]]:
    services: list[dict[str, Any]] = []
    for name in sorted(raw_services):
        if name == 'public_ingresses':
            continue
        info = raw_services.get(name)
        if not isinstance(info, dict):
            continue
        services.append(
            {
                'name': name,
                'status': info.get('status'),
                'control_plane': info.get('control_plane'),
                'container_name': info.get('container_name') or info.get('container'),
                'host_binding': info.get('host_binding') or info.get('host_bindings'),
                'docker_networks': info.get('docker_networks'),
                'public_url': info.get('public_url'),
            }
        )
    return services


def _summaries(raw_entries: list[Any], *, fields: tuple[str, ...]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for entry in raw_entries:
        if not isinstance(entry, dict):
            continue
        record: dict[str, Any] = {}
        for key in fields:
            if key in entry:
                record[key] = entry[key]
        if record:
            result.append(record)
    return result


def describe_prod2_main_topology(repo_root: Path) -> dict[str, Any]:
    '''Dump the prod2-main topology truth that Lane 9 maintains for onboarding/offboarding.'''

    inventory = _load_inventory(repo_root)
    networks = _summaries(inventory.get('managed_bridge_networks', []), fields=('name', 'driver', 'subnet', 'gateway_ip', 'required_for'))
    services_raw = inventory.get('services', {})
    services_dict = services_raw if isinstance(services_raw, dict) else {}
    services = _normalize_services(services_dict)
    websites = _summaries(services_dict.get('public_ingresses', []), fields=('alias', 'primary_domain', 'public_url', 'proxy', 'config_file', 'certificate_mode', 'status'))
    automations = _summaries(inventory.get('automations', []), fields=('name', 'command', 'schedule'))

    app_resources: list[dict[str, Any]] = []
    for name in sorted(services_dict):
        info = services_dict.get(name)
        if not isinstance(info, dict):
            continue
        summary = info.get('app_resource_summary')
        if isinstance(summary, dict):
            app_resources.append({'app': name, 'resources': list(summary.keys())})

    return {
        'target': PRODUCTION_TARGET,
        'networks': networks,
        'services': services,
        'websites': websites,
        'automations': automations,
        'app_resources': app_resources,
    }


def build_prod2_main_onboarding_plan(repo_root: Path) -> dict[str, Any]:
    '''Lane 2 can call this to retrieve the current prod2-main onboarding checklist.'''

    repo_root_shell = shlex.quote(str(repo_root.resolve()))
    ingress_config_shell = shlex.quote(str((repo_root / _PUBLIC_INGRESS_CONFIG).resolve()))
    cloudflare_shell = shlex.quote(str((repo_root / _CLOUDFLARE_ENV).resolve()))
    topology = describe_prod2_main_topology(repo_root)
    commands_base = [
        f'uv run python -m agentplane.cli infra inventory {PRODUCTION_TARGET} --repo-root {repo_root_shell} --write',
        f'uv run python -m agentplane.cli infra audit {PRODUCTION_TARGET} --repo-root {repo_root_shell}',
        f'uv run python -m agentplane.cli projection ledger refresh --target {PRODUCTION_TARGET} --repo-root {repo_root_shell} --write',
    ]

    network_details: list[str] = []
    host_network: list[str] = []
    if topology['networks']:
        network = topology['networks'][0]
        host_network = [
            f'uv run python -m agentplane.cli infra network audit {PRODUCTION_TARGET} --repo-root {repo_root_shell}',
            f'uv run python -m agentplane.cli infra network ensure {PRODUCTION_TARGET} --repo-root {repo_root_shell}',
        ]
        network_details = [
            f'managed bridge: {network.get('name')} {network.get('subnet')}',
            f'gateway: {network.get('gateway_ip')}',
        ]
    else:
        network_details = ['managed bridge: (not declared)']

    service_verify_cmds = []
    for service in ('postgres', 'redis', 'minio', 'onepanel', 'onepanel_openresty'):
        service_verify_cmds.append(f'uv run python -m agentplane.cli service verify --target {PRODUCTION_TARGET} --name {service} --repo-root {repo_root_shell}')

    app_verify_cmds = [
        f'uv run python -m agentplane.cli app resource verify --target {PRODUCTION_TARGET} --app sub2api --repo-root {repo_root_shell}',
        f'uv run python -m agentplane.cli service verify --target {PRODUCTION_TARGET} --name sub2api --repo-root {repo_root_shell}',
    ]

    website_verify_cmds: list[str] = []
    for alias in ('1panel', 'token', 'vmail'):
        website_verify_cmds.append(f'uv run python -m agentplane.cli ingress verify --target {PRODUCTION_TARGET} --alias {alias} --repo-root {repo_root_shell}')
    website_verify_cmds.append(
        f'uv run python -m agentplane.cli ingress publish verify --target {PRODUCTION_TARGET} --config-file {ingress_config_shell} --cloudflare-env-file {cloudflare_shell} --repo-root {repo_root_shell}'
    )

    return {
        'target': PRODUCTION_TARGET,
        'topology': topology,
        'steps': [
            {
                'id': 'record-host-truth',
                'summary': 'Capture the prod2-main host baseline and keep its docs in sync',
                'commands': commands_base,
                'references': [
                    _RUNBOOK_DOC,
                    str((repo_root / _HOST_INVENTORY).resolve()),
                ],
            },
            {
                'id': 'bridge-network',
                'summary': 'Ensure the zqf_network bridge that ties the shared services and apps',
                'commands': host_network,
                'details': network_details,
            },
            {
                'id': 'core-services',
                'summary': 'Validate the shared services and 1Panel infrastructure that every onboarding relies on',
                'commands': service_verify_cmds,
                'notes': ['Shared compose services depend on zqf_network.', '1Panel host network is mandatory for https ingress.'],
            },
            {
                'id': 'app-objects',
                'summary': 'Use app object + resource verify so Lane 2 can prove the tracked apps match the real contracts',
                'commands': app_verify_cmds,
                'notes': ['Run validate-contract, inventory-refresh, doc-sync and delivery verify/deploy if the ledger is out of date.'],
            },
            {
                'id': 'website-ingress',
                'summary': 'Confirm the 1Panel public ingress family is aligned with the Cloudflare-managed domains',
                'commands': website_verify_cmds,
                'notes': [
                    'The 1Panel publish plan uses secrets/services/onepanel-public-ingress.prod2.env',
                    'The fallback Cloudflare env is secrets/env/prod-jump.env',
                ],
            },
        ],
    }


def build_prod2_main_offboarding_plan(repo_root: Path) -> dict[str, Any]:
    '''Lane 2 can call this before decommissioning to understand the prod2-main removal sequence.'''

    repo_root_shell = shlex.quote(str(repo_root.resolve()))
    ingress_config_shell = shlex.quote(str((repo_root / _PUBLIC_INGRESS_CONFIG).resolve()))
    cloudflare_shell = shlex.quote(str((repo_root / _CLOUDFLARE_ENV).resolve()))

    removal_commands: list[str] = []
    for alias in ('1panel', 'token', 'vmail'):
        removal_commands.append(
            f'uv run python -m agentplane.cli ingress publish plan --target {PRODUCTION_TARGET} --config-file {ingress_config_shell} --cloudflare-env-file {cloudflare_shell} --repo-root {repo_root_shell}'
        )
        removal_commands.append(
            f'uv run python -m agentplane.cli ingress publish apply --target {PRODUCTION_TARGET} --config-file {ingress_config_shell} --cloudflare-env-file {cloudflare_shell} --repo-root {repo_root_shell} --execute'
        )

    app_remove_commands: list[str] = []
    for app_name in ('sub2api', 'vmail'):
        app_remove_commands.append(
            f'uv run python -m agentplane.cli app delivery rollback --target {PRODUCTION_TARGET} --app {app_name} --repo-root {repo_root_shell} --dry-run'
        )

    service_cleanup_commands = [
        f'uv run python -m agentplane.cli service verify --target {PRODUCTION_TARGET} --name onepanel_openresty --repo-root {repo_root_shell}',
        f'uv run python -m agentplane.cli infra network audit {PRODUCTION_TARGET} --repo-root {repo_root_shell}',
    ]

    return {
        'target': PRODUCTION_TARGET,
        'steps': [
            {
                'id': 'website-retirement',
                'summary': 'Remove the public ingress objects before tearing down the host',
                'commands': removal_commands,
                'notes': [
                    'Plan before apply so Cloudflare entries can be verified before commit.',
                    '1Panel publish hooks enforce the 443-only rule described in the prod2-main runbook.',
                ],
            },
            {
                'id': 'app-decommission',
                'summary': 'Roll back tracked apps so their resources can be reclaimed',
                'commands': app_remove_commands,
                'notes': ['Gracefully drain sub2api and vmail.'],
            },
            {
                'id': 'service-cleanup',
                'summary': 'Ensure the host-level services and bridge network are tidy',
                'commands': service_cleanup_commands,
                'notes': [
                    'Once all apps are gone the zqf_network bridge can be deleted without collateral damage.',
                    'Document the ledger removals under inventory/servers/prod2-main/ledgers.',
                ],
            },
            {
                'id': 'docs-and-inventory',
                'summary': 'Remove prod2-main entries from inventory, ledgers, and runbooks',
                'commands': [
                    f'uv run python -m agentplane.cli infra inventory {PRODUCTION_TARGET} --repo-root {repo_root_shell} --write',
                ],
                'notes': [
                    f'Archive {_RUNBOOK_DOC} references into docs/archive if the host is retired.',
                    'Update inventory/servers/prod2-main/README.md and ledgers to mark the host retired.',
                ],
            },
        ],
    }


def build_prod2_main_lifecycle_policy(repo_root: Path) -> dict[str, Any]:
    '''Return the full lifecycle policy summary for Lane 2 integrations.'''

    return {
        'target': PRODUCTION_TARGET,
        'topology': describe_prod2_main_topology(repo_root),
        'onboarding': build_prod2_main_onboarding_plan(repo_root)['steps'],
        'offboarding': build_prod2_main_offboarding_plan(repo_root)['steps'],
    }
