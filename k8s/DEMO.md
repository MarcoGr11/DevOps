# Лабораторна №3: розгортання в Kubernetes — журнал виконання

Текстовий вивід реальних команд, виконаних 2026-10-14. Скріншоти замінено
збереженим виводом.

**Середовище:** macOS (arm64), Docker 29.6.1, minikube v1.39.0 (`--driver=docker`),
Kubernetes v1.37.0, kubectl v1.37.1. Доповнення: `metrics-server`, `ingress`.

**Образи** (зібрані й запушені вручну, `docker build` → `docker tag` → `docker push`):

| Образ | Digest |
|---|---|
| `ghcr.io/marcogr11/devops-api:1.0.0` | `sha256:2f795998422b…` |
| `ghcr.io/marcogr11/devops-api:1.1.0` | `sha256:a4401c991f4a…` |
| `ghcr.io/marcogr11/devops-worker:1.0.0` | `sha256:51ce56d9d2ce…` |
| `ghcr.io/marcogr11/devops-worker:1.1.0` | `sha256:d88cdc1ff154…` |

Між 1.0.0 і 1.1.0 відрізняється поле `version` у відповіді `/api/health/`,
а у worker — стартовий рядок логу. Поле `pod` (hostname) показує, який под
обробив запит.

**Доступ з хоста під час демонстрації:** `kubectl port-forward` на Service
`api` (порт 8080) і на `ingress-nginx-controller` (порт 8081, заголовок
`Host: booking.local`). Цикли curl у 6.2–6.5 ідуть через Ingress, бо
port-forward на Service прив'язується до одного конкретного пода.

## Примітки до виводу

- **5.3.** RESTARTS 3–4 у api і worker одразу після `apply` — не помилка
  маніфестів. Postgres ще не приймав з'єднань (`Connection refused` у
  `kubectl logs --previous`), і kubelet перезапускав контейнери, доки БД не
  піднялась. З тієї ж причини один worker на старті один раз залогував
  `relation "booking_booking" does not exist`: він стартував раніше, ніж api
  виконав міграції. Worker обробив виняток і далі працює без помилок (див.
  7.3).
- **5.3.** `kubectl top` показує не всі поди: metrics-server ще не встиг
  зібрати метрики для щойно запущених.
- **6.2.** Перший вимір розподілу дав лише 2 поди з 4. Нові поди стали Ready
  за 7 с до запиту, і ingress-nginx ще не оновив свій список ендпоінтів.
  Повторний вимір через 15 с показує рівномірний розподіл між усіма 4.
- **6.4–7.5.** `CHANGE-CAUSE` проставлено вручну через `kubectl annotate`.
  Після відкату ревізія 1 перенумерувалась у 3: Kubernetes переносить
  шаблон, на який відкочуються, у нову ревізію. Ревізія 4 (тег 9.9.9)
  успадкувала стару анотацію «initial deploy: image 1.0.0». `kubectl apply`
  не прибирає анотації, яких немає в YAML, тож підпис для 4 некоректний: це
  артефакт ручних анотацій, а не стан образу. Фактичний образ видно у 7.1/7.5.
- **7.1.** Через `maxUnavailable: 0` під час зламаного оновлення старі поди
  1.0.0 продовжували обслуговувати запити. Недоступності не було, «застряг»
  лише rollout.
- **7.4.** `kubectl exec -it ... -- sh` потребує TTY. В автоматизованому
  журналі сесію записано як `kubectl exec -i ... -- sh` з командами через
  stdin. Інтерактивно це робиться так:
  `kubectl exec -it deploy/api -n coworking-booking -- sh`.

## Журнал

### 5.1 Namespace і Secret

```
$ kubectl apply -f k8s/namespace.yaml
namespace/coworking-booking created
```

```
$ kubectl create secret generic booking-secret -n coworking-booking --from-literal=POSTGRES_PASSWORD="$(openssl rand -hex 16)" --from-literal=DJANGO_SECRET_KEY="$(openssl rand -hex 32)"
secret/booking-secret created
```

### 5.2 Застосування всіх маніфестів

```
$ kubectl apply -f k8s/ -n coworking-booking
deployment.apps/api created
ingress.networking.k8s.io/api created
service/api created
configmap/booking-config created
namespace/coworking-booking unchanged
deployment.apps/postgres created
persistentvolumeclaim/postgres-data created
service/postgres created
deployment.apps/worker created
```

### 5.3 Стан об'єктів

```
$ kubectl get pods -n coworking-booking -o wide
NAME                        READY   STATUS    RESTARTS      AGE    IP            NODE       NOMINATED NODE   READINESS GATES
api-6469f9dd88-ktbw8        1/1     Running   3 (71s ago)   2m4s   10.244.0.9    minikube   <none>           <none>
api-6469f9dd88-z582b        1/1     Running   3 (71s ago)   2m4s   10.244.0.10   minikube   <none>           <none>
postgres-747ccbb877-g5xs5   1/1     Running   0             2m4s   10.244.0.11   minikube   <none>           <none>
worker-6cf4b4d54d-7wcfs     1/1     Running   4 (60s ago)   2m4s   10.244.0.7    minikube   <none>           <none>
worker-6cf4b4d54d-jmdvd     1/1     Running   3 (80s ago)   2m4s   10.244.0.8    minikube   <none>           <none>
```

```
$ kubectl get deployments -n coworking-booking
NAME       READY   UP-TO-DATE   AVAILABLE   AGE
api        2/2     2            2           2m4s
postgres   1/1     1            1           2m4s
worker     2/2     2            2           2m4s
```

```
$ kubectl get replicasets -n coworking-booking
NAME                  DESIRED   CURRENT   READY   AGE
api-6469f9dd88        2         2         2       2m4s
postgres-747ccbb877   1         1         1       2m4s
worker-6cf4b4d54d     2         2         2       2m4s
```

```
$ kubectl get services,ingress,pvc,configmap,secret -n coworking-booking
NAME               TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)    AGE
service/api        ClusterIP   10.101.22.241    <none>        80/TCP     2m5s
service/postgres   ClusterIP   10.102.169.167   <none>        5432/TCP   2m5s

NAME                            CLASS   HOSTS           ADDRESS        PORTS   AGE
ingress.networking.k8s.io/api   nginx   booking.local   192.168.49.2   80      2m5s

NAME                                  STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
persistentvolumeclaim/postgres-data   Bound    pvc-1decfa59-17e9-4f18-8380-d4ace179050c   1Gi        RWO            standard       <unset>                 2m5s

NAME                         DATA   AGE
configmap/booking-config     8      2m5s
configmap/kube-root-ca.crt   1      2m5s

NAME                    TYPE     DATA   AGE
secret/booking-secret   Opaque   2      2m5s
```

```
$ kubectl top pods -n coworking-booking
NAME                        CPU(cores)   MEMORY(bytes)   
postgres-747ccbb877-g5xs5   51m          23Mi            
worker-6cf4b4d54d-jmdvd     18m          14Mi            
```

### 5.4 Доступ з хоста

```
$ kubectl port-forward -n coworking-booking svc/api 8080:80 &   # у фоні
Forwarding from 127.0.0.1:8080 -> 8000
Forwarding from [::1]:8080 -> 8000
```

```
$ curl -s http://localhost:8080/api/health/
{"status":"ok","version":"1.0.0","pod":"api-6469f9dd88-z582b"}
```

```
$ kubectl port-forward -n ingress-nginx svc/ingress-nginx-controller 8081:80 &   # у фоні, вхід через Ingress
Forwarding from 127.0.0.1:8081 -> 80
Forwarding from [::1]:8081 -> 80
```

```
$ curl -s -H "Host: booking.local" http://localhost:8081/api/health/
{"status":"ok","version":"1.0.0","pod":"api-6469f9dd88-z582b"}
```

```
$ curl -s -o /dev/null -w "%{http_code}\n" -H "Host: booking.local" http://localhost:8081/api/resources/
200
```

### 5.5 Змінні ConfigMap і Secret всередині контейнера api

```
$ kubectl exec -n coworking-booking deploy/api -- sh -c "$(cat envcheck.sh)"
APP_VERSION=1.0.0
BOOKING_TIMEOUT_CHECK_INTERVAL=30
BOOKING_TIMEOUT_MINUTES=15
DJANGO_ALLOWED_HOSTS=*
DJANGO_DEBUG=0
POSTGRES_DB=booking
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_USER=booking
POSTGRES_PASSWORD: 32 chars, sha256=b8716a56c9a6
DJANGO_SECRET_KEY: 64 chars, sha256=ee4073d6d33f
```

```
$ for k in POSTGRES_PASSWORD DJANGO_SECRET_KEY; do echo "$k in Secret: sha256=$(kubectl get secret booking-secret -n coworking-booking -o jsonpath="{.data.$k}" | base64 -d | shasum -a 256 | cut -c1-12)"; done
POSTGRES_PASSWORD in Secret: sha256=b8716a56c9a6
DJANGO_SECRET_KEY in Secret: sha256=ee4073d6d33f
```

### 6.1 Самовідновлення

```
$ kubectl get pods -n coworking-booking -l app=api
NAME                   READY   STATUS    RESTARTS        AGE
api-6469f9dd88-ktbw8   1/1     Running   3 (2m32s ago)   3m25s
api-6469f9dd88-z582b   1/1     Running   3 (2m32s ago)   3m25s
```

```
$ kubectl delete pod -n coworking-booking api-6469f9dd88-ktbw8
pod "api-6469f9dd88-ktbw8" deleted from coworking-booking namespace
```

```
$ kubectl get pods -n coworking-booking -l app=api
NAME                   READY   STATUS    RESTARTS       AGE
api-6469f9dd88-4zpnj   1/1     Running   0              32s
api-6469f9dd88-z582b   1/1     Running   3 (3m4s ago)   3m57s
```

```
$ kubectl wait --for=condition=Ready pod -l app=api -n coworking-booking --timeout=120s && kubectl get pods -n coworking-booking -l app=api
pod/api-6469f9dd88-4zpnj condition met
pod/api-6469f9dd88-z582b condition met
NAME                   READY   STATUS    RESTARTS       AGE
api-6469f9dd88-4zpnj   1/1     Running   0              32s
api-6469f9dd88-z582b   1/1     Running   3 (3m4s ago)   3m57s
```

```
$ kubectl get events -n coworking-booking --field-selector involvedObject.kind=ReplicaSet --sort-by=.lastTimestamp | tail -2
3m57s       Normal   SuccessfulCreate   replicaset/worker-6cf4b4d54d     Created pod: worker-6cf4b4d54d-jmdvd
32s         Normal   SuccessfulCreate   replicaset/api-6469f9dd88        Created pod: api-6469f9dd88-4zpnj
```

### 6.2 Масштабування

```
$ kubectl scale deployment api -n coworking-booking --replicas=4
deployment.apps/api scaled
```

```
$ kubectl rollout status deployment/api -n coworking-booking --timeout=180s
Waiting for deployment "api" rollout to finish: 2 of 4 updated replicas are available...
Waiting for deployment "api" rollout to finish: 3 of 4 updated replicas are available...
deployment "api" successfully rolled out
```

```
$ kubectl get pods -n coworking-booking -l app=api -o wide
NAME                   READY   STATUS    RESTARTS        AGE     IP            NODE       NOMINATED NODE   READINESS GATES
api-6469f9dd88-4zpnj   1/1     Running   0               45s     10.244.0.12   minikube   <none>           <none>
api-6469f9dd88-9ckjg   1/1     Running   0               7s      10.244.0.14   minikube   <none>           <none>
api-6469f9dd88-f2h2f   1/1     Running   0               7s      10.244.0.13   minikube   <none>           <none>
api-6469f9dd88-z582b   1/1     Running   3 (3m17s ago)   4m10s   10.244.0.10   minikube   <none>           <none>
```

```
$ for i in $(seq 1 20); do curl -s -H "Host: booking.local" http://localhost:8081/api/health/ | python3 -c "import sys,json;print(json.load(sys.stdin)[\"pod\"])"; done | sort | uniq -c
  10 api-6469f9dd88-4zpnj
  10 api-6469f9dd88-z582b
```

```
$ kubectl get endpointslices -n coworking-booking -l kubernetes.io/service-name=api
NAME        ADDRESSTYPE   PORTS   ENDPOINTS                                         AGE
api-dchbn   IPv4          8000    10.244.0.10,10.244.0.12,10.244.0.13 + 1 more...   4m32s
```

```
$ for i in $(seq 1 40); do curl -s -H "Host: booking.local" http://localhost:8081/api/health/ | python3 -c "import sys,json;print(json.load(sys.stdin)[\"pod\"])"; done | sort | uniq -c
  10 api-6469f9dd88-4zpnj
  12 api-6469f9dd88-9ckjg
   9 api-6469f9dd88-f2h2f
   9 api-6469f9dd88-z582b
```

### 6.3 Rolling update 1.0.0 → 1.1.0 (паралельно працює curl-цикл через Ingress, кожні 0.1 с)

```
$ kubectl set image deployment/api api=ghcr.io/marcogr11/devops-api:1.1.0 -n coworking-booking && kubectl annotate deployment/api -n coworking-booking kubernetes.io/change-cause="update image to 1.1.0" --overwrite
deployment.apps/api image updated
deployment.apps/api annotated
```

```
$ kubectl rollout status deployment/api -n coworking-booking --timeout=300s
Waiting for deployment "api" rollout to finish: 1 out of 4 new replicas have been updated...
Waiting for deployment "api" rollout to finish: 1 out of 4 new replicas have been updated...
Waiting for deployment "api" rollout to finish: 1 out of 4 new replicas have been updated...
Waiting for deployment "api" rollout to finish: 2 out of 4 new replicas have been updated...
Waiting for deployment "api" rollout to finish: 2 out of 4 new replicas have been updated...
Waiting for deployment "api" rollout to finish: 2 out of 4 new replicas have been updated...
Waiting for deployment "api" rollout to finish: 3 out of 4 new replicas have been updated...
Waiting for deployment "api" rollout to finish: 3 out of 4 new replicas have been updated...
Waiting for deployment "api" rollout to finish: 3 out of 4 new replicas have been updated...
Waiting for deployment "api" rollout to finish: 1 old replicas are pending termination...
Waiting for deployment "api" rollout to finish: 1 old replicas are pending termination...
deployment "api" successfully rolled out
```

```
$ uniq -c loop-update.log   # результати curl-циклу по порядку: кількість, HTTP-код, версія
 146 200 1.0.0
   2 200 1.1.0
   2 200 1.0.0
   2 200 1.1.0
   7 200 1.0.0
   2 200 1.1.0
  16 200 1.0.0
   1 200 1.1.0
   3 200 1.0.0
   2 200 1.1.0
   5 200 1.0.0
   1 200 1.1.0
   1 200 1.0.0
   1 200 1.1.0
   4 200 1.0.0
   1 200 1.1.0
   2 200 1.0.0
   4 200 1.1.0
   3 200 1.0.0
   1 200 1.1.0
   1 200 1.0.0
   2 200 1.1.0
   1 200 1.0.0
   1 200 1.1.0
   1 200 1.0.0
   4 200 1.1.0
   1 200 1.0.0
   1 200 1.1.0
   1 200 1.0.0
   2 200 1.1.0
   1 200 1.0.0
   1 200 1.1.0
   3 200 1.0.0
   1 200 1.1.0
   1 200 1.0.0
   1 200 1.1.0
   1 200 1.0.0
   1 200 1.1.0
   2 200 1.0.0
   2 200 1.1.0
   3 200 1.0.0
   1 200 1.1.0
   1 200 1.0.0
   1 200 1.1.0
   1 200 1.0.0
   2 200 1.1.0
   1 200 1.0.0
   2 200 1.1.0
   1 200 1.0.0
   5 200 1.1.0
   2 200 1.0.0
   3 200 1.1.0
   1 200 1.0.0
   2 200 1.1.0
   1 200 1.0.0
   2 200 1.1.0
   1 200 1.0.0
   9 200 1.1.0
   1 200 1.0.0
   1 200 1.1.0
   1 200 1.0.0
   1 200 1.1.0
   2 200 1.0.0
   2 200 1.1.0
   2 200 1.0.0
  25 200 1.1.0
```

```
$ kubectl get pods -n coworking-booking -l app=api; kubectl get rs -n coworking-booking -l app=api
NAME                   READY   STATUS        RESTARTS        AGE
api-6469f9dd88-4zpnj   1/1     Terminating   0               2m6s
api-6469f9dd88-9ckjg   1/1     Terminating   0               88s
api-6469f9dd88-f2h2f   1/1     Terminating   0               88s
api-6469f9dd88-z582b   1/1     Terminating   3 (4m38s ago)   5m31s
api-84b8bccfdf-5hzqk   1/1     Running       0               40s
api-84b8bccfdf-gc88l   1/1     Running       0               23s
api-84b8bccfdf-pl267   1/1     Running       0               17s
api-84b8bccfdf-x9zqc   1/1     Running       0               11s
NAME             DESIRED   CURRENT   READY   AGE
api-6469f9dd88   0         0         0       5m31s
api-84b8bccfdf   4         4         4       40s
```

```
$ echo "всього запитів: $(wc -l < loop-update.log)"; echo "за HTTP-кодом:"; cut -d" " -f1 loop-update.log | sort | uniq -c; echo "за версією:"; cut -d" " -f2 loop-update.log | sort | uniq -c
всього запитів:      309
за HTTP-кодом:
 309 200
за версією:
 220 1.0.0
  89 1.1.0
```

```
$ curl -s -H "Host: booking.local" http://localhost:8081/api/health/
{"status":"ok","version":"1.1.0","pod":"api-84b8bccfdf-pl267"}
```

### 6.4 Історія

```
$ kubectl rollout history deployment/api -n coworking-booking
deployment.apps/api 
REVISION  CHANGE-CAUSE
1         initial deploy: image 1.0.0
2         update image to 1.1.0
```

### 6.5 Відкат

```
$ kubectl rollout undo deployment/api -n coworking-booking
Warning: resource deployments/api was previously managed with 'kubectl apply'. Rolling back will not update the kubectl.kubernetes.io/last-applied-configuration annotation, which may cause unexpected behavior on future 'kubectl apply' operations. Consider using 'kubectl apply' with your previous configuration file instead.
deployment.apps/api rolled back
```

```
$ kubectl rollout status deployment/api -n coworking-booking --timeout=300s
Waiting for deployment "api" rollout to finish: 1 out of 4 new replicas have been updated...
Waiting for deployment "api" rollout to finish: 1 out of 4 new replicas have been updated...
Waiting for deployment "api" rollout to finish: 1 out of 4 new replicas have been updated...
Waiting for deployment "api" rollout to finish: 1 out of 4 new replicas have been updated...
Waiting for deployment "api" rollout to finish: 2 out of 4 new replicas have been updated...
Waiting for deployment "api" rollout to finish: 2 out of 4 new replicas have been updated...
Waiting for deployment "api" rollout to finish: 2 out of 4 new replicas have been updated...
Waiting for deployment "api" rollout to finish: 2 out of 4 new replicas have been updated...
Waiting for deployment "api" rollout to finish: 3 out of 4 new replicas have been updated...
Waiting for deployment "api" rollout to finish: 3 out of 4 new replicas have been updated...
Waiting for deployment "api" rollout to finish: 3 out of 4 new replicas have been updated...
Waiting for deployment "api" rollout to finish: 1 old replicas are pending termination...
Waiting for deployment "api" rollout to finish: 1 old replicas are pending termination...
deployment "api" successfully rolled out
```

```
$ echo "запитів під час відкату: $(wc -l < loop-undo.log)"; cut -d" " -f1 loop-undo.log | sort | uniq -c; echo "останні 3 відповіді:"; tail -3 loop-undo.log
запитів під час відкату:      219
 219 200
останні 3 відповіді:
200 1.0.0
200 1.0.0
200 1.0.0
```

```
$ kubectl get deployment api -n coworking-booking -o jsonpath="{.spec.template.spec.containers[0].image}{\"\n\"}"; curl -s -H "Host: booking.local" http://localhost:8081/api/health/
ghcr.io/marcogr11/devops-api:1.0.0
{"status":"ok","version":"1.0.0","pod":"api-6469f9dd88-gwglj"}
```

```
$ kubectl rollout history deployment/api -n coworking-booking
deployment.apps/api 
REVISION  CHANGE-CAUSE
2         update image to 1.1.0
3         initial deploy: image 1.0.0
```

```
$ kubectl get rs -n coworking-booking -l app=api
NAME             DESIRED   CURRENT   READY   AGE
api-6469f9dd88   4         4         4       6m18s
api-84b8bccfdf   0         0         0       87s
```

### 7.1 Неіснуючий тег образу

```
$ grep -n image: k8s/api-deployment.yaml
24:          image: ghcr.io/marcogr11/devops-api:9.9.9
```

```
$ kubectl apply -f k8s/api-deployment.yaml -n coworking-booking
deployment.apps/api configured
```

```
$ kubectl get pods -n coworking-booking -l app=api
NAME                   READY   STATUS             RESTARTS   AGE
api-6469f9dd88-5sq47   1/1     Running            0          87s
api-6469f9dd88-qc2ct   1/1     Running            0          99s
api-64d5fbbf6d-6bxx5   0/1     ImagePullBackOff   0          45s
```

```
$ kubectl rollout status deployment/api -n coworking-booking --timeout=5s
Waiting for deployment "api" rollout to finish: 1 out of 2 new replicas have been updated...
error: timed out waiting for the condition
```

### 7.2 Пошук причини

```
$ kubectl describe pod api-64d5fbbf6d-6bxx5 -n coworking-booking | sed -n '/^Containers:/,/^    Ready:/p;/^Events:/,$p'
Containers:
  api:
    Container ID:   
    Image:          ghcr.io/marcogr11/devops-api:9.9.9
    Image ID:       
    Port:           8000/TCP
    Host Port:      0/TCP
    State:          Waiting
      Reason:       ErrImagePull
    Ready:          False
Events:
  Type     Reason     Age                From               Message
  ----     ------     ----               ----               -------
  Normal   Scheduled  57s                default-scheduler  Successfully assigned coworking-booking/api-64d5fbbf6d-6bxx5 to minikube
  Normal   Pulling    16s (x3 over 57s)  kubelet            spec.containers{api}: Pulling image "ghcr.io/marcogr11/devops-api:9.9.9"
  Warning  Failed     15s (x3 over 56s)  kubelet            spec.containers{api}: Failed to pull image "ghcr.io/marcogr11/devops-api:9.9.9": rpc error: code = NotFound desc = failed to pull and unpack image "ghcr.io/marcogr11/devops-api:9.9.9": failed to resolve reference "ghcr.io/marcogr11/devops-api:9.9.9": ghcr.io/marcogr11/devops-api:9.9.9: not found
  Warning  Failed     15s (x3 over 56s)  kubelet            spec.containers{api}: Error: ErrImagePull
  Normal   BackOff    5s (x3 over 56s)   kubelet            spec.containers{api}: Back-off pulling image "ghcr.io/marcogr11/devops-api:9.9.9"
  Warning  Failed     5s (x3 over 56s)   kubelet            spec.containers{api}: Error: ImagePullBackOff
```

```
$ kubectl get events -n coworking-booking --field-selector involvedObject.name=api-64d5fbbf6d-6bxx5 --sort-by=.lastTimestamp
LAST SEEN   TYPE      REASON      OBJECT                     MESSAGE
57s         Normal    Scheduled   pod/api-64d5fbbf6d-6bxx5   Successfully assigned coworking-booking/api-64d5fbbf6d-6bxx5 to minikube
16s         Normal    Pulling     pod/api-64d5fbbf6d-6bxx5   Pulling image "ghcr.io/marcogr11/devops-api:9.9.9"
15s         Warning   Failed      pod/api-64d5fbbf6d-6bxx5   Failed to pull image "ghcr.io/marcogr11/devops-api:9.9.9": rpc error: code = NotFound desc = failed to pull and unpack image "ghcr.io/marcogr11/devops-api:9.9.9": failed to resolve reference "ghcr.io/marcogr11/devops-api:9.9.9": ghcr.io/marcogr11/devops-api:9.9.9: not found
15s         Warning   Failed      pod/api-64d5fbbf6d-6bxx5   Error: ErrImagePull
5s          Normal    BackOff     pod/api-64d5fbbf6d-6bxx5   Back-off pulling image "ghcr.io/marcogr11/devops-api:9.9.9"
5s          Warning   Failed      pod/api-64d5fbbf6d-6bxx5   Error: ImagePullBackOff
```

```
$ curl -s -H "Host: booking.local" http://localhost:8081/api/health/   # сервіс доступний на старих подах
{"status":"ok","version":"1.0.0","pod":"api-6469f9dd88-qc2ct"}
```

### 7.3 Логи

```
$ kubectl logs api-64d5fbbf6d-6bxx5 -n coworking-booking
Error from server (BadRequest): container "api" in pod "api-64d5fbbf6d-6bxx5" is waiting to start: image can't be pulled
```

```
$ kubectl logs api-6469f9dd88-5sq47 -n coworking-booking --tail=8
Operations to perform:
  Apply all migrations: admin, auth, booking, contenttypes, sessions
Running migrations:
  No migrations to apply.
[2026-10-13 22:00:37 +0000] [8] [INFO] Starting gunicorn 22.0.0
[2026-10-13 22:00:37 +0000] [8] [INFO] Listening at: http://0.0.0.0:8000 (8)
[2026-10-13 22:00:37 +0000] [8] [INFO] Using worker: sync
[2026-10-13 22:00:37 +0000] [9] [INFO] Booting worker with pid: 9
```

```
$ kubectl logs deploy/worker -n coworking-booking --tail=3
Found 2 pods, using pod/worker-6cf4b4d54d-jmdvd
LINE 2:             UPDATE booking_booking
                           ^
```

### 7.4 Інтерактивний вхід у контейнер

```
$ kubectl exec -i api-6469f9dd88-5sq47 -n coworking-booking -- sh <<'SH'
echo "whoami: $(whoami)  host: $(hostname)  version: $APP_VERSION"
ls /app
python -c 'import urllib.request;print(urllib.request.urlopen("http://localhost:8000/api/health/").read().decode())'
python manage.py showmigrations booking
SH
whoami: root  host: api-6469f9dd88-5sq47  version: 1.0.0
Dockerfile
booking
config
manage.py
requirements.txt
staticfiles
{"status":"ok","version":"1.0.0","pod":"api-6469f9dd88-5sq47"}
booking
 [X] 0001_initial
 [X] 0002_alter_resource_options
```

### 7.5 Виправлення

```
$ grep -n image: k8s/api-deployment.yaml
24:          image: ghcr.io/marcogr11/devops-api:1.0.0
```

```
$ kubectl apply -f k8s/api-deployment.yaml -n coworking-booking
deployment.apps/api configured
```

```
$ kubectl rollout status deployment/api -n coworking-booking --timeout=180s
deployment "api" successfully rolled out
```

```
$ kubectl get pods,deployments,rs -n coworking-booking
NAME                            READY   STATUS    RESTARTS        AGE
pod/api-6469f9dd88-5sq47        1/1     Running   0               2m9s
pod/api-6469f9dd88-qc2ct        1/1     Running   0               2m21s
pod/postgres-747ccbb877-g5xs5   1/1     Running   0               8m10s
pod/worker-6cf4b4d54d-7wcfs     1/1     Running   4 (7m6s ago)    8m10s
pod/worker-6cf4b4d54d-jmdvd     1/1     Running   3 (7m26s ago)   8m10s

NAME                       READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/api        2/2     2            2           8m10s
deployment.apps/postgres   1/1     1            1           8m10s
deployment.apps/worker     2/2     2            2           8m10s

NAME                                  DESIRED   CURRENT   READY   AGE
replicaset.apps/api-6469f9dd88        2         2         2       8m10s
replicaset.apps/api-64d5fbbf6d        0         0         0       87s
replicaset.apps/api-84b8bccfdf        0         0         0       3m19s
replicaset.apps/postgres-747ccbb877   1         1         1       8m10s
replicaset.apps/worker-6cf4b4d54d     2         2         2       8m10s
```

```
$ kubectl rollout history deployment/api -n coworking-booking
deployment.apps/api 
REVISION  CHANGE-CAUSE
2         update image to 1.1.0
4         initial deploy: image 1.0.0
5         initial deploy: image 1.0.0
```

```
$ curl -s -H "Host: booking.local" http://localhost:8081/api/health/
{"status":"ok","version":"1.0.0","pod":"api-6469f9dd88-5sq47"}
```
