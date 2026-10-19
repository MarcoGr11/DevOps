# Лабораторна №4 — чекліст скриншотів

14 скриншотів, лише пункти 6–9 методички (пункти 1–5 перевіряються кодом у
`chart/`). Кожен PNG кладеться в `reports/screens/лаб4/` під іменем із заголовка
`###`. Один блок команд = один скриншот (якщо не влазить в одне вікно,
кілька знімків одного блоку склеюються вертикально). `reports/build_report.py`
бере звідси «Що робимо», «Підпис» і «Що видно» для PDF.

Вікно терміналу — не ширше ~1800 px (приблизно 130 символів).

**Як копіювати:** кожен блок коду вставляється в термінал **цілком**, одним
копіюванням. Рядки, що закінчуються на `\`, — це одна команда, перенесена для
читабельності. Коментарів `#` у блоках немає: zsh без `setopt interactivecomments`
на них відповідає `command not found: #`. Що запускати в окремому терміналі,
написано над блоком.

## Порядок виконання

Розділи в PDF ідуть за методичкою, але знімати треба в такому порядку:

`4-06a → 4-06b → 4-07a → 4-07b → 4-07c → 4-07d → 4-07e → 4-08a → (термінал №3 для 4-09a) → 4-08b → 4-08c → 4-08d → 4-09a → 4-09b → 4-08e`

**Hook і test (4-09a, 4-09b) знімаються ДО `helm uninstall` (4-08e).**

## Перехід з лаби №3 (не знімається, обов'язково перед 4-07c)

```bash
kubectl delete namespace coworking-booking
kubectl wait --for=delete namespace/coworking-booking --timeout=300s
kubectl get namespace coworking-booking
```

Остання команда має відповісти `NotFound`, лише тоді переходити до `helm install`.

**Термінал №2** (лишити працювати до кінця, не знімається; запустити після 4-07c, коли є Ingress):

```bash
kubectl port-forward -n ingress-nginx svc/ingress-nginx-controller 8081:80
```

Паролі в кадр не потрапляють:
- значення `helm get values` проходять через `sed` з маскою `********`;
- на prod-upgrade паролі підставляються з `$(kubectl get secret ...)`;
- `x`/`y` у `helm template` — це заглушки, без них prod не рендериться.

Не запускати `helm get manifest`, `helm get all` і `helm upgrade --debug`: у них видно Secret.

---

## 6. Два середовища

### 4-06a-diff-dev-prod.png — 6.a Різниця dev і prod без встановлення

**Що робимо:** Рендеримо чарт для dev і prod командою `helm template`, нічого не встановлюючи, і порівнюємо результат.

**Команди:**
```bash
helm template booking chart/ -f chart/values-dev.yaml > /tmp/dev.yaml
helm template booking chart/ -f chart/values-prod.yaml \
  --set secret.postgresPassword=x \
  --set secret.djangoSecretKey=y > /tmp/prod.yaml
diff /tmp/dev.yaml /tmp/prod.yaml | grep -v -E "POSTGRES_PASSWORD|DJANGO_SECRET_KEY"
```

**Має бути видно:** різниця в `replicas` (1 → 3 і 1 → 2), `image` (1.0.0 → 1.1.0), `resources`, `DJANGO_DEBUG`, `BOOKING_TIMEOUT_CHECK_INTERVAL`, `storage` (1Gi → 10Gi), `host` (dev.booking.local → booking.example.com).

**Не має бути:** рядків `POSTGRES_PASSWORD`/`DJANGO_SECRET_KEY`.

**Підпис:** Різниця маніфестів dev і prod (helm template + diff)

**Що видно:** Обидва рендери пройшли без помилок, а `diff` показує лише ті поля, які перевизначає `values-prod.yaml`: `DJANGO_DEBUG` "1" → "0", `BOOKING_TIMEOUT_CHECK_INTERVAL` "15" → "60", розмір PVC `storage: 1Gi` → `10Gi`, `replicas: 1` → `3` для api, образи `devops-api:1.0.0` → `1.1.0` і `devops-worker:1.0.0` → `1.1.0`, більші requests/limits (api `cpu: "1"`, `memory: 512Mi`) та Ingress-хост `dev.booking.local` → `booking.example.com`. Змінюються й анотації `checksum/config` та `checksum/secret`, тому поди перезапускаються при зміні ConfigMap чи Secret. Рядки з паролями відфільтровано `grep -v`, від них лишився тільки заголовок `16,17c16,17`. Вивід не вмістився в одне вікно, тому склеєно два знімки; пунктир позначає кілька пропущених рядків між ними (ресурси postgres і початок блоку worker).

### 4-06b-priority.png — 6.b Пріоритет values < -f < --set

**Що робимо:** Рендеримо Deployment api трьома способами, щоб побачити, яке значення перемагає.

**Команди:**
```bash
echo "--- values.yaml"
helm template booking chart/ -s templates/deployment-api.yaml \
  | grep -E "^  replicas:|image:"
echo "--- -f values-prod.yaml"
helm template booking chart/ -s templates/deployment-api.yaml \
  -f chart/values-prod.yaml \
  --set secret.postgresPassword=x --set secret.djangoSecretKey=y \
  | grep -E "^  replicas:|image:"
echo "--- -f values-prod.yaml --set"
helm template booking chart/ -s templates/deployment-api.yaml \
  -f chart/values-prod.yaml \
  --set secret.postgresPassword=x --set secret.djangoSecretKey=y \
  --set replicaCount.api=5 --set image.api.tag=1.0.0 \
  | grep -E "^  replicas:|image:"
```

**Має бути видно:** 2 / `:1.0.0` (values.yaml) → 3 / `:1.1.0` (`-f values-prod.yaml`) → 5 / `:1.0.0` (`--set`).

**Не має бути:** `Error: ... is required`.

**Підпис:** Перекриття значень: values.yaml < -f < --set

**Що видно:** Той самий шаблон Deployment api відрендерено тричі. З самим `values.yaml` маємо `replicas: 2` і образ `1.0.0`. Із `-f values-prod.yaml` отримуємо `replicas: 3` і `1.1.0`, тобто файл перекрив значення за замовчуванням. Якщо додати `--set replicaCount.api=5 --set image.api.tag=1.0.0`, буде `replicas: 5` і `1.0.0`: `--set` має найвищий пріоритет і перекриває і файл, і `values.yaml`.

## 7. Перевірка і встановлення

### 4-07a-lint.png — 7.a helm lint і структура чарта

**Що робимо:** Перевіряємо чарт лінтером і показуємо його структуру.

**Команди:**
```bash
helm lint chart/
helm lint chart/ -f chart/values-dev.yaml
find chart -type f ! -name DEMO.md | sort
```

Замість `find` можна `tree chart/` (спершу `brew install tree`).

**Має бути видно:** `1 chart(s) linted, 0 chart(s) failed` двічі; файли `Chart.yaml`, `values*.yaml`, `templates/*.yaml`, `_helpers.tpl`, `NOTES.txt`, `tests/test-health.yaml`.

**Не має бути:** `[ERROR]`. `[INFO] icon is recommended` — це нормально.

**Підпис:** helm lint і структура каталогу chart/

**Що видно:** `helm lint` для чарта з базовими значеннями і з `values-dev.yaml` двічі показує `1 chart(s) linted, 0 chart(s) failed`; єдине повідомлення — інформаційне `icon is recommended`. Нижче видно структуру чарта: `Chart.yaml`, три файли values, шаблони всіх об'єктів лаби №3, `_helpers.tpl`, `NOTES.txt`, hook `hook-db-check.yaml` і тест `tests/test-health.yaml`.

### 4-07b-compare.png — 7.b Набір об'єктів: чарт vs лаба №3

**Що робимо:** Порівнюємо, які об'єкти створює чарт і які були в маніфестах лаби №3.

**Команди:**
```bash
echo "--- helm template (dev):"
helm template booking chart/ -f chart/values-dev.yaml | grep "^kind:" | sort | uniq -c
echo "--- k8s/ (лаба 3):"
cat k8s/*.yaml | grep "^kind:" | sort | uniq -c
```

**Має бути видно:** однакові ConfigMap, 3 Deployment, Ingress, PVC, 2 Service. У чарті додатково Secret (у лабі №3 створювався командою), Job (hook) і Pod (test); Namespace у чарті немає, його створює `--create-namespace`.

**Не має бути:** —

**Підпис:** Об'єкти чарта порівняно з маніфестами лаби №3

**Що видно:** Чарт створює ті самі об'єкти, що й маніфести лаби №3: 1 ConfigMap, 3 Deployment, 1 Ingress, 1 PVC, 2 Service. До них додано Secret (у лабі №3 його створювали командою `kubectl create secret`), Job (pre-upgrade hook) і Pod (`helm test`). Окремого Namespace у рендері немає, бо namespace створює сам Helm через `--create-namespace`.

### 4-07c-install.png — 7.c helm install

**Що робимо:** Встановлюємо реліз `booking` з dev-значеннями.

**Команди:**
```bash
kubectl get namespace coworking-booking
helm install booking chart/ -f chart/values-dev.yaml \
  -n coworking-booking --create-namespace
```

**Має бути видно:** `NotFound`; `STATUS: deployed`, `REVISION: 1`; блок `NOTES` (образ, replicas, як відкрити через Ingress/port-forward, `helm test`).

**Не має бути:** `cannot re-use a name`, `already exists`.

**Підпис:** Встановлення релізу booking (dev) і NOTES

**Що видно:** Перед встановленням `kubectl get namespace` повертає `NotFound`, тобто стан лаби №3 повністю видалено. `helm install` створює namespace і реліз: `STATUS: deployed`, `REVISION: 1`, `LAST DEPLOYED 01:52:27`. Далі виводяться NOTES із чарта: версія `booking 0.1.0`, образ `devops-api:1.0.0` з `replicas: 1` (dev), хост `dev.booking.local` і підказки для port-forward і `helm test`.

### 4-07d-list-status.png — 7.d list, status, get values, поди

**Що робимо:** Перевіряємо стан релізу, передані значення і поди.

**Команди:**
```bash
kubectl rollout status deployment/booking-api -n coworking-booking --timeout=180s
helm list -n coworking-booking
helm status booking -n coworking-booking | head -6
helm get values booking -n coworking-booking \
  | sed -E 's/(postgresPassword|djangoSecretKey): .*/\1: ********/'
kubectl get pods -n coworking-booking
```

**Має бути видно:** реліз `booking`, ревізія 1, `deployed`, чарт `booking-0.1.0`; `USER-SUPPLIED VALUES` з dev-значеннями; 3 поди `Running`.

**Не має бути:** значень паролів.

**Підпис:** Стан релізу, значення користувача і поди

**Що видно:** Rollout api завершився (`successfully rolled out`). `helm list` показує реліз `booking`: ревізія 1, `deployed`, chart `booking-0.1.0`, app version `1.0.0`. `helm get values` виводить лише значення, передані користувачем з `values-dev.yaml`: interval "15", debug "1", теги `1.0.0`, хост `dev.booking.local`, 1Gi, по одній репліці api і worker, зменшені ресурси; секретів серед них немає. Усі три поди (`booking-api-cbc7c7556-6bk7d`, postgres, worker) мають статус `Running 1/1`. Перезапуски api і worker відбулися, поки стартував postgres.

### 4-07e-helm-state.png — 7.e Де Helm зберігає стан

**Що робимо:** Показуємо Secret, у якому Helm зберігає ревізію релізу.

**Команди:**
```bash
kubectl get secrets -n coworking-booking | grep helm
kubectl get secret sh.helm.release.v1.booking.v1 -n coworking-booking \
  -o jsonpath='{.metadata.labels}'; echo
```

**Має бути видно:** `sh.helm.release.v1.booking.v1` типу `helm.sh/release.v1`; мітки `name=booking`, `owner=helm`, `status=deployed`, `version=1`.

**Не має бути:** `-o yaml` чи `.data` (там закодований маніфест разом із Secret).

**Підпис:** Secret sh.helm.release.v1.booking.v1 зі станом релізу

**Що видно:** Ревізію релізу Helm зберігає в кластері як Secret `sh.helm.release.v1.booking.v1` типу `helm.sh/release.v1`. За мітками `name=booking`, `owner=helm`, `status=deployed`, `version=1` Helm знаходить історію релізу; кожна наступна ревізія додає новий такий Secret.

## 8. Життєвий цикл релізу

### 4-08a-upgrade-set.png — 8.a upgrade через --set

**Що робимо:** Оновлюємо лише тег образу api, решта dev-значень лишається.

**Команди:**
```bash
helm upgrade booking chart/ -n coworking-booking \
  --reuse-values --set image.api.tag=1.1.0 | head -6
kubectl rollout status deployment/booking-api -n coworking-booking
sleep 10
curl -s -H "Host: dev.booking.local" http://localhost:8081/api/health/; echo
```

**Має бути видно:** `has been upgraded`, `REVISION: 2`; `successfully rolled out`; `"version":"1.1.0"`.

**Не має бути:** `"version":"1.0.0"` у curl (тоді повторити curl через 10 с).

**Підпис:** Upgrade тегу api до 1.1.0 через --set

**Що видно:** Завдяки `--reuse-values` змінився лише тег образу api, решта dev-значень залишилась без змін. Upgrade створив `REVISION: 2`, rollout пройшов, а запит через Ingress (`Host: dev.booking.local`) повертає `"version":"1.1.0"` від нового пода `booking-api-674f7cf49-nv7xc`.

### 4-08b-upgrade-prod.png — 8.b upgrade з values-prod

**Що робимо:** Переводимо реліз на prod-значення; паролі беремо з поточного Secret, щоб postgres прийняв той самий пароль.

**Підготовка до 4-09a:** перед цим блоком у **терміналі №3** запустити команду нижче і не закривати до кінця upgrade (її вивід знімається для 4-09a):

```bash
kubectl get jobs -n coworking-booking -w
```

**Команди:**
```bash
helm upgrade booking chart/ -n coworking-booking -f chart/values-prod.yaml \
  --set secret.postgresPassword="$(kubectl get secret booking-secret -n coworking-booking \
      -o jsonpath={.data.POSTGRES_PASSWORD} | base64 -d)" \
  --set secret.djangoSecretKey="$(kubectl get secret booking-secret -n coworking-booking \
      -o jsonpath={.data.DJANGO_SECRET_KEY} | base64 -d)" \
  | head -6
kubectl rollout status deployment/booking-api -n coworking-booking --timeout=300s
kubectl get pods -n coworking-booking
```

**Має бути видно:** `REVISION: 3`; 3 поди `booking-api`, 2 `booking-worker`, 1 postgres — усі `Running`.

**Не має бути:** значень паролів (у кадрі лише `$(kubectl get secret ...)`), `UPGRADE FAILED`.

**Підпис:** Upgrade релізу на values-prod.yaml

**Що видно:** Реліз переведено на prod-значення: `REVISION: 3`, `LAST DEPLOYED 01:54:52`. Паролі передано через `$(kubectl get secret … | base64 -d)`, тому в терміналі їх значень немає. Rollout видно поетапно: 1, потім 2 з 3 нових реплік, далі очікування видалення старих. Після цього працюють 3 поди `booking-api-7489549547-*` і 2 поди `booking-worker-66dfbfd595-*`, а старі `674f7cf49-*` і `7695b9f9bb-*` перебувають у `Terminating`. Postgres перестворено з prod-ресурсами (`booking-postgres-69f4d4fbc7-x2frj`).

### 4-08c-history.png — 8.c Історія і значення ревізій

**Що робимо:** Дивимось історію ревізій і що саме змінювалось між ними.

**Команди:**
```bash
helm history booking -n coworking-booking
v() {
  helm get values booking -n coworking-booking --revision $1 \
    | sed -E 's/(postgresPassword|djangoSecretKey): .*/\1: ********/'
}
echo "=== ревізія 1 -> 2"
diff <(v 1) <(v 2)
echo "=== ревізія 2 -> 3"
diff <(v 2) <(v 3)
```

**Має бути видно:** ревізії 1–3 (1, 2 — `superseded`, 3 — `deployed`); 1 → 2 змінився лише `tag: 1.1.0`; 2 → 3 — репліки, теги, ресурси, хост, `secret: ********`.

**Не має бути:** справжніх значень `postgresPassword`/`djangoSecretKey`.

**Підпис:** helm history і різниця значень між ревізіями

**Що видно:** `helm history` показує три ревізії: 1 — `Install complete`, 2 і 3 — `Upgrade complete`; остання має статус `deployed`. Різниця 1 → 2 складається з одного рядка `tag: 1.0.0` → `1.1.0`, тобто з того, що передано через `--set`. Різниця 2 → 3 — це повний перехід на prod: interval "60", debug "0", хост `booking.example.com`, `size: 10Gi`, репліки api 3 і worker 2, prod-ресурси. Також додався блок `secret:`, значення якого замасковано (`********`). Пунктир позначає кілька пропущених рядків між двома знімками (старі `api: 1`, `worker: 1`).

### 4-08d-rollback.png — 8.d rollback

**Що робимо:** Відкочуємо реліз на ревізію 1 (dev, образ 1.0.0).

**Команди:**
```bash
helm rollback booking 1 -n coworking-booking
helm history booking -n coworking-booking
kubectl rollout status deployment/booking-api -n coworking-booking
sleep 10
curl -s -H "Host: dev.booking.local" http://localhost:8081/api/health/; echo
```

**Має бути видно:** `Rollback was a success`; нова ревізія 4 `Rollback to 1` (`deployed`); `"version":"1.0.0"`.

**Не має бути:** —

**Підпис:** Rollback на ревізію 1

**Що видно:** `helm rollback booking 1` пройшов успішно (`Rollback was a success!`). В історії з'явилась нова ревізія 4 з описом `Rollback to 1`: Helm не видаляє ревізії, а додає нову з конфігурацією першої. Після rollout запит повертає `"version":"1.0.0"` від пода `booking-api-cbc7c7556-hfhng`; це той самий ReplicaSet `cbc7c7556`, що і після install.

> **Тепер зняти 4-09a і 4-09b, і лише після цього — 4-08e.**

### 4-08e-uninstall.png — 8.e uninstall

**Що робимо:** Видаляємо реліз і перевіряємо, що в namespace нічого не лишилось.

**Команди:**
```bash
helm uninstall booking -n coworking-booking
sleep 15
kubectl get all -n coworking-booking
helm list -n coworking-booking
kubectl get secrets -n coworking-booking | grep helm
```

**Має бути видно:** `release "booking" uninstalled`; `No resources found in coworking-booking namespace.`; порожній `helm list`; порожній вивід `grep helm`.

**Не має бути:** подів у `Terminating` (тоді почекати й повторити `get all`).

**Підпис:** helm uninstall і порожній namespace

**Що видно:** `release "booking" uninstalled`. Через 15 секунд у namespace лишився тільки один под api, який ще завершує роботу (`Terminating`); жодного Deployment, Service чи ReplicaSet уже немає. `helm list` порожній, а `kubectl get secrets` відповідає `No resources found`, тобто Secret-и з історією релізу Helm теж видалив.

## 9. Hook і helm test

### 4-09a-hook.png — 9.a pre-upgrade hook

**Що робимо:** Показуємо, що перед upgrade запускався Job перевірки БД.

**Команди:**
Верхня частина скріна — вивід **терміналу №3** (`kubectl get jobs -w`, запущений перед 4-08b, потім Ctrl+C). Нижня — **основний термінал** після 4-08d:

```bash
grep -n "helm.sh/hook" chart/templates/hook-db-check.yaml
kubectl get events -n coworking-booking \
  --field-selector involvedObject.kind=Job --sort-by=.lastTimestamp
```

**Має бути видно:** у `-w` з'являється `booking-db-check` (`0/1` → `1/1`) і зникає; анотації `pre-upgrade` і `hook-delete-policy`; події `SuccessfulCreate` + `Completed` по одному на кожен upgrade (ревізії 2 і 3) і жодної на rollback.

**Не має бути:** `BackoffLimitExceeded`.

**Підпис:** pre-upgrade hook booking-db-check

**Що видно:** У шаблоні hook позначено анотаціями `helm.sh/hook: pre-upgrade`, `hook-weight: "0"` і `hook-delete-policy: before-hook-creation,hook-succeeded`. У подіях namespace видно два запуски Job `booking-db-check` (поди `22hc4` і `bp6x8`), кожен із `SuccessfulCreate` і `Completed`. За часом вони збігаються з двома upgrade (ревізії 2 і 3); на rollback hook не запускався. Сам Job після успіху видалено політикою `hook-succeeded`, тому в `kubectl get jobs` його вже немає. Знімок зроблено після uninstall (події namespace ще зберігались), а вивід `kubectl get jobs -w` не знято.

### 4-09b-helm-test.png — 9.b helm test

**Що робимо:** Запускаємо smoke-тест, вбудований у чарт.

**Команди:**
```bash
helm test booking -n coworking-booking \
  | grep -v -E "^(NOTES|Release|api image|Wait|Via|Smoke|  |$)"
```

**Має бути видно:** `TEST SUITE: booking-test-health`, `Phase: Succeeded`.

**Не має бути:** `Phase: Failed`.

**Підпис:** helm test: smoke-тест /api/health/

**Що видно:** `helm test` запустив тестовий под `booking-test-health`, і тест пройшов: `Phase: Succeeded`, тривалість близько секунди (01:59:33 → 01:59:34). Тест виконувався на релізі, встановленому повторно після uninstall (`REVISION: 1`, `LAST DEPLOYED 01:58:27`) з тими самими dev-значеннями. Рядки NOTES відфільтровано `grep -v`.

---

## Після лаби

Спершу зупинити port-forward-и (Ctrl+C), потім:

```bash
kubectl delete namespace coworking-booking
kubectl wait --for=delete namespace/coworking-booking --timeout=300s
```
