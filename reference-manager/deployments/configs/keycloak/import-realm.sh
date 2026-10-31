#!/bin/bash
# entry point of the local Keycloak: writes the realm file with the secret of the provisioner client taken
# from the environment, then starts Keycloak with the realm import, the realm file in the repository holds
# the placeholder only, so no secret is committed (NFR-RM-22), the image has bash and no sed, hence the loop
set -eu

: "${KEYCLOAK_PROVISIONER_SECRET:?KEYCLOAK_PROVISIONER_SECRET is required}"

template=/opt/keycloak/realm-template/arch-info-system-realm.json
target=/opt/keycloak/data/import/arch-info-system-realm.json

mkdir -p "$(dirname "$target")"

while IFS= read -r line || [ -n "$line" ]; do
    printf '%s\n' "${line//__PROVISIONER_SECRET__/$KEYCLOAK_PROVISIONER_SECRET}"
done < "$template" > "$target"

exec /opt/keycloak/bin/kc.sh start-dev --import-realm "$@"
