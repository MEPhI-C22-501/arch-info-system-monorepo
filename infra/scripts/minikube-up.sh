#!/bin/bash
set -euo pipefail
if ! command -v minikube >/dev/null || ! command -v kubectl >/dev/null; then
  echo "minikube или kubectl не установлены. Манифесты: infra/k8s/overlays/minikube. Кластер не запускался." >&2
  exit 1
fi
echo "Дальше: minikube start и kubectl apply -k infra/k8s/overlays/minikube. Секрет arch-infra-secrets создайте из .env и не коммитьте его."
