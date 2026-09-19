#!/bin/sh
set -eu

postgres_container="${POSTGRES_CONTAINER:-course_postgres}"
backend_image="${BACKEND_TEST_IMAGE:-course_local_test-backend}"
docker_network="${DOCKER_NETWORK:-course_selection_system_default}"
backend_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

container_env=$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$postgres_container")
POSTGRES_PASSWORD=$(printf '%s\n' "$container_env" | sed -n 's/^POSTGRES_PASSWORD=//p')
POSTGRES_USER=$(printf '%s\n' "$container_env" | sed -n 's/^POSTGRES_USER=//p')
POSTGRES_DB=$(printf '%s\n' "$container_env" | sed -n 's/^POSTGRES_DB=//p')
export POSTGRES_PASSWORD POSTGRES_USER POSTGRES_DB

if [ -z "$POSTGRES_PASSWORD" ]; then
    echo "Could not read PostgreSQL settings from $postgres_container" >&2
    exit 1
fi

docker run --rm \
    --network "$docker_network" \
    -e POSTGRES_PASSWORD -e POSTGRES_USER -e POSTGRES_DB \
    -e POSTGRES_HOST=postgres \
    -v "$backend_dir:/work:ro" -w /work \
    "$backend_image" python tests/run_postgres_concurrency.py
