# Лабораторна №3 — чекліст скриншотів

14 скриншотів, лише пункти 5–7 методички. Кожен PNG кладеться в
`reports/screens/лаб3/` під іменем із заголовка `###`. Один блок команд = один
скриншот (якщо команди не влазять в одне вікно, кілька знімків одного
блоку склеюються вертикально в один PNG). `reports/build_report.py` бере
звідси «Що робимо», «Підпис» і «Що видно» для PDF.

Вікно терміналу — не ширше ~1800 px (приблизно 130 символів), інакше текст
у PDF стане дрібним. Довгі рядки нехай переносяться.

**Підготовка (не знімається):**

```bash
open -a Docker; minikube start
minikube addons enable ingress; minikube addons enable metrics-server
kubectl get namespace coworking-booking      # має бути NotFound, інакше див. «Перехід до лаби №4»
kubectl apply -f k8s/namespace.yaml
```

Паролі не мають потрапити в кадр: ніяких `env` без фільтра,
`kubectl get secret -o yaml`, `echo $POSTGRES_PASSWORD`.

---

## 5. Розгортання

### 3-05a-apply.png — 5.a Secret і apply

**Що робимо:** Створюємо Secret з випадковими паролями і застосовуємо всі маніфести з `k8s/`.

**Команди:**
```bash
kubectl create secret generic booking-secret -n coworking-booking \
  --from-literal=POSTGRES_PASSWORD="$(openssl rand -hex 16)" \
  --from-literal=DJANGO_SECRET_KEY="$(openssl rand -hex 32)"
kubectl apply -f k8s/ -n coworking-booking
kubectl annotate deployment/api -n coworking-booking kubernetes.io/change-cause="initial deploy: image 1.0.0"
```

**Має бути видно:** `secret/booking-secret created`; `created` для api, worker, postgres, сервісів, Ingress, ConfigMap, PVC; `namespace/coworking-booking unchanged`.

**Не має бути:** `already exists` (Secret створюється рівно один раз у свіжому namespace), значень паролів.

**Підпис:** Створення Secret і застосування маніфестів

**Що видно:** `secret/booking-secret created`, далі `created` для Deployment-ів api, worker і postgres, обох Service-ів, Ingress, ConfigMap і PVC `postgres-data`. Namespace перед цим створено командою `kubectl create namespace`, тому `apply` вивів `Warning` про відсутню анотацію `last-applied-configuration`, сам її додав (`namespace/coworking-booking configured`). Значення паролів у терміналі не з'являються.

### 3-05b-objects.png — 5.b Об'єкти в namespace

**Що робимо:** Перевіряємо, що всі поди запустились і об'єкти створені.

**Команди:**
```bash
kubectl rollout status deployment/api -n coworking-booking --timeout=180s
kubectl get pods -n coworking-booking -o wide
kubectl get deployments,replicasets,services,ingress,pvc,configmap,secret -n coworking-booking
```

**Має бути видно:** 5 подів `Running` `1/1` (2 api, 2 worker, 1 postgres); Deployment-и `2/2`, `1/1`, `2/2`; Service-и, Ingress `booking.local`, PVC `Bound`.

**Не має бути:** подів у `CrashLoopBackOff`/`Pending`.

**Підпис:** Поди, Deployment-и, ReplicaSet-и, Service-и, Ingress, PVC після розгортання

**Що видно:** Усі 5 подів у стані `Running` і `1/1`: `api-6469f9dd88-m5rp5`, `api-6469f9dd88-zjf7h`, два worker і `postgres-747ccbb877-tvrpd`. Deployment-и `api 2/2`, `worker 2/2`, `postgres 1/1`, PVC `postgres-data` у стані `Bound` (1Gi), Ingress на `booking.local`. `RESTARTS 2` у api та worker — це перезапуски на старті, поки postgres ще не приймав з'єднань.

### 3-05c-browser.png — 5.c /api/health/ у браузері

**Що робимо:** Відкриваємо health-ендпоінт застосунку в браузері.

**Команди:**
```bash
# окремий термінал, лишити працювати:
kubectl port-forward -n coworking-booking svc/api 8080:80
# браузер: http://localhost:8080/api/health/
```

**Має бути видно:** вікно БРАУЗЕРА з адресним рядком `localhost:8080/api/health/` і JSON `{"status":"ok","version":"1.0.0","pod":"api-..."}`.

**Не має бути:** терміналу замість браузера, сторінки помилки.

**Підпис:** Відповідь /api/health/ у браузері

**Що видно:** В адресному рядку `localhost:8080/api/health/` (port-forward на Service api). Django REST framework повертає `HTTP 200 OK` з JSON `"status": "ok"`, `"version": "1.0.0"`, а поле `pod` показує под, який обробив запит: `api-6469f9dd88-4j6zr`.

### 3-05d-config-secret.png — 5.d ConfigMap і Secret у контейнері

**Що робимо:** Перевіряємо, що змінні з ConfigMap і Secret потрапили в контейнер api, не показуючи паролів.

**Команди:**
```bash
kubectl exec -n coworking-booking deploy/api -- env | grep -E "POSTGRES_(USER|DB|HOST)|DJANGO_DEBUG|BOOKING_" | sort
for k in POSTGRES_PASSWORD DJANGO_SECRET_KEY; do
  echo "$k  Secret: $(kubectl get secret booking-secret -n coworking-booking -o jsonpath="{.data.$k}" | base64 -d | shasum -a 256 | cut -c1-12)  pod: $(kubectl exec -n coworking-booking deploy/api -- printenv $k | tr -d '\n' | shasum -a 256 | cut -c1-12)"
done
```

**Має бути видно:** `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_USER`, `DJANGO_DEBUG`, `BOOKING_TIMEOUT_*` зі значеннями з ConfigMap; для кожного ключа Secret два однакові 12-символьні хеші.

**Не має бути:** самих значень `POSTGRES_PASSWORD` і `DJANGO_SECRET_KEY`.

**Підпис:** Змінні ConfigMap і хеші значень Secret у контейнері api

**Що видно:** У контейнері api є всі значення з ConfigMap: `POSTGRES_DB=booking`, `POSTGRES_HOST=postgres`, `POSTGRES_USER=booking`, `DJANGO_DEBUG=0`, `BOOKING_TIMEOUT_CHECK_INTERVAL=30`, `BOOKING_TIMEOUT_MINUTES=15`. Для кожного ключа Secret хеш значення в Secret і в поді однаковий (`be3d4efaec0d` для пароля БД, `1347ce6b64f2` для ключа Django): паролі потрапили в контейнер, хоча самих значень на екрані немає.

## 6. Життєвий цикл

Для 6.b–6.e потрібен port-forward на Ingress (окремий термінал, лишити працювати):
`kubectl port-forward -n ingress-nginx svc/ingress-nginx-controller 8081:80`.
Port-forward на Service прив'язується до одного пода і обірветься під час rolling update.

### 3-06a-selfheal.png — 6.a Самовідновлення

**Що робимо:** Видаляємо под api вручну і дивимось, як Kubernetes створює заміну.

**Команди:**
```bash
kubectl get pods -n coworking-booking -l app=api
kubectl delete pod -n coworking-booking $(kubectl get pods -n coworking-booking -l app=api -o jsonpath='{.items[0].metadata.name}')
kubectl get pods -n coworking-booking -l app=api
```

**Має бути видно:** до: 2 поди; видалено один; після: знову 2, один з них новий (AGE у секундах, RESTARTS 0).

**Не має бути:** помилок `NotFound`.

**Підпис:** Видалення пода api і його автоматична заміна

**Що видно:** Видалено под `api-6469f9dd88-m5rp5`. Після цього знову працюють 2 поди: старий `api-6469f9dd88-zjf7h` (AGE 5m57s) і новий `api-6469f9dd88-vq8km` (AGE 53s, RESTARTS 0), якого ReplicaSet створив замість видаленого.

### 3-06b-scale.png — 6.b Масштабування до 4

**Що робимо:** Збільшуємо кількість реплік api до 4 і перевіряємо, що запити розходяться між усіма подами.

**Команди:**
```bash
kubectl scale deployment api -n coworking-booking --replicas=4
kubectl rollout status deployment/api -n coworking-booking
kubectl get pods -n coworking-booking -l app=api -o wide
for i in $(seq 1 40); do curl -s -H "Host: booking.local" http://localhost:8081/api/health/ | grep -o '"pod":"[^"]*"'; done | sort | uniq -c
```

**Має бути видно:** 4 поди `Running` з різними IP; у циклі — 4 різні імена подів.

**Не має бути:** `Pending` чи лише 1–2 імен у циклі (тоді почекати 15 с і повторити цикл).

**Підпис:** Масштабування api до 4 реплік і розподіл запитів

**Що видно:** Працюють 4 поди api (`c4wrz`, `l5bzc`, `vq8km`, `zjf7h`) з різними IP 10.244.0.6–0.12. 40 запитів через Ingress розподілились між усіма чотирма приблизно порівну: 10, 9, 10 і 11.

### 3-06c-rollout.png — 6.c Rolling update на 1.1.0

**Що робимо:** Оновлюємо образ api з 1.0.0 на 1.1.0. Перед цим у другому вікні запускаємо цикл curl (6.d).

**Команди:**
```bash
kubectl set image deployment/api api=ghcr.io/marcogr11/devops-api:1.1.0 -n coworking-booking
kubectl annotate deployment/api -n coworking-booking kubernetes.io/change-cause="update image to 1.1.0" --overwrite
kubectl rollout status deployment/api -n coworking-booking
kubectl get pods,rs -n coworking-booking -l app=api
```

**Має бути видно:** `image updated`; у `rollout status` рядки `Waiting ... N out of 4 new replicas have been updated` (запускати одразу після set image); старі поди `Terminating`, нові `Running`; новий ReplicaSet 4, старий 0.

**Не має бути:** `ImagePullBackOff`.

**Підпис:** Rolling update api з 1.0.0 на 1.1.0

**Що видно:** Після `set image` старий ReplicaSet `api-6469f9dd88` зменшився до 0, а новий `api-84b8bccfdf` виріс до 4 (усі `Ready`). Останній старий под `api-6469f9dd88-zjf7h` ще у стані `Terminating`, а чотири нові `api-84b8bccfdf-*` уже `Running` з AGE 32–50 с: їх запускали по одному.

### 3-06d-availability.png — 6.d Доступність під час оновлення

**Що робимо:** Перевіряємо, що під час оновлення сервіс відповідав без помилок.

**Команди:**
```bash
# друге вікно, запустити ДО 6.c, зупинити Ctrl+C після rollout status:
while true; do curl -s -m 2 -w " %{http_code}\n" -H "Host: booking.local" http://localhost:8081/api/health/; sleep 0.1; done | tee /tmp/loop-update.log
# підсумок:
echo "всього запитів: $(wc -l < /tmp/loop-update.log)"
awk '{print $NF}' /tmp/loop-update.log | sort | uniq -c
grep -o '"version":"[^"]*"' /tmp/loop-update.log | sort | uniq -c
```

**Має бути видно:** початок циклу з відповідями 200; підсумок: усі запити з кодом 200, версії 1.0.0 і 1.1.0.

**Не має бути:** кодів `000`, `502`, `503`.

**Підпис:** Цикл запитів під час rolling update і підсумок

**Що видно:** Під час оновлення відправлено 708 запитів, і всі 708 повернули HTTP 200, жодної помилки. Спершу відповідали поди 1.0.0 (330 відповідей), потім 1.1.0 (378), тобто версія змінилась без простою.

### 3-06e-history-undo.png — 6.e Історія і відкат

**Що робимо:** Дивимось історію ревізій, відкочуємось на 1.0.0 і перевіряємо версію.

**Команди:**
```bash
kubectl rollout history deployment/api -n coworking-booking
kubectl rollout undo deployment/api -n coworking-booking
kubectl rollout status deployment/api -n coworking-booking
kubectl rollout history deployment/api -n coworking-booking
kubectl get deployment api -n coworking-booking -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
curl -s -H "Host: booking.local" http://localhost:8081/api/health/; echo
```

**Має бути видно:** історія 1 (1.0.0), 2 (1.1.0) → після undo 2 і 3; образ `:1.0.0`; `"version":"1.0.0"`.

**Не має бути:** помилок, крім стандартного `Warning ... previously managed with 'kubectl apply'`.

**Підпис:** Історія ревізій і відкат на 1.0.0

**Що видно:** До відкату в історії ревізії 1 (`initial deploy: image 1.0.0`) і 2 (`update image to 1.1.0`). Після `rollout undo` ревізія 1 стала новою ревізією 3, образ знову `devops-api:1.0.0`, і `/api/health/` відповідає `"version":"1.0.0"`. `Warning` про `kubectl apply` — стандартне попередження: undo не оновлює анотацію last-applied-configuration.

## 7. Діагностика

### 3-07a-imagepullbackoff.png — 7.a Неіснуючий тег 9.9.9

**Що робимо:** Вказуємо в маніфесті неіснуючий тег образу і застосовуємо його.

**Команди:**
```bash
sed -i '' 's#devops-api:1.0.0#devops-api:9.9.9#' k8s/api-deployment.yaml
grep -n "image:" k8s/api-deployment.yaml
kubectl apply -f k8s/api-deployment.yaml -n coworking-booking
sleep 40; kubectl get pods -n coworking-booking -l app=api
kubectl rollout status deployment/api -n coworking-booking --timeout=5s
curl -s -H "Host: booking.local" http://localhost:8081/api/health/; echo
```

**Має бути видно:** `image: ...:9.9.9`; один под `ErrImagePull`/`ImagePullBackOff` `0/1`, два старі `Running`; `timed out waiting for the condition`; curl відповідає `"status":"ok"`.

**Не має бути:** усіх подів у помилці.

**Підпис:** Оновлення на неіснуючий тег 9.9.9

**Що видно:** Новий под `api-64d5fbbf6d-rl772` у стані `ErrImagePull` (`0/1`), а два старі поди `api-6469f9dd88-*` далі `Running`. `rollout status` завершився за таймаутом: оновлено 1 з 2 реплік. Застосунок при цьому доступний: curl отримав відповідь `"status":"ok"` від старого пода `api-6469f9dd88-qdts6`.

### 3-07b-describe-events.png — 7.b describe і events

**Що робимо:** Шукаємо причину через опис пода і події.

**Команди:**
```bash
BAD=$(kubectl get pods -n coworking-booking -l app=api --field-selector=status.phase=Pending -o jsonpath='{.items[0].metadata.name}')
kubectl describe pod $BAD -n coworking-booking | tail -12
kubectl get events -n coworking-booking --field-selector involvedObject.name=$BAD --sort-by=.lastTimestamp
```

**Має бути видно:** у Events `Failed to pull image "...:9.9.9" ... not found`, `ErrImagePull`, `Back-off pulling image`, `ImagePullBackOff`.

**Не має бути:** порожнього `$BAD` (тоді `describe` покаже всі поди).

**Підпис:** Події пода з помилкою завантаження образу

**Що видно:** В Events пода `api-64d5fbbf6d-rl772` kubelet 4 рази пробував завантажити `ghcr.io/marcogr11/devops-api:9.9.9` і отримав `not found`, після чого перейшов у `Back-off pulling image` / `ImagePullBackOff`. Отже, причина в тому, що образу з таким тегом немає в реєстрі.

### 3-07c-logs.png — 7.c Логи

**Що робимо:** Дивимось логи зламаного пода і робочих api та worker.

**Команди:**
```bash
kubectl logs $BAD -n coworking-booking
kubectl logs deploy/api -n coworking-booking --tail=8
kubectl logs deploy/worker -n coworking-booking --tail=5
```

**Має бути видно:** для зламаного пода `image can't be pulled`; для api — міграції і старт gunicorn.

**Не має бути:** —

**Підпис:** Логи зламаного пода, api і worker

**Що видно:** Зламаний под логів не має, бо контейнер не стартував (`waiting to start: image can't be pulled`), тому для ImagePullBackOff дивляться events. Робочий под api застосував міграції (`No migrations to apply`) і запустив gunicorn на `0.0.0.0:8000`. Останні рядки worker — помилка `relation "booking_booking" does not exist` зі старту: worker запустився раніше, ніж api створив таблиці. Після цього под не перезапускався (RESTARTS 2 лише на старті, див. 7.e).

### 3-07d-exec.png — 7.d Вхід у контейнер

**Що робимо:** Заходимо в робочий контейнер api і перевіряємо його зсередини.

**Команди:**
```bash
kubectl exec -it deploy/api -n coworking-booking -- sh
whoami; hostname
ls /app
env | grep -E "POSTGRES_(USER|DB|HOST)|DJANGO_DEBUG"
python -c 'import urllib.request;print(urllib.request.urlopen("http://localhost:8000/api/health/").read().decode())'
python manage.py showmigrations booking
exit
```

**Має бути видно:** ім'я пода, вміст `/app`, змінні без паролів, `"status":"ok"`, міграції `[X]`, вихід `exit`.

**Не має бути:** `env` без фільтра.

**Підпис:** Інтерактивний shell у контейнері api

**Що видно:** Shell відкрився в поді `api-6469f9dd88-qdts6` від імені `root`. У `/app` лежить код Django-проєкту, змінні з ConfigMap на місці (`POSTGRES_HOST=postgres`, `DJANGO_DEBUG=0`). Застосунок відповідає зсередини на `localhost:8000`, обидві міграції `booking` застосовані (`[X]`).

### 3-07e-fix.png — 7.e Виправлення

**Що робимо:** Повертаємо тег 1.0.0 у маніфест і застосовуємо знову.

**Команди:**
```bash
sed -i '' 's#devops-api:9.9.9#devops-api:1.0.0#' k8s/api-deployment.yaml
git diff --stat k8s/api-deployment.yaml      # порожньо = файл як у git
kubectl apply -f k8s/api-deployment.yaml -n coworking-booking
kubectl rollout status deployment/api -n coworking-booking --timeout=180s
kubectl get pods -n coworking-booking
curl -s -H "Host: booking.local" http://localhost:8081/api/health/; echo
```

**Має бути видно:** порожній `git diff`; `successfully rolled out`; усі поди `Running`; `"status":"ok"`.

**Не має бути:** подів `ImagePullBackOff`.

**Підпис:** Повернення тегу 1.0.0 і відновлення rollout

**Що видно:** `git diff` порожній, тобто маніфест знову такий, як у git. Rollout завершився (`successfully rolled out`), под з помилкою прибрано, і всі 5 подів `Running`. `/api/health/` відповідає `"status":"ok"`, версія 1.0.0.

---

## Перехід до лаби №4 (обов'язково)

```bash
# зупинити port-forward-и (Ctrl+C)
kubectl delete namespace coworking-booking
kubectl wait --for=delete namespace/coworking-booking --timeout=300s
kubectl get namespace coworking-booking     # має бути NotFound
```
