#!/usr/bin/env bash
# Local demo only. All Kubernetes commands target the arch-demo context.
set -euo pipefail
umask 077
export PATH="$HOME/.local/bin:$PATH"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MANIFESTS="$ROOT/infra/k8s/demo"
PROFILE=arch-demo
MOCK_IMAGE=arch-info-demo:local
MINIO_IMAGE=arch-info-minio:RELEASE.2025-10-15T17-29-55Z
STATE="${XDG_STATE_HOME:-$HOME/.local/state}/arch-info-demo/$PROFILE"
export DEMO_STATE="$STATE"
TEAMS=(planning-system task-tracker reference-manager qa reports)
k() { kubectl --context="$PROFILE" "$@"; }

prepare_secrets() {
  mkdir -p "$STATE"
  if [[ ! -f "$STATE/secrets.env" ]]; then
    while IFS='=' read -r key _; do
      [[ "$key" =~ ^[A-Z][A-Z0-9_]*$ ]] || continue
      case "$key" in
        KC_BOOTSTRAP_ADMIN_USERNAME) value=admin ;;
        MINIO_ROOT_USER) value=demo-minio-admin ;;
        *) value="$(openssl rand -hex 24)" ;;
      esac
      printf '%s=%s\n' "$key" "$value"
    done < "$ROOT/.env.example" > "$STATE/secrets.env.tmp"
    printf 'DEMO_DB_PASSWORD=%s\n' "$(openssl rand -hex 24)" >> "$STATE/secrets.env.tmp"
    mv "$STATE/secrets.env.tmp" "$STATE/secrets.env"
  fi
  declare -A secret=()
  while IFS='=' read -r key value; do
    [[ "$key" =~ ^[A-Z][A-Z0-9_]*$ ]] && secret["$key"]="$value"
  done < "$STATE/secrets.env"
  k -n arch-infra create secret generic arch-infra-secrets --from-env-file="$STATE/secrets.env" \
    --dry-run=client -o yaml | k apply -f -
  for team in "${TEAMS[@]}"; do
    host=postgres; database=demo; password="${secret[DEMO_DB_PASSWORD]}"
    case "$team" in
      planning-system) s3_key=S3_PLANNING_SECRET ;;
      task-tracker) s3_key=S3_TASK_TRACKER_SECRET ;;
      reference-manager) s3_key=S3_REFERENCE_MANAGER_SECRET ;;
      qa) s3_key=S3_QA_SECRET ;;
      reports) s3_key=S3_REPORTS_SECRET; host=reports-db.arch-infra.svc.cluster.local
        database=reports; password="${secret[REPORTS_DB_PASSWORD]}" ;;
    esac
    {
      printf 'DATABASE_URL=postgresql://%s:%s@%s:5432/%s\n' "$database" "$password" "$host" "$database"
      printf 'POSTGRES_PASSWORD=%s\nS3_SECRET_KEY=%s\n' "$password" "${secret[$s3_key]}"
      printf 'KC_EXAMPLE_CALLER_SECRET=%s\n' "${secret[KC_EXAMPLE_CALLER_SECRET]}"
      printf 'KAFKA_EXAMPLE_PASSWORD=%s\n' "${secret[KAFKA_EXAMPLE_PASSWORD]}"
    } > "$STATE/$team.env"
    k -n "arch-$team" create secret generic demo-secrets --from-env-file="$STATE/$team.env" \
      --dry-run=client -o yaml | k apply -f -
  done
  printf 'Keycloak: http://localhost:18081/admin/\nUser: admin\nPassword: %s\n\nMinIO: http://localhost:19001\nUser: %s\nPassword: %s\n' \
    "${secret[KC_BOOTSTRAP_ADMIN_PASSWORD]}" "${secret[MINIO_ROOT_USER]}" "${secret[MINIO_ROOT_PASSWORD]}" > "$STATE/access.txt"
  echo "Credentials: $STATE/access.txt"
}

apply_configmaps() {
  # Mount existing files into the YAML workloads.
  k -n arch-infra create configmap otel-config \
    --from-file="collector.yaml=$ROOT/infra/config/otel/collector.yaml" --dry-run=client -o yaml | k apply -f -
  k -n arch-infra create configmap reports-db-init \
    --from-file="$ROOT/infra/config/postgres/10-replication.sh" \
    --from-file="$ROOT/infra/config/postgres/replica-entrypoint.sh" --dry-run=client -o yaml | k apply -f -
  k -n arch-infra create configmap kafka-scripts \
    --from-file="$MANIFESTS/config/kafka-init.sh" --from-file="$ROOT/infra/scripts/kafka-converge.sh" \
    --dry-run=client -o yaml | k apply -f -
  k -n arch-infra create configmap demo-keycloak \
    --from-file="$ROOT/infra/keycloak/realm/desired.json" --from-file="$ROOT/infra/scripts/keycloak_converge.py" \
    --dry-run=client -o yaml | k apply -f -
  k -n arch-infra create configmap demo-minio --from-file="$ROOT/infra/scripts/minio-converge.sh" \
    --dry-run=client -o yaml | k apply -f -
  k -n arch-infra create configmap demo-minio-policies --from-file="$ROOT/infra/config/minio/policies/" \
    --dry-run=client -o yaml | k apply -f -
}

open_ports() {
  mkdir -p "$STATE"
  for mapping in 'demo-gateway 18080:8080' 'keycloak 18081:8080' 'minio 19001:9001'; do
    read -r service ports <<< "$mapping"
    pidfile="$STATE/forward-$service.pid"
    if [[ -f "$pidfile" ]] && ps -p "$(cat "$pidfile")" -o args= | \
      grep -Fq "kubectl --context=$PROFILE -n arch-infra port-forward --address=127.0.0.1 service/$service $ports"; then
      continue
    fi
    nohup setsid kubectl --context="$PROFILE" -n arch-infra port-forward --address=127.0.0.1 \
      "service/$service" "$ports" > "$STATE/forward-$service.log" 2>&1 < /dev/null &
    echo "$!" > "$pidfile"
  done
  for port in 18080 18081 19001; do
    ready=false
    for attempt in {1..40}; do
      if curl -fsS --max-time 2 "http://127.0.0.1:$port/" > /dev/null 2>&1; then ready=true; break; fi
      sleep .5
    done
    if [[ "$ready" != true ]]; then echo "Port $port unavailable; logs: $STATE/forward-*.log" >&2; return 1; fi
  done
  echo 'Demo: http://localhost:18080'
}

case "${1:-help}" in
  up)
    minikube start -p "$PROFILE" --driver=docker --cpus="${DEMO_CPUS:-2}" \
      --memory="${DEMO_MEMORY:-4096}" --kubernetes-version=v1.37.2 --keep-context
    # Load the CNI through the host if the node cannot reach the image registry.
    kindnet_image="$(k -n kube-system get daemonset kindnet -o jsonpath='{.spec.template.spec.containers[0].image}')"
    docker image inspect "$kindnet_image" >/dev/null 2>&1 || docker pull "$kindnet_image"
    minikube -p "$PROFILE" image load "$kindnet_image"
    if [[ "$(k -n kube-system get daemonset kindnet -o jsonpath='{.status.numberReady}')" != 1 ]]; then
      k -n kube-system delete pod -l app=kindnet
    fi
    k wait --for=condition=Ready node --all --timeout=180s
    docker build -t "$MOCK_IMAGE" "$ROOT/infra/mocks/k8s-demo"
    minikube -p "$PROFILE" image load "$MOCK_IMAGE" --overwrite=true
    for image in postgres:18.6 apache/kafka:4.3.1 quay.io/keycloak/keycloak:26.7.4 \
      otel/opentelemetry-collector-contrib:0.149.0; do
      docker image inspect "$image" >/dev/null 2>&1 || docker pull "$image"
      minikube -p "$PROFILE" image load "$image"
    done
    if ! docker image inspect "$MINIO_IMAGE" >/dev/null 2>&1; then
      docker build -t "$MINIO_IMAGE" "$ROOT/infra/images/minio"
    fi
    minikube -p "$PROFILE" image load "$MINIO_IMAGE"

    # Deployment order: namespaces -> configuration -> stores -> bootstrap -> applications.
    k apply -f "$MANIFESTS/00-namespaces.yaml"
    prepare_secrets
    apply_configmaps
    k apply -f "$MANIFESTS/shared/"
    if k -n arch-infra get pod minio-0 --ignore-not-found \
      -o jsonpath='{.status.containerStatuses[*].state.waiting.reason}' | grep -Eq 'ImagePullBackOff|ErrImagePull'; then
      k -n arch-infra delete pod minio-0
    fi
    for name in keycloak-db reports-db reports-db-replica kafka minio; do
      k -n arch-infra rollout status "statefulset/$name" --timeout=600s
    done
    k -n arch-infra rollout status deployment/keycloak --timeout=600s
    k -n arch-infra rollout status deployment/otel-collector --timeout=180s
    k -n arch-infra exec kafka-0 -c kafka -- bash -c \
      'for attempt in {1..90}; do test -f /var/lib/kafka/config/bootstrapped && exit 0; sleep 2; done; exit 1'
    k -n arch-infra exec kafka-0 -c kafka -- cat /var/lib/kafka/certs/kafka.crt > "$STATE/kafka.crt"
    for team in "${TEAMS[@]}"; do
      k -n "arch-$team" create configmap demo-kafka-ca --from-file="kafka.crt=$STATE/kafka.crt" \
        --dry-run=client -o yaml | k apply -f -
    done
    k -n arch-infra delete job demo-keycloak-bootstrap demo-minio-bootstrap --ignore-not-found
    k apply -f "$MANIFESTS/bootstrap/"
    k -n arch-infra wait --for=condition=complete job/demo-keycloak-bootstrap job/demo-minio-bootstrap --timeout=360s
    for team in "${TEAMS[@]}"; do k -n "arch-$team" delete job demo-migrate --ignore-not-found; done
    k apply -f "$MANIFESTS/teams/"
    k apply -f "$MANIFESTS/60-gateway.yaml"
    # Refresh the reusable local image tag explicitly.
    for team in "${TEAMS[@]}"; do
      k -n "arch-$team" wait --for=condition=complete job/demo-migrate --timeout=360s
      k -n "arch-$team" rollout restart deployment/backend deployment/frontend
      k -n "arch-$team" rollout status deployment/backend --timeout=240s
      k -n "arch-$team" rollout status deployment/frontend --timeout=180s
    done
    k -n arch-infra rollout restart deployment/demo-gateway
    k -n arch-infra rollout status deployment/demo-gateway --timeout=180s
    open_ports
    "$0" check
    ;;
  open) open_ports ;;
  check) open_ports; python3 "$MANIFESTS/check.py" ;;
  status) k get pods,svc,pvc,jobs,cronjobs -A -l arch-demo=true ;;
  restart) open_ports; python3 "$MANIFESTS/check.py" --restart ;;
  stop)
    for pidfile in "$STATE"/forward-*.pid; do
      [[ -f "$pidfile" ]] || continue
      pid="$(cat "$pidfile")"
      if ps -p "$pid" -o args= | grep -Fq "kubectl --context=$PROFILE -n arch-infra port-forward"; then
        kill "$pid" 2>/dev/null || true
      fi
      rm -f "$pidfile"
    done
    minikube stop -p "$PROFILE"
    ;;
  *) echo 'Usage: infra/scripts/k8s-demo.sh up|open|check|status|restart|stop' ;;
esac
