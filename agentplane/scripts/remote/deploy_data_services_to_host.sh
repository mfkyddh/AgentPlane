#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
SSH_CONFIG="$REPO_ROOT/secrets/ssh/config"
REMOTE_SCRIPT="$SCRIPT_DIR/remote_deploy_data_services.sh"

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <host-alias>" >&2
  exit 1
fi

target_host="$1"
case "$target_host" in
  prod0-main)
    target_alias="prod0"
    postgres_compose_file="docker-compose.prod0.yml"
    redis_compose_file="docker-compose.prod0.yml"
    minio_compose_file="docker-compose.prod0.yml"
    ;;
  prod2-main)
    target_alias="prod2"
    postgres_compose_file="docker-compose.prod2.yml"
    redis_compose_file="docker-compose.prod2.yml"
    minio_compose_file="docker-compose.prod2.yml"
    ;;
  *)
    echo "Unsupported host alias: $target_host (expected: prod0-main or prod2-main)" >&2
    exit 1
    ;;
esac

op_id="data-services-$(date -u +%Y%m%dT%H%M%SZ)-$$"
remote_stage_root="/tmp/oplinux/$op_id"

required_files=(
  "$REPO_ROOT/secrets/services/postgres/admin.${target_alias}.env"
  "$REPO_ROOT/secrets/services/redis/admin.${target_alias}.conf"
  "$REPO_ROOT/secrets/services/minio/admin.${target_alias}.env"
  "$REPO_ROOT/infra/compose/postgres/${postgres_compose_file}"
  "$REPO_ROOT/infra/compose/redis/${redis_compose_file}"
  "$REPO_ROOT/infra/compose/minio/${minio_compose_file}"
  "$REMOTE_SCRIPT"
)

for path in "${required_files[@]}"; do
  if [[ ! -f "$path" ]]; then
    echo "Missing required file: $path" >&2
    exit 1
  fi
done

stage_dir="$(mktemp -d)"
cleanup() {
  rm -rf "$stage_dir"
  ssh -F "$SSH_CONFIG" "$target_host" "rm -rf '$remote_stage_root'" >/dev/null 2>&1 || true
}
trap cleanup EXIT

mkdir -p \
  "$stage_dir/infra/compose/postgres" \
  "$stage_dir/infra/compose/redis" \
  "$stage_dir/infra/compose/minio" \
  "$stage_dir/secrets/services/postgres" \
  "$stage_dir/secrets/services/redis" \
  "$stage_dir/secrets/services/minio"

cp "$REPO_ROOT/infra/compose/postgres/${postgres_compose_file}" "$stage_dir/infra/compose/postgres/"
cp "$REPO_ROOT/infra/compose/redis/${redis_compose_file}" "$stage_dir/infra/compose/redis/"
cp "$REPO_ROOT/infra/compose/minio/${minio_compose_file}" "$stage_dir/infra/compose/minio/"
cp "$REPO_ROOT/secrets/services/postgres/admin.${target_alias}.env" "$stage_dir/secrets/services/postgres/"
cp "$REPO_ROOT/secrets/services/redis/admin.${target_alias}.conf" "$stage_dir/secrets/services/redis/"
cp "$REPO_ROOT/secrets/services/minio/admin.${target_alias}.env" "$stage_dir/secrets/services/minio/"

ssh -F "$SSH_CONFIG" "$target_host" "mkdir -p /tmp/oplinux '$remote_stage_root'"
tar -C "$stage_dir" -cf - infra secrets | ssh -F "$SSH_CONFIG" "$target_host" "tar -xf - -C '$remote_stage_root'"
ssh -F "$SSH_CONFIG" "$target_host" "bash -s -- '$remote_stage_root' '$op_id' '$target_alias'" < "$REMOTE_SCRIPT"
