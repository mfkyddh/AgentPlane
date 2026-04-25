from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentplane.domain.app.resource_paths import app_resource_secret_dir, app_resource_secret_relative
from agentplane.domain.app.resource_registry import resolve_app_resource
from agentplane.domain.app.resource_state import load_registry

STATUS_MATERIALIZED = 'materialized-in-agentplane'
STATUS_RETIRED = 'retired'


def plan_secret_allocation(repo_root: Path, target: str, app: str) -> dict[str, Any]:
    '''Describe the canonical secret allocation steps for an app resource.'''

    return _build_plan(repo_root, target, app, operation='allocate')


def apply_secret_allocation(repo_root: Path, target: str, app: str, *, execute: bool) -> dict[str, Any]:
    '''Ensure app resource secret files and registry metadata are materialized.'''

    if not execute:
        raise ValueError('secret allocation apply requires execute=True')
    state = _load_secret_state(repo_root, target, app)
    created: list[str] = []
    for entry in state['canonical_entries']:
        path = entry['path']
        if not path.is_file():
            _write_secret_file(path, _render_secret_content(entry['kind'], state['definition'].app, target, state['raw_entry']))
            created.append(str(path))

    registry_updated = _normalize_registry_entry(state, desired_status=STATUS_MATERIALIZED)
    return {
        'operation': 'allocate',
        'target': target,
        'app': state['definition'].app,
        'secret_root': str(state['secret_dir']),
        'created_files': created,
        'registry_updated': registry_updated,
        'local_secret_presence': state['raw_entry'].get('ledger_status', {}).get('local_secret_presence'),
    }


def plan_secret_retirement(repo_root: Path, target: str, app: str) -> dict[str, Any]:
    '''Describe how to retire secret files for the app resource.'''

    return _build_plan(repo_root, target, app, operation='retire')


def apply_secret_retirement(repo_root: Path, target: str, app: str, *, execute: bool) -> dict[str, Any]:
    '''Delete canonical secret files and mark the resource as retired.'''

    if not execute:
        raise ValueError('secret retirement apply requires execute=True')
    state = _load_secret_state(repo_root, target, app)
    removed: list[str] = []
    for entry in state['canonical_entries']:
        path = entry['path']
        if path.is_file():
            path.unlink()
            removed.append(str(path))

    registry_updated = _normalize_registry_entry(state, desired_status=STATUS_RETIRED)
    return {
        'operation': 'retire',
        'target': target,
        'app': state['definition'].app,
        'secret_root': str(state['secret_dir']),
        'removed_files': removed,
        'registry_updated': registry_updated,
        'local_secret_presence': state['raw_entry'].get('ledger_status', {}).get('local_secret_presence'),
    }


def _build_plan(repo_root: Path, target: str, app: str, *, operation: str) -> dict[str, Any]:
    state = _load_secret_state(repo_root, target, app)
    registry_secret_files = state['registry_secret_files']
    canonical_relatives = state['canonical_relatives']
    files: list[dict[str, Any]] = []
    missing: list[str] = []
    for entry in state['canonical_entries']:
        path = entry['path']
        rel = entry['relative']
        exists = path.is_file()
        if not exists:
            missing.append(rel)
        files.append(
            {
                'kind': entry['kind'],
                'path': str(path),
                'relative': rel,
                'exists': exists,
                'in_registry': rel in registry_secret_files,
            }
        )

    non_canonical = [item for item in registry_secret_files if item not in canonical_relatives]
    markup = STATUS_MATERIALIZED if operation == 'allocate' else STATUS_RETIRED

    steps: list[str] = [
        f"Ensure the secret directory {state['secret_dir']} exists",
        f"Keep {state['definition'].app} secret paths under the canonical names",
    ]
    if operation == 'allocate':
        steps.extend(
            [
                'Create or update placeholder secret files for the missing entries',
                f'Record canonical secret paths and ledger_status.local_secret_presence={markup}',
            ]
        )
    else:
        steps.extend(
            [
                'Delete canonical secret files that are present',
                f'Set ledger_status.local_secret_presence={markup} after retirement',
            ]
        )

    return {
        'target': target,
        'app': state['definition'].app,
        'operation': operation,
        'guarded': operation == 'retire',
        'requires_execute': True,
        'secret_root': str(state['secret_dir']),
        'files': files,
        'registry_secret_files': list(registry_secret_files),
        'canonical_secret_files': canonical_relatives,
        'missing_files': missing,
        'non_canonical_registry': non_canonical,
        'local_secret_presence': state['local_secret_presence'],
        'steps': steps,
        'registry_path': str(state['registry_path']),
    }


def _load_secret_state(repo_root: Path, target: str, app: str) -> dict[str, Any]:
    definition, raw_entry = resolve_app_resource(repo_root, target, app)
    registry_path, registry = load_registry(repo_root, target)
    registry_key = _registry_key_for_entry(registry, raw_entry)
    if registry_key is None:
        raise ValueError('app resource entry missing from registry file')
    secret_dir = app_resource_secret_dir(repo_root, target, definition.app)
    canonical_entries = _canonical_secret_entries(repo_root, target, definition)
    canonical_relatives = [entry['relative'] for entry in canonical_entries]
    registry_secret_files = raw_entry.get('secret_files') if isinstance(raw_entry.get('secret_files'), list) else []
    ledger = raw_entry.get('ledger_status')
    local_secret_presence = ledger.get('local_secret_presence') if isinstance(ledger, dict) else None
    return {
        'definition': definition,
        'raw_entry': raw_entry,
        'registry': registry,
        'registry_path': registry_path,
        'registry_key': registry_key,
        'secret_dir': secret_dir,
        'canonical_entries': canonical_entries,
        'canonical_relatives': canonical_relatives,
        'registry_secret_files': registry_secret_files,
        'local_secret_presence': local_secret_presence,
    }


def _canonical_secret_entries(repo_root: Path, target: str, definition: Any) -> list[dict[str, Any]]:
    secret_dir = app_resource_secret_dir(repo_root, target, definition.app)
    items: list[dict[str, Any]] = []
    for kind in definition.resource_kinds:
        path = secret_dir / f'{kind}.env'
        items.append(
            {
                'kind': kind,
                'path': path,
                'relative': app_resource_secret_relative(target, definition.app, kind),
            }
        )
    return items


def _registry_key_for_entry(registry: dict[str, Any], entry: dict[str, Any]) -> str | None:
    for key, value in registry.items():
        if value is entry:
            return key
    for key, value in registry.items():
        if value == entry:
            return key
    return None


def _normalize_registry_entry(state: dict[str, Any], *, desired_status: str) -> bool:
    registry = state['registry']
    entry = registry[state['registry_key']]
    updated = False
    canonical = state['canonical_relatives']
    if entry.get('secret_files') != canonical:
        entry['secret_files'] = canonical
        updated = True
    ledger = entry.setdefault('ledger_status', {})
    if ledger.get('local_secret_presence') != desired_status:
        ledger['local_secret_presence'] = desired_status
        updated = True
    if updated:
        _persist_registry(state['registry_path'], registry)
    return updated


def _render_secret_content(kind: str, app: str, target: str, entry: dict[str, Any]) -> str:
    if kind == 'postgres':
        value = entry.get('postgres') or {}
        database = _coerce(value.get('database'))
        user = _coerce(value.get('user'))
        lines = [
            f'# Postgres secret for {app} on {target}',
            '# Replace blank credentials with the values you provision.',
            'PGHOST=',
            'PGPORT=5432',
            f'PGDATABASE={database}',
            f'PGUSER={user}',
            'PGPASSWORD=',
        ]
    elif kind == 'redis':
        value = entry.get('redis') or {}
        db = _coerce(value.get('db'))
        key_prefix = _coerce(value.get('key_prefix'))
        lines = [
            f'# Redis secret for {app} on {target}',
            '# Fill in REDIS_PASSWORD before using the cluster.',
            'REDIS_HOST=',
            'REDIS_PORT=6379',
            f'REDIS_DB={db}',
            f'REDIS_KEY_PREFIX={key_prefix}',
            'REDIS_PASSWORD=',
            'REDIS_ENABLE_TLS=false',
        ]
    elif kind == 'minio':
        value = entry.get('minio') or {}
        bucket = _coerce(value.get('bucket'))
        access_key = _coerce(value.get('access_key'))
        lines = [
            f'# MinIO secret for {app} on {target}',
            '# Populate the secret key to unlock the bucket.',
            f'MINIO_BUCKET={bucket}',
            f'MINIO_ACCESS_KEY={access_key}',
            'MINIO_SECRET_KEY=',
        ]
    else:
        lines = [
            f'# Secret file for {kind} on {app}/{target}',
            '# Supply the needed credentials in this file.',
        ]
    return '\n'.join(lines) + '\n'


def _coerce(value: Any) -> str:
    if value is None:
        return ''
    return str(value)


def _write_secret_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')
    path.chmod(0o600)


def _persist_registry(path: Path, registry: dict[str, Any]) -> None:
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
