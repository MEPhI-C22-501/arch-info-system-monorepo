#!/bin/bash
# entry point of the local Keycloak: writes the realm file with the secrets of the service clients taken
# from the environment, then starts Keycloak with the realm import, the realm file in the repository holds
# the placeholders only, so no secret is committed (NFR-RM-22), the image has bash and no sed, hence the loop
set -eu

: "${KEYCLOAK_PROVISIONER_SECRET:?KEYCLOAK_PROVISIONER_SECRET is required}"

# the consumer clients are optional: without a secret in the environment they get a random one nobody knows
consumer_secret="${KEYCLOAK_CONSUMER_SECRET:-$(cat /proc/sys/kernel/random/uuid)}"

template=/opt/keycloak/realm-template/arch-info-system-realm.json
target=/opt/keycloak/data/import/arch-info-system-realm.json

mkdir -p "$(dirname "$target")"

while IFS= read -r line || [ -n "$line" ]; do
    line="${line//__PROVISIONER_SECRET__/$KEYCLOAK_PROVISIONER_SECRET}"
    printf '%s\n' "${line//__CONSUMER_SECRET__/$consumer_secret}"
done < "$template" > "$target"

exec /opt/keycloak/bin/kc.sh start-dev --import-realm "$@"
