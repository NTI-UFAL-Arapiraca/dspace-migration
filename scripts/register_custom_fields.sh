#!/usr/bin/env bash
# Registra metadados pelo CLI oficial do DSpace, sem SQL direto.
set -euo pipefail

usage() {
    echo "Uso: $0 [NOME_OU_ID_CONTAINER_DSPACE]"
    echo "Padrão: DSPACE_CONTAINER ou dspace. Use o backend, não o PostgreSQL."
}

if [[ ${1:-} == --help || ${1:-} == -h ]]; then
    usage
    exit 0
fi
if (( $# > 1 )); then
    usage >&2
    exit 2
fi

CONTAINER_NAME="${1:-${DSPACE_CONTAINER:-dspace}}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REGISTRY_FILE="$SCRIPT_DIR/../config/registries/migration-metadata.xml"

if [[ ! -r "$REGISTRY_FILE" ]]; then
    echo "Registro XML não encontrado ou ilegível: $REGISTRY_FILE" >&2
    exit 1
fi

# O backend precisa estar iniciado e usar o banco de destino da migração.
REMOTE_FILE="$(docker exec "$CONTAINER_NAME" mktemp /tmp/dspace-migration-metadata.XXXXXX.xml)"
cleanup() {
    docker exec "$CONTAINER_NAME" rm -f -- "$REMOTE_FILE" || true
}
trap cleanup EXIT

docker cp "$REGISTRY_FILE" "$CONTAINER_NAME:$REMOTE_FILE"
docker exec "$CONTAINER_NAME" /dspace/bin/dspace registry-loader -m "$REMOTE_FILE"
echo "✔ Registro concluído. Campos existentes foram preservados."
