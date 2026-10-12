# minikube

На машине, где готовился этот комплект 06.10.2026, команд `minikube` и `kubectl` не было. `infra/scripts/minikube-up.sh` в этом случае завершается с ошибкой. Манифесты лежат в `infra/k8s`, запуск кластера не выполнен и развёртывание всей системы не отмечается завершённым.

В манифестах есть primary и read-replica витрины Reports. Реплика проверена только в Compose: запись отклонена, lag около 0,26 с. В кластере этот путь не запускался. Образ `arch-info-minio` локальный, в кластер его нужно загрузить отдельно; в реестр он не публиковался.

Когда инструменты появятся:

```bash
minikube start --driver=docker --cpus=4 --memory=6g
minikube addons enable ingress storage-provisioner
kubectl create secret generic arch-infra-secrets -n arch-infra --from-env-file=.env
kubectl apply -k infra/k8s/overlays/minikube
```

NetworkPolicy для базы Keycloak объявлена. Стандартный CNI minikube может её не применять; для проверки политики нужен CNI с поддержкой NetworkPolicy, например Calico. Без этого политика остаётся записью, а не доказательством изоляции.

`minikube delete` удаляет кластер и не входит в обычный перезапуск. PVC при удалении pod сохраняются, пока не удалить PVC или кластер.

Ingress-хост `arch.local` — черновик. Его нужно добавить в `/etc/hosts` на IP minikube. Это не TLS общего стенда.
