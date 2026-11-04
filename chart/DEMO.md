# Лабораторна №4: Helm-чарт — журнал виконання

Текстовий вивід реальних команд, виконаних 2026-10-14, за зразком
`k8s/DEMO.md`. Вивід не редагувався. Місця, де щось пішло не так, лишено
в журналі з поясненням (позначені цитатою `>`).

**Середовище:** macOS (arm64), Docker 29.6.1, minikube v1.39.0, Kubernetes v1.37.0,
Helm v3.22.0+g144ca65. Доповнення: `ingress`, `metrics-server`.

**Підготовка (п.1).** Helm 3 встановлено через `brew install helm@3`: формула
`helm` уже ставить Helm 4. Перед роботою маніфести лаби 3 повторно
застосовано (`kubectl apply -f k8s/` → усі `unchanged`, `/api/health/` →
`{"status":"ok","version":"1.0.0",...}`). Потім namespace видалено
повністю (`kubectl delete namespace coworking-booking`), щоб імена не
конфліктували з Helm-релізом.

**Доступ з хоста:** `kubectl port-forward -n ingress-nginx
svc/ingress-nginx-controller 8081:80`, запити йдуть із заголовком `Host`
відповідного Ingress.

**Порядок у журналі хронологічний.** Пункт 9 (`helm test`, два релізи)
виконувався на живому релізі, тобто перед `helm uninstall` з 8.6.

## Що змінювалось у кожній ревізії (п.8)

| Ревізія | Команда | Що змінилось |
|---|---|---|
| 1 | `helm install -f values-dev.yaml` | Початкове встановлення: dev, по 1 репліці api/worker, образи 1.0.0, Ingress `dev.booking.local`, PVC 1Gi. |
| 2 | `helm upgrade --reuse-values --set image.api.tag=1.1.0` | Лише тег образу api 1.0.0 → 1.1.0; решта dev-значень збережена завдяки `--reuse-values`. `diff` маніфестів 1→2 — один рядок `image:`. Pre-upgrade hook перевірив БД перед оновленням. |
| 3 | `helm upgrade -f values-prod.yaml` | **failed**: prod збільшує PVC до 10Gi, а storageclass minikube не вміє розширювати томи. Helm встиг застосувати частину об'єктів, але ревізія позначена `failed`. |
| 4 | той самий `helm upgrade -f values-prod.yaml` з виправленим `pvc.yaml` | Prod: api 3 репліки, worker 2, обидва образи 1.1.0, більші ресурси, `DJANGO_DEBUG=0`, інтервал worker 60 с, Ingress `booking.example.com`. PVC лишився 1Gi (розмір наявного PVC зберігається). |
| 5 | `helm rollback booking 2` | Повернення значень і маніфестів ревізії 2: dev, 1 репліка, api 1.1.0, worker 1.0.0, `dev.booking.local`. Rollback — це нова ревізія 5 з описом «Rollback to 2», історія не переписується. Pre-upgrade hook на rollback не запускався. |

## Примітки

- **6.1.** У diff dev/prod різняться значення Secret (dev-заглушки проти
  тестових `prod-placeholder`, переданих через `--set`) і
  `checksum/config`/`checksum/secret`. Ці анотації перезапускають поди api
  і worker, коли змінюється ConfigMap або Secret, бо `envFrom` читається
  лише при старті контейнера.
- **7.1.** `[INFO] icon is recommended` — порада, а не помилка, тому іконку
  не вигадував. Без обов'язкових секретів `helm lint` лише інформує, а
  `helm template`/`install` падають з `secret.postgresPassword is
  required`.
- **7.2.** Набір об'єктів збігається з лабою 3. Відмінності:
  - **Secret** тепер у чарті (у лабі 3 — через `kubectl create secret`);
  - **Job** і **Pod** — hook і test, вони не входять у маніфест релізу;
  - **Namespace** не рендериться (`namespace.create: false`), бо його
    створює `--create-namespace`, а Namespace у самому релізі конфліктував
    би з ним;
  - імена мають префікс релізу (`booking-api` замість `api`).
- **7.3.** RESTARTS 2 у api і worker одразу після встановлення мають ту саму
  причину, що й у лабі 3: postgres ще не приймав з'єднань.
- **8.1.** Перший curl одразу після `rollout status` потрапив на старий под
  1.0.0, бо ingress-nginx ще не оновив ендпоінти. Повтор через 10 с
  відповідає з нового пода 1.1.0.
- **8.2/8.3.** Під час переходу на prod пароль БД передано той самий, узятий з
  поточного Secret. Postgres застосовує `POSTGRES_PASSWORD` лише при першій
  ініціалізації тому.

## Журнал

### 6.1 Рендер для двох середовищ (без встановлення)

```
$ helm template booking chart/ -f chart/values-dev.yaml > /tmp/dev.yaml && helm template booking chart/ -f chart/values-prod.yaml --set secret.postgresPassword=prod-placeholder --set secret.djangoSecretKey=prod-placeholder > /tmp/prod.yaml && wc -l /tmp/dev.yaml /tmp/prod.yaml
     418 /tmp/dev.yaml
     418 /tmp/prod.yaml
     836 total
```

```
$ diff /tmp/dev.yaml /tmp/prod.yaml
16,17c16,17
<   POSTGRES_PASSWORD: "ZGV2LW9ubHktcGFzc3dvcmQ="
<   DJANGO_SECRET_KEY: "ZGV2LW9ubHktaW5zZWN1cmUtc2VjcmV0LWtleQ=="
---
>   POSTGRES_PASSWORD: "cHJvZC1wbGFjZWhvbGRlcg=="
>   DJANGO_SECRET_KEY: "cHJvZC1wbGFjZWhvbGRlcg=="
36c36
<   DJANGO_DEBUG: "1"
---
>   DJANGO_DEBUG: "0"
38c38
<   BOOKING_TIMEOUT_CHECK_INTERVAL: "15"
---
>   BOOKING_TIMEOUT_CHECK_INTERVAL: "60"
58c58
<       storage: 1Gi
---
>       storage: 10Gi
120c120
<   replicas: 1
---
>   replicas: 3
143,144c143,144
<         checksum/config: 6f54ed050f6387191176eccec49e00ce3f888e67ccb8d3f0059914230e3be4b2
<         checksum/secret: 355483a988e7fdc8208b234448966c1a913b1aa1bb0d6fdd6de27952edd3a594
---
>         checksum/config: b53b8ce2a13f4596464808ffa1afde5a85938a061151c2e7245891ec80ef4f30
>         checksum/secret: 22069a229ba46d69cf645b959a1093ef656a3b41aa05ec20cb7b9766170e3577
148c148
<           image: ghcr.io/marcogr11/devops-api:1.0.0
---
>           image: ghcr.io/marcogr11/devops-api:1.1.0
160,161c160,161
<               cpu: 250m
<               memory: 192Mi
---
>               cpu: "1"
>               memory: 512Mi
163,164c163,164
<               cpu: 50m
<               memory: 96Mi
---
>               cpu: 250m
>               memory: 256Mi
241,242c241,242
<               cpu: 250m
<               memory: 256Mi
---
>               cpu: "1"
>               memory: 1Gi
244,245c244,245
<               cpu: 50m
<               memory: 96Mi
---
>               cpu: 250m
>               memory: 512Mi
268c268
<   replicas: 1
---
>   replicas: 2
285,286c285,286
<         checksum/config: 6f54ed050f6387191176eccec49e00ce3f888e67ccb8d3f0059914230e3be4b2
<         checksum/secret: 355483a988e7fdc8208b234448966c1a913b1aa1bb0d6fdd6de27952edd3a594
---
>         checksum/config: b53b8ce2a13f4596464808ffa1afde5a85938a061151c2e7245891ec80ef4f30
>         checksum/secret: 22069a229ba46d69cf645b959a1093ef656a3b41aa05ec20cb7b9766170e3577
290c290
<           image: ghcr.io/marcogr11/devops-worker:1.0.0
---
>           image: ghcr.io/marcogr11/devops-worker:1.1.0
299,300c299,300
<               cpu: 100m
<               memory: 96Mi
---
>               cpu: 250m
>               memory: 256Mi
302,303c302,303
<               cpu: 20m
<               memory: 32Mi
---
>               cpu: 100m
>               memory: 128Mi
321c321
<     - host: "dev.booking.local"
---
>     - host: "booking.example.com"
```

### 6.2 Пріоритет значень: values.yaml → -f → --set

```
$ helm template booking chart/ -s templates/deployment-api.yaml | grep -E "^  replicas:|image:"   # лише values.yaml
  replicas: 2
          image: ghcr.io/marcogr11/devops-api:1.0.0
```

```
$ helm template booking chart/ -s templates/deployment-api.yaml -f chart/values-dev.yaml | grep -E "^  replicas:|image:"   # + values-dev.yaml
  replicas: 1
          image: ghcr.io/marcogr11/devops-api:1.0.0
```

```
$ helm template booking chart/ -s templates/deployment-api.yaml -f chart/values-dev.yaml --set replicaCount.api=4 --set image.api.tag=1.1.0 | grep -E "^  replicas:|image:"   # + --set
  replicas: 4
          image: ghcr.io/marcogr11/devops-api:1.1.0
```

### 7.1 helm lint

```
$ helm lint chart/ -f chart/values-dev.yaml
==> Linting chart/
[INFO] Chart.yaml: icon is recommended

1 chart(s) linted, 0 chart(s) failed
```

```
$ helm lint chart/ -f chart/values-prod.yaml --set secret.postgresPassword=x --set secret.djangoSecretKey=y
==> Linting chart/
[INFO] Chart.yaml: icon is recommended

1 chart(s) linted, 0 chart(s) failed
```

```
$ helm lint chart/ -f chart/values-prod.yaml   # без секретів: lint лише інформує (INFO), див. наступну команду
engine.go:214: [INFO] Missing required value: secret.postgresPassword is required
engine.go:214: [INFO] Missing required value: secret.djangoSecretKey is required
engine.go:214: [INFO] Missing required value: secret.postgresPassword is required
engine.go:214: [INFO] Missing required value: secret.djangoSecretKey is required
engine.go:214: [INFO] Missing required value: secret.postgresPassword is required
engine.go:214: [INFO] Missing required value: secret.djangoSecretKey is required
==> Linting chart/
[INFO] Chart.yaml: icon is recommended

1 chart(s) linted, 0 chart(s) failed
```

```
$ helm template booking chart/ -f chart/values-prod.yaml > /dev/null   # а рендер/встановлення без секретів падає
Error: execution error at (booking/templates/secret.yaml:9:24): secret.postgresPassword is required

Use --debug flag to render out invalid YAML
(exit code 1)
```

### 7.2 Набір об'єктів: чарт (dev) vs k8s/ з лаби 3

```
$ echo "--- helm template (dev):"; helm template booking chart/ -f chart/values-dev.yaml | grep -E "^kind:|^  name:" | paste - - | sed "s/kind: //;s/  name: / /" | sort; echo "--- k8s/ (лаба 3):"; cat k8s/*.yaml | grep -E "^kind:|^  name:" | paste - - | sed "s/kind: //;s/  name: / /" | sort
--- helm template (dev):
ConfigMap	 booking-config
Deployment	 booking-api
Deployment	 booking-postgres
Deployment	 booking-worker
Ingress	 booking-api
Job	 booking-db-check
PersistentVolumeClaim	 booking-postgres-data
Pod	 booking-test-health
Secret	 booking-secret
Service	 booking-api
Service	 booking-postgres
--- k8s/ (лаба 3):
ConfigMap	 booking-config
Deployment	 api
Deployment	 postgres
Deployment	 worker
Ingress	 api
Namespace	 coworking-booking
PersistentVolumeClaim	 postgres-data
Service	 api
Service	 postgres
```

### 7.3 Встановлення

```
$ helm install booking chart/ -f chart/values-dev.yaml -n coworking-booking --create-namespace
NAME: booking
LAST DEPLOYED: Wed Oct 14 01:19:09 2026
NAMESPACE: coworking-booking
STATUS: deployed
REVISION: 1
NOTES:
Release "booking" (booking 0.1.0) installed in namespace "coworking-booking".
api image: ghcr.io/marcogr11/devops-api:1.0.0, replicas: 1

Wait for the pods:
  kubectl get pods -n coworking-booking -l app.kubernetes.io/instance=booking -w

Via Ingress (host dev.booking.local):
  minikube tunnel   # in a separate terminal; add "127.0.0.1 dev.booking.local" to /etc/hosts
  curl http://dev.booking.local/api/health/

Via port-forward:
  kubectl port-forward -n coworking-booking svc/booking-api 8080:80
  curl http://localhost:8080/api/health/

Smoke test:
  helm test booking -n coworking-booking
```

```
$ kubectl get pods,svc,ingress,pvc,configmap,secret -n coworking-booking
NAME                                    READY   STATUS    RESTARTS      AGE
pod/booking-api-cbc7c7556-j4hpb         1/1     Running   2 (17s ago)   23s
pod/booking-postgres-65c7b87bf9-8vxn2   1/1     Running   0             23s
pod/booking-worker-7695b9f9bb-p8hb8     1/1     Running   2 (20s ago)   23s

NAME                       TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)    AGE
service/booking-api        ClusterIP   10.103.125.191   <none>        80/TCP     23s
service/booking-postgres   ClusterIP   10.106.86.197    <none>        5432/TCP   23s

NAME                                    CLASS   HOSTS               ADDRESS        PORTS   AGE
ingress.networking.k8s.io/booking-api   nginx   dev.booking.local   192.168.49.2   80      23s

NAME                                          STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
persistentvolumeclaim/booking-postgres-data   Bound    pvc-88d89fb6-a68d-4a5c-a85e-d894fd9528b7   1Gi        RWO            standard       <unset>                 23s

NAME                         DATA   AGE
configmap/booking-config     8      23s
configmap/kube-root-ca.crt   1      23s

NAME                                   TYPE                 DATA   AGE
secret/booking-secret                  Opaque               2      23s
secret/sh.helm.release.v1.booking.v1   helm.sh/release.v1   1      23s
```

### 7.4 Стан релізу

```
$ helm list -n coworking-booking
NAME   	NAMESPACE        	REVISION	UPDATED                              	STATUS  	CHART        	APP VERSION
booking	coworking-booking	1       	2026-10-14 01:19:09.923231 +0300 EEST	deployed	booking-0.1.0	1.0.0      
```

```
$ helm status booking -n coworking-booking | head -6
NAME: booking
LAST DEPLOYED: Wed Oct 14 01:19:09 2026
NAMESPACE: coworking-booking
STATUS: deployed
REVISION: 1
NOTES:
```

```
$ helm get values booking -n coworking-booking
USER-SUPPLIED VALUES:
config:
  bookingTimeoutCheckInterval: "15"
  djangoDebug: "1"
image:
  api:
    tag: 1.0.0
  worker:
    tag: 1.0.0
ingress:
  enabled: true
  host: dev.booking.local
postgres:
  persistence:
    size: 1Gi
replicaCount:
  api: 1
  worker: 1
resources:
  api:
    limits:
      cpu: 250m
      memory: 192Mi
    requests:
      cpu: 50m
      memory: 96Mi
  postgres:
    limits:
      cpu: 250m
      memory: 256Mi
    requests:
      cpu: 50m
      memory: 96Mi
  worker:
    limits:
      cpu: 100m
      memory: 96Mi
    requests:
      cpu: 20m
      memory: 32Mi
```

### 7.5 Де Helm зберігає стан релізу

```
$ kubectl get secrets -n coworking-booking | grep helm
sh.helm.release.v1.booking.v1   helm.sh/release.v1   1      35s
```

```
$ kubectl get secret sh.helm.release.v1.booking.v1 -n coworking-booking -o jsonpath="{.metadata.labels}"; echo; kubectl get secret sh.helm.release.v1.booking.v1 -n coworking-booking -o jsonpath="{.data.release}" | base64 -d | base64 -d | gunzip | python3 -c "import sys,json;r=json.load(sys.stdin);print(\"name:\",r[\"name\"],\"| version:\",r[\"version\"],\"| status:\",r[\"info\"][\"status\"],\"| chart:\",r[\"chart\"][\"metadata\"][\"name\"],r[\"chart\"][\"metadata\"][\"version\"],\"| manifest bytes:\",len(r[\"manifest\"]))"
{"modifiedAt":"1791929950","name":"booking","owner":"helm","status":"deployed","version":"1"}
name: booking | version: 1 | status: deployed | chart: booking 0.1.0 | manifest bytes: 9650
```

### 7.6 Доступ до застосунку

```
$ curl -s -H "Host: dev.booking.local" http://localhost:8081/api/health/
{"status":"ok","version":"1.0.0","pod":"booking-api-cbc7c7556-j4hpb"}
```

### 8.1 Upgrade через --set (ревізія 2)

```
$ helm upgrade booking chart/ -n coworking-booking --reuse-values --set image.api.tag=1.1.0 | head -6
Release "booking" has been upgraded. Happy Helming!
NAME: booking
LAST DEPLOYED: Wed Oct 14 01:20:01 2026
NAMESPACE: coworking-booking
STATUS: deployed
REVISION: 2
```

```
$ cat /private/tmp/claude-501/-Users-admin-PycharmProjects-DevOps-lab1/7aaf2daa-b7a1-4759-9d4e-1ca7bcb60df6/scratchpad/hook1.log   # лог pre-upgrade Job booking-db-check, знятий під час upgrade
database booking at booking-postgres:5432 is ready
```

```
$ kubectl get events -n coworking-booking --field-selector involvedObject.kind=Job --sort-by=.lastTimestamp
LAST SEEN   TYPE     REASON             OBJECT                 MESSAGE
3s          Normal   SuccessfulCreate   job/booking-db-check   Created pod: booking-db-check-q24jb
0s          Normal   Completed          job/booking-db-check   Job completed
```

```
$ kubectl get deploy -n coworking-booking -o custom-columns=NAME:.metadata.name,REPLICAS:.spec.replicas,IMAGE:.spec.template.spec.containers[0].image; curl -s -H "Host: dev.booking.local" http://localhost:8081/api/health/
NAME               REPLICAS   IMAGE
booking-api        1          ghcr.io/marcogr11/devops-api:1.1.0
booking-postgres   1          postgres:16-alpine
booking-worker     1          ghcr.io/marcogr11/devops-worker:1.0.0
{"status":"ok","version":"1.0.0","pod":"booking-api-cbc7c7556-j4hpb"}
```

```
$ kubectl get pods -n coworking-booking -l app.kubernetes.io/component=api; curl -s -H "Host: dev.booking.local" http://localhost:8081/api/health/   # повтор через 10 с
NAME                          READY   STATUS        RESTARTS      AGE
booking-api-674f7cf49-hc5fn   1/1     Running       0             23s
booking-api-cbc7c7556-j4hpb   1/1     Terminating   2 (71s ago)   77s
{"status":"ok","version":"1.1.0","pod":"booking-api-674f7cf49-hc5fn"}
```

### 8.2 Upgrade повним файлом values-prod.yaml (ревізія 3)

```
$ helm upgrade booking chart/ -n coworking-booking -f chart/values-prod.yaml --set secret.postgresPassword="$(kubectl get secret booking-secret -n coworking-booking -o jsonpath={.data.POSTGRES_PASSWORD} | base64 -d)" --set secret.djangoSecretKey="$(openssl rand -hex 32)" | head -6
Error: UPGRADE FAILED: cannot patch "booking-postgres-data" with kind PersistentVolumeClaim: persistentvolumeclaims "booking-postgres-data" is forbidden: only dynamically provisioned pvc can be resized and the storageclass that provisions the pvc must support resize
```

```
$ cat /private/tmp/claude-501/-Users-admin-PycharmProjects-DevOps-lab1/7aaf2daa-b7a1-4759-9d4e-1ca7bcb60df6/scratchpad/hook2.log   # лог pre-upgrade Job
database booking at booking-postgres:5432 is ready
```

```
$ kubectl get deploy,ingress -n coworking-booking -o wide
NAME                               READY   UP-TO-DATE   AVAILABLE   AGE    CONTAINERS   IMAGES                                  SELECTOR
deployment.apps/booking-api        3/3     3            3           2m7s   api          ghcr.io/marcogr11/devops-api:1.1.0      app.kubernetes.io/component=api,app.kubernetes.io/instance=booking,app.kubernetes.io/name=booking
deployment.apps/booking-postgres   1/1     1            1           2m7s   postgres     postgres:16-alpine                      app.kubernetes.io/component=postgres,app.kubernetes.io/instance=booking,app.kubernetes.io/name=booking
deployment.apps/booking-worker     2/2     2            2           2m7s   worker       ghcr.io/marcogr11/devops-worker:1.1.0   app.kubernetes.io/component=worker,app.kubernetes.io/instance=booking,app.kubernetes.io/name=booking

NAME                                    CLASS   HOSTS                 ADDRESS        PORTS   AGE
ingress.networking.k8s.io/booking-api   nginx   booking.example.com   192.168.49.2   80      2m7s
```

```
$ kubectl get pods -n coworking-booking
NAME                                READY   STATUS        RESTARTS   AGE
booking-api-674f7cf49-csxqf         1/1     Terminating   0          29s
booking-api-674f7cf49-hc5fn         1/1     Terminating   0          73s
booking-api-674f7cf49-xpl4r         1/1     Terminating   0          29s
booking-api-7b9ddcf4dd-rrk9v        1/1     Running       0          16s
booking-api-7b9ddcf4dd-tfzcm        1/1     Running       0          29s
booking-api-7b9ddcf4dd-vpcg6        1/1     Running       0          22s
booking-postgres-69f4d4fbc7-vtnfn   1/1     Running       0          29s
booking-worker-759bdf5b74-jrzph     1/1     Running       0          25s
booking-worker-759bdf5b74-vdmdv     1/1     Running       0          29s
booking-worker-7695b9f9bb-dk2v8     1/1     Terminating   0          29s
```

```
$ for i in 1 2 3 4 5 6; do curl -s -H "Host: booking.example.com" http://localhost:8081/api/health/; echo; done
{"status":"ok","version":"1.1.0","pod":"booking-api-7b9ddcf4dd-rrk9v"}
{"status":"ok","version":"1.1.0","pod":"booking-api-7b9ddcf4dd-rrk9v"}
{"status":"ok","version":"1.1.0","pod":"booking-api-7b9ddcf4dd-tfzcm"}
{"status":"ok","version":"1.1.0","pod":"booking-api-7b9ddcf4dd-vpcg6"}
{"status":"ok","version":"1.1.0","pod":"booking-api-7b9ddcf4dd-rrk9v"}
{"status":"ok","version":"1.1.0","pod":"booking-api-7b9ddcf4dd-tfzcm"}
```

> Ревізія 3 впала: values-prod.yaml збільшує PVC 1Gi → 10Gi, а storageclass `standard` у minikube не підтримує розширення томів. Helm 3 встиг застосувати частину об'єктів (Deployment-и на 1.1.0), але ревізія позначена `failed`. Виправлення в чарті: `templates/pvc.yaml` через `lookup` зберігає розмір наявного PVC, а `persistence.size` діє лише при першому встановленні. Далі — повторний upgrade з виправленим чартом.

### 8.3 Повторний upgrade values-prod.yaml з виправленим чартом (ревізія 4)

```
$ helm upgrade booking chart/ -n coworking-booking -f chart/values-prod.yaml --set secret.postgresPassword="$(kubectl get secret booking-secret -n coworking-booking -o jsonpath={.data.POSTGRES_PASSWORD} | base64 -d)" --set secret.djangoSecretKey="$(kubectl get secret booking-secret -n coworking-booking -o jsonpath={.data.DJANGO_SECRET_KEY} | base64 -d)" | head -6
Release "booking" has been upgraded. Happy Helming!
NAME: booking
LAST DEPLOYED: Wed Oct 14 01:21:51 2026
NAMESPACE: coworking-booking
STATUS: deployed
REVISION: 4
```

```
$ cat /private/tmp/claude-501/-Users-admin-PycharmProjects-DevOps-lab1/7aaf2daa-b7a1-4759-9d4e-1ca7bcb60df6/scratchpad/hook3.log   # лог pre-upgrade Job
database booking at booking-postgres:5432 is ready
```

```
$ kubectl get deploy -n coworking-booking -o custom-columns=NAME:.metadata.name,REPLICAS:.spec.replicas,IMAGE:.spec.template.spec.containers[0].image,CPU_REQ:.spec.template.spec.containers[0].resources.requests.cpu; kubectl get pvc,ingress -n coworking-booking
NAME               REPLICAS   IMAGE                                   CPU_REQ
booking-api        3          ghcr.io/marcogr11/devops-api:1.1.0      250m
booking-postgres   1          postgres:16-alpine                      250m
booking-worker     2          ghcr.io/marcogr11/devops-worker:1.1.0   100m
NAME                                          STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
persistentvolumeclaim/booking-postgres-data   Bound    pvc-88d89fb6-a68d-4a5c-a85e-d894fd9528b7   1Gi        RWO            standard       <unset>                 2m52s

NAME                                    CLASS   HOSTS                 ADDRESS        PORTS   AGE
ingress.networking.k8s.io/booking-api   nginx   booking.example.com   192.168.49.2   80      2m52s
```

```
$ for i in 1 2 3 4 5 6; do curl -s -H "Host: booking.example.com" http://localhost:8081/api/health/; echo; done
{"status":"ok","version":"1.1.0","pod":"booking-api-7b9ddcf4dd-tfzcm"}
{"status":"ok","version":"1.1.0","pod":"booking-api-7b9ddcf4dd-vpcg6"}
{"status":"ok","version":"1.1.0","pod":"booking-api-7b9ddcf4dd-vpcg6"}
{"status":"ok","version":"1.1.0","pod":"booking-api-7b9ddcf4dd-rrk9v"}
{"status":"ok","version":"1.1.0","pod":"booking-api-7b9ddcf4dd-tfzcm"}
{"status":"ok","version":"1.1.0","pod":"booking-api-7b9ddcf4dd-vpcg6"}
```

### 8.4 Історія ревізій

```
$ helm history booking -n coworking-booking --max 10 -o table | cut -c1-140
REVISION	UPDATED                 	STATUS    	CHART        	APP VERSION	DESCRIPTION                                                          
1       	Wed Oct 14 01:19:09 2026	superseded	booking-0.1.0	1.0.0      	Install complete                                                     
2       	Wed Oct 14 01:20:01 2026	superseded	booking-0.1.0	1.0.0      	Upgrade complete                                                     
3       	Wed Oct 14 01:20:44 2026	failed    	booking-0.1.0	1.0.0      	Upgrade "booking" failed: cannot patch "booking-postgres-data" with k
4       	Wed Oct 14 01:21:51 2026	deployed  	booking-0.1.0	1.0.0      	Upgrade complete                                                     
```

```
$ for r in 1 2 4; do echo "== revision $r"; helm get values booking -n coworking-booking --revision $r -o json | python3 -c "import sys,json;v=json.load(sys.stdin);s=v.get(\"secret\");v[\"secret\"]=\"<hidden>\" if s else None;v.pop(\"resources\",None);print(json.dumps({k:x for k,x in v.items() if x is not None},sort_keys=True))"; done   # resources і secret приховано для стислості
== revision 1
{"config": {"bookingTimeoutCheckInterval": "15", "djangoDebug": "1"}, "image": {"api": {"tag": "1.0.0"}, "worker": {"tag": "1.0.0"}}, "ingress": {"enabled": true, "host": "dev.booking.local"}, "postgres": {"persistence": {"size": "1Gi"}}, "replicaCount": {"api": 1, "worker": 1}}
== revision 2
{"config": {"bookingTimeoutCheckInterval": "15", "djangoDebug": "1"}, "image": {"api": {"tag": "1.1.0"}, "worker": {"tag": "1.0.0"}}, "ingress": {"enabled": true, "host": "dev.booking.local"}, "postgres": {"persistence": {"size": "1Gi"}}, "replicaCount": {"api": 1, "worker": 1}}
== revision 4
{"config": {"bookingTimeoutCheckInterval": "60", "djangoDebug": "0"}, "image": {"api": {"tag": "1.1.0"}, "worker": {"tag": "1.1.0"}}, "ingress": {"enabled": true, "host": "booking.example.com"}, "postgres": {"persistence": {"size": "10Gi"}}, "replicaCount": {"api": 3, "worker": 2}, "secret": "<hidden>"}
```


```
$ helm get manifest booking -n coworking-booking --revision 1 > /tmp/r1.yaml; helm get manifest booking -n coworking-booking --revision 2 > /tmp/r2.yaml; diff /tmp/r1.yaml /tmp/r2.yaml   # 1 → 2: лише образ api (+ шаблон пода змінився → rolling update)
148c148
<           image: ghcr.io/marcogr11/devops-api:1.0.0
---
>           image: ghcr.io/marcogr11/devops-api:1.1.0
```

```
$ curl -s -o /dev/null -w "GET /api/resources/ -> %{http_code}\n" -H "Host: booking.example.com" http://localhost:8081/api/resources/   # api досі автентифікується в БД
GET /api/resources/ -> 200
```

### 8.5 Rollback на ревізію 2

```
$ helm rollback booking 2 -n coworking-booking
Rollback was a success! Happy Helming!
```

```
$ helm history booking -n coworking-booking -o table | cut -c1-140
REVISION	UPDATED                 	STATUS    	CHART        	APP VERSION	DESCRIPTION                                                          
1       	Wed Oct 14 01:19:09 2026	superseded	booking-0.1.0	1.0.0      	Install complete                                                     
2       	Wed Oct 14 01:20:01 2026	superseded	booking-0.1.0	1.0.0      	Upgrade complete                                                     
3       	Wed Oct 14 01:20:44 2026	failed    	booking-0.1.0	1.0.0      	Upgrade "booking" failed: cannot patch "booking-postgres-data" with k
4       	Wed Oct 14 01:21:51 2026	superseded	booking-0.1.0	1.0.0      	Upgrade complete                                                     
5       	Wed Oct 14 01:22:37 2026	deployed  	booking-0.1.0	1.0.0      	Rollback to 2                                                        
```

```
$ kubectl get deploy -n coworking-booking -o custom-columns=NAME:.metadata.name,REPLICAS:.spec.replicas,IMAGE:.spec.template.spec.containers[0].image; kubectl get ingress -n coworking-booking
NAME               REPLICAS   IMAGE
booking-api        1          ghcr.io/marcogr11/devops-api:1.1.0
booking-postgres   1          postgres:16-alpine
booking-worker     1          ghcr.io/marcogr11/devops-worker:1.0.0
NAME          CLASS   HOSTS               ADDRESS        PORTS   AGE
booking-api   nginx   dev.booking.local   192.168.49.2   80      3m44s
```


```
$ kubectl get events -n coworking-booking --field-selector involvedObject.kind=Job -o custom-columns=TIME:.lastTimestamp,REASON:.reason,MSG:.message   # 3 запуски pre-upgrade hook = ревізії 2,3,4 (22:20:01, 22:20:44, 22:21:51 UTC); на rollback (22:22:37) hook не запускався
TIME                   REASON             MSG
2026-10-13T22:20:01Z   SuccessfulCreate   Created pod: booking-db-check-q24jb
2026-10-13T22:20:04Z   Completed          Job completed
2026-10-13T22:20:45Z   SuccessfulCreate   Created pod: booking-db-check-g9xd7
2026-10-13T22:20:48Z   Completed          Job completed
2026-10-13T22:21:51Z   SuccessfulCreate   Created pod: booking-db-check-sttsc
2026-10-13T22:21:54Z   Completed          Job completed
```

```
$ curl -s -H "Host: dev.booking.local" http://localhost:8081/api/health/
{"status":"ok","version":"1.1.0","pod":"booking-api-674f7cf49-mfncs"}
```

### 9.1 helm test

```
$ helm test booking -n coworking-booking
NAME: booking
LAST DEPLOYED: Wed Oct 14 01:22:37 2026
NAMESPACE: coworking-booking
STATUS: deployed
REVISION: 5
TEST SUITE:     booking-test-health
Last Started:   Wed Oct 14 01:23:19 2026
Last Completed: Wed Oct 14 01:23:25 2026
Phase:          Succeeded
NOTES:
Release "booking" (booking 0.1.0) installed in namespace "coworking-booking".
api image: ghcr.io/marcogr11/devops-api:1.1.0, replicas: 1

Wait for the pods:
  kubectl get pods -n coworking-booking -l app.kubernetes.io/instance=booking -w

Via Ingress (host dev.booking.local):
  minikube tunnel   # in a separate terminal; add "127.0.0.1 dev.booking.local" to /etc/hosts
  curl http://dev.booking.local/api/health/

Via port-forward:
  kubectl port-forward -n coworking-booking svc/booking-api 8080:80
  curl http://localhost:8080/api/health/

Smoke test:
  helm test booking -n coworking-booking
```

```
$ kubectl logs booking-test-health -n coworking-booking
GET http://booking-api:80/api/health/ -> {"status":"ok","version":"1.1.0","pod":"booking-api-674f7cf49-mfncs"}
```

```
$ kubectl get pod booking-test-health -n coworking-booking -o jsonpath="phase={.status.phase} annotations={.metadata.annotations}{\"\n\"}"
phase=Succeeded annotations={"helm.sh/hook":"test","helm.sh/hook-delete-policy":"before-hook-creation"}
```

### 9.2 Два релізи одного чарта в одному namespace

```
$ helm install demo chart/ -f chart/values-dev.yaml --set ingress.enabled=false -n coworking-booking --wait --timeout 5m | head -5
NAME: demo
LAST DEPLOYED: Wed Oct 14 01:23:40 2026
NAMESPACE: coworking-booking
STATUS: deployed
REVISION: 1
```

```
$ helm list -n coworking-booking
NAME   	NAMESPACE        	REVISION	UPDATED                              	STATUS  	CHART        	APP VERSION
booking	coworking-booking	5       	2026-10-14 01:22:37.110343 +0300 EEST	deployed	booking-0.1.0	1.0.0      
demo   	coworking-booking	1       	2026-10-14 01:23:40.534363 +0300 EEST	deployed	booking-0.1.0	1.0.0      
```

```
$ kubectl get deploy,svc,pvc,secret -n coworking-booking -L app.kubernetes.io/instance
NAME                                    READY   UP-TO-DATE   AVAILABLE   AGE     INSTANCE
deployment.apps/booking-api             1/1     1            1           4m54s   booking
deployment.apps/booking-postgres        1/1     1            1           4m54s   booking
deployment.apps/booking-worker          1/1     1            1           4m54s   booking
deployment.apps/demo-booking-api        1/1     1            1           24s     demo
deployment.apps/demo-booking-postgres   1/1     1            1           24s     demo
deployment.apps/demo-booking-worker     1/1     1            1           24s     demo

NAME                            TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)    AGE     INSTANCE
service/booking-api             ClusterIP   10.103.125.191   <none>        80/TCP     4m54s   booking
service/booking-postgres        ClusterIP   10.106.86.197    <none>        5432/TCP   4m54s   booking
service/demo-booking-api        ClusterIP   10.107.97.23     <none>        80/TCP     24s     demo
service/demo-booking-postgres   ClusterIP   10.104.44.114    <none>        5432/TCP   24s     demo

NAME                                               STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE     INSTANCE
persistentvolumeclaim/booking-postgres-data        Bound    pvc-88d89fb6-a68d-4a5c-a85e-d894fd9528b7   1Gi        RWO            standard       <unset>                 4m54s   booking
persistentvolumeclaim/demo-booking-postgres-data   Bound    pvc-535602e6-ddd9-428c-9200-59ede3893ed9   1Gi        RWO            standard       <unset>                 24s     demo

NAME                                   TYPE                 DATA   AGE     INSTANCE
secret/booking-secret                  Opaque               2      4m54s   booking
secret/demo-booking-secret             Opaque               2      24s     demo
secret/sh.helm.release.v1.booking.v1   helm.sh/release.v1   1      4m54s   
secret/sh.helm.release.v1.booking.v2   helm.sh/release.v1   1      4m3s    
secret/sh.helm.release.v1.booking.v3   helm.sh/release.v1   1      3m19s   
secret/sh.helm.release.v1.booking.v4   helm.sh/release.v1   1      2m13s   
secret/sh.helm.release.v1.booking.v5   helm.sh/release.v1   1      87s     
secret/sh.helm.release.v1.demo.v1      helm.sh/release.v1   1      24s     
```

```
$ helm test demo -n coworking-booking | grep -E "TEST SUITE|Phase"; kubectl logs demo-booking-test-health -n coworking-booking
TEST SUITE:     demo-booking-test-health
Phase:          Succeeded
GET http://demo-booking-api:80/api/health/ -> {"status":"ok","version":"1.0.0","pod":"demo-booking-api-5f5d57d9ff-67kjn"}
```

```
$ helm uninstall demo -n coworking-booking
release "demo" uninstalled
```

### 8.6 Видалення релізу

```
$ helm uninstall booking -n coworking-booking
release "booking" uninstalled
```

```
$ kubectl get all -n coworking-booking
NAME                           READY   STATUS      RESTARTS   AGE
pod/booking-test-health        0/1     Completed   0          93s
pod/demo-booking-test-health   0/1     Completed   0          48s
```

```
$ kubectl get configmap,secret,pvc,ingress,jobs -n coworking-booking; kubectl get pv; helm list -n coworking-booking
NAME                         DATA   AGE
configmap/kube-root-ca.crt   1      5m43s
No resources found
NAME	NAMESPACE	REVISION	UPDATED	STATUS	CHART	APP VERSION
```

> Після `uninstall` лишились два тестові поди: Helm не відстежує hook-ресурси як частину релізу, а політика `before-hook-creation` видаляла под лише перед наступним запуском тесту. Виправлення: `helm.sh/hook-delete-policy: before-hook-creation,hook-succeeded` у `templates/tests/test-health.yaml`, а лог тесту тепер виводить `helm test --logs`. Залишки прибрано вручну, далі — повторний цикл з виправленим чартом.

```
$ kubectl delete pod booking-test-health demo-booking-test-health -n coworking-booking
pod "booking-test-health" deleted from coworking-booking namespace
pod "demo-booking-test-health" deleted from coworking-booking namespace
```

### 8.7 Повторний цикл з виправленим чартом: install → test → uninstall

```
$ helm install booking chart/ -f chart/values-dev.yaml -n coworking-booking --wait --timeout 5m | head -5
NAME: booking
LAST DEPLOYED: Wed Oct 14 01:25:07 2026
NAMESPACE: coworking-booking
STATUS: deployed
REVISION: 1
```

```
$ helm test --logs booking -n coworking-booking | grep -v -E "^(NOTES|Release|api image|Wait|Via|Smoke|  |$)"
Error: unable to get pod logs for booking-test-health: pods "booking-test-health" not found
NAME: booking
LAST DEPLOYED: Wed Oct 14 01:25:07 2026
NAMESPACE: coworking-booking
STATUS: deployed
REVISION: 1
TEST SUITE:     booking-test-health
Last Started:   Wed Oct 14 01:25:37 2026
Last Completed: Wed Oct 14 01:25:39 2026
Phase:          Succeeded
```

```
$ helm uninstall booking -n coworking-booking
release "booking" uninstalled
```

```
$ kubectl get all -n coworking-booking
No resources found in coworking-booking namespace.
```

```
$ kubectl get configmap,secret,pvc,ingress,jobs -n coworking-booking; kubectl get pv; helm list -n coworking-booking
NAME                         DATA   AGE
configmap/kube-root-ca.crt   1      7m10s
No resources found
NAME	NAMESPACE	REVISION	UPDATED	STATUS	CHART	APP VERSION
```

> `helm test --logs` разом із `hook-succeeded` дає `pods "booking-test-health" not found`: Helm 3 видаляє успішний тест-под раніше, ніж забирає його лог. Сам тест пройшов (`Phase: Succeeded`), а вміст відповіді видно в 9.1. Обрано чистий `uninstall`: успішний тест-под прибирається, упалий лишається для діагностики. `--logs` з NOTES прибрано. `configmap/kube-root-ca.crt` Kubernetes автоматично створює в кожному namespace, до релізу він не належить.
