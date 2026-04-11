#!/usr/bin/env bash
set -euo pipefail

stage_root="${1:?stage_root is required}"
op_id="${2:-unknown}"
target_alias="${3:?target_alias is required}"
control_root="/opt/agentplane"

case "$target_alias" in
  prod0)
    redis_compose="${control_root}/infra/compose/redis/docker-compose.prod0.yml"
    minio_compose="${control_root}/infra/compose/minio/docker-compose.prod0.yml"
    postgres_compose="${control_root}/infra/compose/postgres/docker-compose.prod0.yml"
    ;;
  prod2)
    redis_compose="${control_root}/infra/compose/redis/docker-compose.prod2.yml"
    minio_compose="${control_root}/infra/compose/minio/docker-compose.prod2.yml"
    postgres_compose="${control_root}/infra/compose/postgres/docker-compose.prod2.yml"
    ;;
  *)
    echo "Unsupported target alias: $target_alias (expected: prod0 or prod2)" >&2
    exit 1
    ;;
esac

redis_conf="${control_root}/secrets/services/redis/admin.${target_alias}.conf"
postgres_env="${control_root}/secrets/services/postgres/admin.${target_alias}.env"

if [[ "$(id -u)" -eq 0 ]]; then
  SUDO=()
else
  SUDO=(sudo)
fi

cleanup() {
  "${SUDO[@]}" rm -rf "$stage_root"
}
trap cleanup EXIT

"${SUDO[@]}" docker network inspect zqf_network >/dev/null 2>&1 || "${SUDO[@]}" docker network create zqf_network >/dev/null

"${SUDO[@]}" mkdir -p "$control_root"
"${SUDO[@]}" mkdir -p /data/redis/data /data/minio/data /data/minio/config /data/postgres/data
"${SUDO[@]}" rm -rf "$control_root/infra" "$control_root/secrets"
"${SUDO[@]}" cp -r "$stage_root/infra" "$control_root/"
"${SUDO[@]}" cp -r "$stage_root/secrets" "$control_root/"

# PostgreSQL 18 官方镜像中的 postgres 用户 uid/gid 为 999。
"${SUDO[@]}" chown -R 999:999 /data/postgres/data
# 仅放宽远端部署副本目录的遍历权限，避免容器进程无法读取挂载文件。
"${SUDO[@]}" chmod 755 "$control_root/secrets" "$control_root/secrets/services" \
  "$control_root/secrets/services/postgres" "$control_root/secrets/services/redis" "$control_root/secrets/services/minio"
# Redis 容器内进程需要可读配置文件，避免复制后的 0600 权限导致启动失败。
"${SUDO[@]}" chmod 644 "$redis_conf"

redis_password="$("${SUDO[@]}" awk '/^requirepass[[:space:]]+/ {print $2; exit}' "$redis_conf")"
postgres_user="$("${SUDO[@]}" awk -F= '/^POSTGRES_USER=/ {print $2; exit}' "$postgres_env")"
postgres_db="$("${SUDO[@]}" awk -F= '/^POSTGRES_DB=/ {print $2; exit}' "$postgres_env")"

for legacy_name in redis7-dev minio-dev postgres18-dev; do
  if "${SUDO[@]}" docker ps -a --format '{{.Names}}' | grep -qx "$legacy_name"; then
    "${SUDO[@]}" docker rm -f "$legacy_name" >/dev/null
  fi
done

cd "${control_root}/infra/compose/redis"
"${SUDO[@]}" docker compose -f "$redis_compose" up -d

cd "${control_root}/infra/compose/minio"
"${SUDO[@]}" docker compose -f "$minio_compose" up -d

cd "${control_root}/infra/compose/postgres"
"${SUDO[@]}" docker compose -f "$postgres_compose" up -d

for _ in $(seq 1 30); do
  status="$("${SUDO[@]}" docker inspect -f '{{.State.Health.Status}}' postgres18-prod 2>/dev/null || true)"
  if [[ "$status" == "healthy" ]]; then
    break
  fi
  sleep 2
done

printf '===OPERATION===\n'
printf 'op_id=%s\n' "$op_id"
printf 'stage_root=%s\n' "$stage_root"
printf 'target=%s\n' "$(hostname)"
printf 'target_alias=%s\n' "$target_alias"
printf 'artifacts=%s\n' "infra/compose/{postgres,redis,minio} + secrets/services/{postgres,redis,minio}"

printf '===NETWORK===\n'
"${SUDO[@]}" docker network ls --format '{{.Name}}' | grep -x 'zqf_network'

printf '===CONTAINERS===\n'
"${SUDO[@]}" docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'

printf '===REDIS===\n'
"${SUDO[@]}" docker exec redis7-prod redis-cli -a "$redis_password" PING
"${SUDO[@]}" docker exec redis7-prod redis-cli -a "$redis_password" INFO server | grep '^redis_version:'

printf '===MINIO===\n'
curl -fsS http://127.0.0.1:9000/minio/health/live >/dev/null && echo 'minio_live=ok'
curl -fsS http://127.0.0.1:9000/minio/health/ready >/dev/null && echo 'minio_ready=ok'

printf '===POSTGRES===\n'
"${SUDO[@]}" docker inspect -f '{{.State.Health.Status}}' postgres18-prod
"${SUDO[@]}" docker exec postgres18-prod psql -h 127.0.0.1 -U "$postgres_user" -d "$postgres_db" -tAc 'SELECT version();'

printf '===UFW===\n'
"${SUDO[@]}" ufw status verbose

printf '===RESULT===\n'
printf 'result=ok\n'
