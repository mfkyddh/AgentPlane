#!/usr/bin/env bash
set -euo pipefail

container_name="${1:?container_name is required}"
docker inspect "$container_name" --format '{{.Name}} {{.State.Status}}'
