# Coworking Booking System

Лабораторна робота з предмету **"Технології DevOps"**, тема **"Віртуалізація та
контейнеризація"**.

Система бронювання коворкінгу: клієнти бронюють переговорні кімнати або робочі
місця (`Resource`) на конкретні часові слоти (`Slot`). Бронювання (`Booking`)
створюється зі статусом `pending`, підтверджується або скасовується вручну
через API, а непідтверджені бронювання автоматично скасовуються фоновим
воркером після таймауту — типовий приклад задачі, яку логічно винести з
основного застосунку в окремий контейнеризований мікросервіс.

## Стек

Python, Django + Django REST Framework, PostgreSQL, Docker / Docker Compose.

## Структура репозиторію

```
.
├── api/                    # Django + DRF застосунок
│   ├── config/             # settings, urls, wsgi
│   ├── booking/             # застосунок booking: models, serializers, views, tests
│   ├── manage.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .dockerignore
├── worker/                 # окремий мікросервіс (без Django)
│   ├── worker.py
│   ├── tests/test_worker.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .dockerignore
├── k8s/                    # маніфести Kubernetes (лаба 3) + DEMO.md зі звітом
├── chart/                  # Helm-чарт (лаба 4): templates/, values*.yaml, DEMO.md
├── docker-compose.yml
├── .gitignore
└── README.md
```

## Моделі

- **Resource** — `name`, `resource_type` (`room`/`desk`), `capacity`
- **Slot** — `resource` (FK), `start_time`, `end_time`;
  `unique_together(resource, start_time)` захищає від дублікатів слоту
- **Booking** — `slot` (FK), `customer_name`, `customer_email`,
  `status` (`pending`/`confirmed`/`cancelled`), `created_at`

**Бізнес-правило:** не можна створити бронювання для слоту, який вже має
активне бронювання (`pending` або `confirmed`). Перевірка виконується у
`BookingSerializer.validate_slot` і повертає `400` з поясненням у полі
`slot`.

## API-ендпоінти

Базовий URL (локально): `http://localhost:8000`

| Метод | URL | Опис |
|---|---|---|
| GET | `/api/health/` | health-check: `{"status":"ok","version":"<APP_VERSION>","pod":"<hostname>"}` |
| GET/POST | `/api/resources/` | список / створення Resource |
| GET/PUT/PATCH/DELETE | `/api/resources/{id}/` | деталі / оновлення / видалення Resource |
| GET/POST | `/api/slots/?resource=<id>&date=YYYY-MM-DD` | список Slot з фільтром по ресурсу і даті, поле `is_available` |
| GET/PUT/PATCH/DELETE | `/api/slots/{id}/` | деталі / оновлення / видалення Slot |
| GET/POST | `/api/bookings/` | список / створення Booking (статус одразу `pending`) |
| GET | `/api/bookings/{id}/` | деталі Booking |
| PATCH | `/api/bookings/{id}/confirm/` | підтвердити бронювання (`pending` → `confirmed`) |
| PATCH | `/api/bookings/{id}/cancel/` | скасувати бронювання (→ `cancelled`) |

### Приклади (curl)

```bash
# health-check
curl http://localhost:8000/api/health/

# створити ресурс
curl -X POST http://localhost:8000/api/resources/ \
  -H "Content-Type: application/json" \
  -d '{"name":"Meeting Room A","resource_type":"room","capacity":6}'

# створити слот
curl -X POST http://localhost:8000/api/slots/ \
  -H "Content-Type: application/json" \
  -d '{"resource":1,"start_time":"2026-09-17T10:00:00Z","end_time":"2026-09-17T11:00:00Z"}'

# список слотів ресурсу 1 на конкретну дату з ознакою is_available
curl "http://localhost:8000/api/slots/?resource=1&date=2026-09-17"

# забронювати слот (статус одразу pending)
curl -X POST http://localhost:8000/api/bookings/ \
  -H "Content-Type: application/json" \
  -d '{"slot":1,"customer_name":"Ivan","customer_email":"ivan@example.com"}'

# повторна спроба забронювати той самий слот -> 400
curl -X POST http://localhost:8000/api/bookings/ \
  -H "Content-Type: application/json" \
  -d '{"slot":1,"customer_name":"Petro","customer_email":"petro@example.com"}'
# {"slot":["This slot already has an active booking (pending or confirmed)."]}

# підтвердити бронювання
curl -X PATCH http://localhost:8000/api/bookings/1/confirm/

# скасувати бронювання (звільняє слот)
curl -X PATCH http://localhost:8000/api/bookings/1/cancel/
```

## Postman-колекція

У корені репозиторію лежить `postman_collection.json` (формат Postman
Collection v2.1) з усіма ендпоінтами API: health-check, CRUD для Resource,
CRUD для Slot, create/confirm/cancel для Booking, а також готовий сценарій
"Scenario: Double Booking" — два послідовні POST на той самий slot, де
другий запит очікувано повертає `400`.

Як імпортувати:

1. Відкрити Postman → **File → Import**.
2. Обрати файл `postman_collection.json` з кореня репозиторію (або
   перетягнути його у вікно імпорту).
3. Колекція "Coworking Booking API" з'явиться у списку колекцій; змінна
   `{{base_url}}` уже виставлена на `http://localhost:8000` (за потреби
   змінити у вкладці Variables колекції).
4. Запустити `docker compose up` і виконувати запити — `resource_id`,
   `slot_id`, `booking_id` підставляються автоматично зі відповіді
   попереднього запиту (через test-скрипти колекції).

## Worker (мікросервіс автоскасування)

`worker/worker.py` — звичайний Python-скрипт (без Django), який підключається
напряму до тієї ж PostgreSQL через `psycopg2`. Раз на
`BOOKING_TIMEOUT_CHECK_INTERVAL` секунд він виконує один SQL-запит:
переводить у статус `cancelled` усі бронювання зі статусом `pending`, чий
`created_at` старіший за `BOOKING_TIMEOUT_MINUTES` хвилин. Це автоматично
звільняє слот (`Slot.is_available` знову стає `true`), бо `is_available`
обчислюється як відсутність активного (`pending`/`confirmed`) бронювання.

Ця задача — фонова, періодична, не залежить від HTTP-запитів — тому винесена
в окремий контейнер, а не в Django (наприклад, через Celery beat чи
management command): менше залежностей, простіший образ, незалежний
життєвий цикл і масштабування.

Змінні середовища worker'а: `POSTGRES_DB`, `POSTGRES_USER`,
`POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`,
`BOOKING_TIMEOUT_CHECK_INTERVAL` (секунди, за замовчуванням 60),
`BOOKING_TIMEOUT_MINUTES` (хвилини, за замовчуванням 15).

## Запуск

```bash
docker compose up --build
```

Піднімає три сервіси:
- **db** — `postgres:16-alpine` з volume та healthcheck
- **api** — Django + DRF на `http://localhost:8000`, при старті виконує
  `migrate --noinput` і запускається через `gunicorn`
- **worker** — фоновий скрипт, чекає, поки `db` стане healthy, і поки
  контейнер `api` стартує

Зупинити: `docker compose down` (додати `-v`, щоб видалити volume з даними
БД).

## Тести

### Локально (api, sqlite fallback — POSTGRES_* env не задані)

```bash
cd api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py test
```

### Локально (worker, з мок-з'єднанням до БД — реальна БД не потрібна)

```bash
cd worker
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests
```

### У контейнері

```bash
docker compose up -d
docker compose exec api python manage.py test
```

## Приклад перевірки автоскасування по таймауту

Для демонстрації без очікування 15 хвилин тимчасово зменшіть таймаут у
`docker-compose.yml` (сервіс `worker`): `BOOKING_TIMEOUT_MINUTES: 0`,
`BOOKING_TIMEOUT_CHECK_INTERVAL: 5`, перезапустіть `docker compose up -d
worker` і подивіться логи:

```bash
docker compose logs -f worker
# worker INFO cancelled stale bookings: [1]
```

Після цього `GET /api/slots/{id}/` знову покаже `"is_available": true`, а
`GET /api/bookings/{id}/` — `"status": "cancelled"`.

## Kubernetes (лабораторна №3)

Маніфести лежать у `k8s/`, по одному файлу на об'єкт. Усі об'єкти живуть у
namespace `coworking-booking`.

| Файл | Об'єкт |
|---|---|
| `namespace.yaml` | Namespace `coworking-booking` |
| `configmap.yaml` | ConfigMap `booking-config` |
| `postgres-pvc.yaml` | PVC `postgres-data` (1Gi, RWO) |
| `postgres-deployment.yaml` | Deployment `postgres` (1 репліка, `strategy: Recreate`) |
| `postgres-service.yaml` | Service `postgres` (ClusterIP, 5432) |
| `api-deployment.yaml` | Deployment `api`: 2 репліки, requests/limits, readiness- і liveness-проби на `/api/health/` |
| `api-service.yaml` | Service `api` (ClusterIP, 80 → 8000) |
| `api-ingress.yaml` | Ingress `api` для хоста `booking.local` |
| `worker-deployment.yaml` | Deployment `worker` (2 репліки) |

Secret `booking-secret` навмисно не закомічений: його значення задаються
командою `kubectl create secret` (див. нижче).

### Образи

Використовуються семантичні версії, не `latest`. Їх збирають і пушать
вручну, версія вшивається через build-arg і видна у відповіді `/api/health/`
та в стартовому лозі worker:

```bash
for svc in api worker; do for v in 1.0.0 1.1.0; do
  docker build --build-arg APP_VERSION=$v -t devops-$svc:$v ./$svc
  docker tag devops-$svc:$v ghcr.io/marcogr11/devops-$svc:$v
  docker push ghcr.io/marcogr11/devops-$svc:$v
done; done
```

Пакети в ghcr.io публічні, тому `imagePullSecret` не потрібен.

### Порядок розгортання

```bash
minikube start --driver=docker
minikube addons enable metrics-server
minikube addons enable ingress

kubectl apply -f k8s/namespace.yaml
kubectl create secret generic booking-secret -n coworking-booking \
  --from-literal=POSTGRES_PASSWORD="$(openssl rand -hex 16)" \
  --from-literal=DJANGO_SECRET_KEY="$(openssl rand -hex 32)"
kubectl apply -f k8s/ -n coworking-booking
kubectl get pods -n coworking-booking -w
```

При першому старті api і worker можуть кілька разів перезапуститись
(`Connection refused`), поки postgres не стане готовим. Kubernetes сам
перезапускає контейнери, і стан стабілізується приблизно за хвилину.

### Параметри

**ConfigMap `booking-config`** підключається в api і worker через `envFrom`,
а в postgres — через `configMapKeyRef`:

| Ключ | Значення | Хто використовує |
|---|---|---|
| `POSTGRES_DB` | `booking` | api, worker, postgres |
| `POSTGRES_USER` | `booking` | api, worker, postgres |
| `POSTGRES_HOST` | `postgres` (ім'я Service) | api, worker |
| `POSTGRES_PORT` | `5432` | api, worker |
| `DJANGO_DEBUG` | `0` | api |
| `DJANGO_ALLOWED_HOSTS` | `*` | api |
| `BOOKING_TIMEOUT_CHECK_INTERVAL` | `30` (с) | worker |
| `BOOKING_TIMEOUT_MINUTES` | `15` (хв) | worker |

**Secret `booking-secret`** підключається в api і worker через `envFrom`, а в
postgres — через `secretKeyRef`:

| Ключ | Опис |
|---|---|
| `POSTGRES_PASSWORD` | пароль користувача БД |
| `DJANGO_SECRET_KEY` | секретний ключ Django |

### Доступ з хоста

З драйвером docker на macOS IP minikube (`192.168.49.2`) недоступний з
хоста напряму. Є три способи:

```bash
# 1) port-forward на Service: завжди веде в ОДИН под, підходить для ручної перевірки
kubectl port-forward -n coworking-booking svc/api 8080:80
curl http://localhost:8080/api/health/

# 2) через Ingress, без sudo: port-forward на ingress-контролер;
#    балансує між усіма подами, переживає rolling update
kubectl port-forward -n ingress-nginx svc/ingress-nginx-controller 8081:80
curl -H "Host: booking.local" http://localhost:8081/api/health/

# 3) через Ingress із «справжнім» доменом (потрібен sudo для порту 80)
echo "127.0.0.1 booking.local" | sudo tee -a /etc/hosts
minikube tunnel            # окремий термінал
curl http://booking.local/api/health/   # або відкрити в браузері
```

### Рішення

- **Postgres: Deployment + окремий PVC замість StatefulSet.** Інстанс БД
  один. Стабільні мережеві імена подів, впорядкований старт і
  `volumeClaimTemplates` StatefulSet'а потрібні, коли реплік кілька
  (primary/replica). Для одного пода Deployment + PVC простіший і так само
  зберігає дані між перезапусками. `strategy: Recreate` гарантує, що
  RWO-том не намагатимуться змонтувати два поди одночасно.
- **Worker з 2 репліками безпечний.** Скасування робиться одним атомарним
  `UPDATE ... WHERE status='pending' ... RETURNING id`. Postgres блокує
  рядки, і друга транзакція після очікування переоцінює `WHERE` (READ
  COMMITTED). Тому кожне бронювання скасується рівно один раз. Ціна другої
  репліки — лише один зайвий легкий запит за інтервал.
- **Rolling update без простою** забезпечують readiness-проба,
  `maxUnavailable: 0` / `maxSurge: 1` і `preStop: sleep 5`. Останнє дає
  Service та Ingress час прибрати под з ендпоінтів до того, як gunicorn
  отримає SIGTERM.
- **Проби.** readiness — `initialDelaySeconds: 5`, `periodSeconds: 5`: под
  швидко потрапляє в балансування. liveness — `initialDelaySeconds: 30`,
  `periodSeconds: 10`, `timeoutSeconds: 3`: не вбиває контейнер, поки той
  ще стартує або виконує `migrate`.
- **Відоме обмеження:** `migrate` виконується в `CMD` кожного api-пода. При
  першому розгортанні кілька подів можуть запустити його одночасно. Для
  production це варто винести в Job або initContainer.

Повний вивід команд розгортання, життєвого циклу й діагностики зібрано в
[`k8s/DEMO.md`](k8s/DEMO.md).

## Helm-чарт (лабораторна №4)

Маніфести з `k8s/` упаковано в чарт `chart/` (ім'я чарта `booking`). Чарт
перевірено з Helm v3.22.

```
chart/
├── Chart.yaml
├── values.yaml           # база, значення за замовчуванням = dev
├── values-dev.yaml       # перекриття для dev
├── values-prod.yaml      # перекриття для prod
├── DEMO.md               # звіт: вивід команд для пунктів 6–9
└── templates/
    ├── _helpers.tpl      # fullname, labels, selectorLabels, image, postgresHost
    ├── NOTES.txt
    ├── namespace.yaml  configmap.yaml  secret.yaml  pvc.yaml
    ├── deployment-postgres.yaml  service-postgres.yaml
    ├── deployment-api.yaml  service-api.yaml  ingress-api.yaml
    ├── deployment-worker.yaml
    ├── hook-db-check.yaml     # pre-upgrade Job: перевірка підключення до БД
    └── tests/test-health.yaml # helm test: curl /api/health/
```

### `version` і `appVersion`

- **`version: 0.1.0`** — версія самого пакета-чарта: шаблонів, структури
  `values.yaml`, хелперів, hook-ів. Її підвищують, коли змінюється чарт.
  Наприклад, додали hook або новий параметр у values → `0.2.0`, хоча
  образи лишились ті самі.
- **`appVersion: "1.0.0"`** — версія застосунку, тобто Docker-образів
  `ghcr.io/marcogr11/devops-api|worker`. Якщо `image.api.tag` /
  `image.worker.tag` не задані, шаблон бере тег саме з `appVersion`
  (`.Values.image.*.tag | default .Chart.AppVersion`). Вона ж потрапляє в
  мітку `app.kubernetes.io/version`.
- Вони змінюються незалежно. Вихід образів 1.1.0 без змін у шаблонах — це
  новий `appVersion` при тому самому `version` (або просто `--set
  image.api.tag=1.1.0`). Рефакторинг шаблонів без нових образів — новий
  `version` при тому самому `appVersion`.

### Імена та мітки

Усі імена об'єктів будуються з `booking.fullname`:
- `<release>-booking`;
- або просто `<release>`, якщо ім'я релізу вже містить `booking`.

Тому реліз `booking` створює `booking-api`, `booking-postgres`, … , а реліз
`demo` — `demo-booking-api`, … . Два релізи співіснують в одному namespace
без конфліктів (перевірено, див. `chart/DEMO.md`, 9.2).

Мітки на всіх об'єктах: `helm.sh/chart`, `app.kubernetes.io/name`,
`instance`, `version`, `managed-by`, `part-of` і `component`. Selector-и
використовують лише `name`, `instance` і `component`.

### Параметри `values.yaml`

| Ключ | Опис | За замовчуванням |
|---|---|---|
| `image.api.repository` | образ API | `ghcr.io/marcogr11/devops-api` |
| `image.api.tag` | тег образу API (порожній → `appVersion`) | `""` → `1.0.0` |
| `image.worker.repository` | образ worker | `ghcr.io/marcogr11/devops-worker` |
| `image.worker.tag` | тег образу worker (порожній → `appVersion`) | `""` → `1.0.0` |
| `image.postgres.repository` / `.tag` | образ PostgreSQL | `postgres` / `16-alpine` |
| `image.*.pullPolicy` | політика завантаження образу | `IfNotPresent` |
| `replicaCount.api` | репліки API | `2` |
| `replicaCount.worker` | репліки worker | `2` |
| `replicaCount.postgres` | репліки PostgreSQL (RWO-том, не масштабувати) | `1` |
| `service.type` | тип Service для API | `ClusterIP` |
| `service.port` | порт Service для API | `80` |
| `service.targetPort` | порт контейнера API (gunicorn) | `8000` |
| `postgres.port` | порт PostgreSQL (Service, контейнер, `POSTGRES_PORT`) | `5432` |
| `postgres.persistence.enabled` | PVC для даних БД (`false` → `emptyDir`) | `true` |
| `postgres.persistence.size` | розмір PVC (лише при першому встановленні) | `1Gi` |
| `postgres.persistence.storageClass` | StorageClass (порожній → дефолтний) | `""` |
| `resources.api` | requests/limits для API | `100m/128Mi` → `500m/256Mi` |
| `resources.worker` | requests/limits для worker | `50m/64Mi` → `200m/128Mi` |
| `resources.postgres` | requests/limits для PostgreSQL | `100m/128Mi` → `500m/512Mi` |
| `config.postgresDb` | `POSTGRES_DB` | `booking` |
| `config.postgresUser` | `POSTGRES_USER` | `booking` |
| `config.djangoDebug` | `DJANGO_DEBUG` | `"0"` |
| `config.djangoAllowedHosts` | `DJANGO_ALLOWED_HOSTS` | `"*"` |
| `config.bookingTimeoutCheckInterval` | `BOOKING_TIMEOUT_CHECK_INTERVAL`, с | `"30"` |
| `config.bookingTimeoutMinutes` | `BOOKING_TIMEOUT_MINUTES`, хв | `"15"` |
| `secret.postgresPassword` | `POSTGRES_PASSWORD` (Secret, обов'язковий) | dev-заглушка `dev-only-password` |
| `secret.djangoSecretKey` | `DJANGO_SECRET_KEY` (Secret, обов'язковий) | dev-заглушка |
| `ingress.enabled` | створювати Ingress | `true` |
| `ingress.className` | IngressClass | `nginx` |
| `ingress.host` | хост Ingress | `booking.local` |
| `namespace.create` | рендерити Namespace (не разом із `--create-namespace`) | `false` |
| `hooks.dbCheck.enabled` | pre-upgrade Job перевірки БД | `true` |
| `tests.image` | образ для `helm test` | `curlimages/curl:8.11.1` |

`POSTGRES_HOST` не винесено в values: він обчислюється з імені релізу
(`<fullname>-postgres`), щоб другий реліз не підключився до чужої БД.

**dev і prod:**

| | `values-dev.yaml` | `values-prod.yaml` |
|---|---|---|
| теги api/worker | `1.0.0` | `1.1.0` |
| репліки api / worker | 1 / 1 | 3 / 2 |
| ресурси | менші (api `50m/96Mi` → `250m/192Mi`) | більші (api `250m/256Mi` → `1/512Mi`) |
| `DJANGO_DEBUG` | `1` | `0` |
| інтервал worker | 15 с | 60 с |
| Ingress | `dev.booking.local` | `booking.example.com` |
| PVC | 1Gi | 10Gi |
| секрети | dev-заглушки з `values.yaml` | порожні → обов'язково через `--set` |

### Встановлення

```bash
# dev
helm install booking chart/ -f chart/values-dev.yaml \
  -n coworking-booking --create-namespace

# prod: секрети тільки через --set (або -f з файлу поза git)
helm install booking chart/ -f chart/values-prod.yaml \
  -n coworking-booking --create-namespace \
  --set secret.postgresPassword="$(openssl rand -hex 16)" \
  --set secret.djangoSecretKey="$(openssl rand -hex 32)"

helm test booking -n coworking-booking      # curl /api/health/ з поду в кластері
helm uninstall booking -n coworking-booking
```

Перевірка без кластера:

```bash
helm lint chart/ -f chart/values-dev.yaml
helm template booking chart/ -f chart/values-dev.yaml > /tmp/dev.yaml
helm template booking chart/ -f chart/values-prod.yaml \
  --set secret.postgresPassword=x --set secret.djangoSecretKey=y > /tmp/prod.yaml
diff /tmp/dev.yaml /tmp/prod.yaml
```

### Пріоритет значень

Від нижчого до вищого:
1. `values.yaml` — база;
2. файли з `-f` (кожен наступний перекриває попередній);
3. `--set` — перекриває все.

На нашому чарті:

| Команда | `replicaCount.api` | образ api |
|---|---|---|
| `helm template booking chart/` | `2` (values.yaml) | `1.0.0` (порожній тег → appVersion) |
| `... -f chart/values-dev.yaml` | `1` (dev перекрив базу) | `1.0.0` (dev) |
| `... -f chart/values-dev.yaml --set replicaCount.api=4 --set image.api.tag=1.1.0` | `4` (`--set` перекрив усе) | `1.1.0` |

**Пастка `helm upgrade`.** Без `--reuse-values` Helm 3 бере `values.yaml` +
лише ті `-f`/`--set`, що передані в цій команді. Значення з попереднього
встановлення не зберігаються. Тому для точкової зміни використовується
`--reuse-values`:

```bash
helm upgrade booking chart/ -n coworking-booking --reuse-values --set image.api.tag=1.1.0
```

### Нюанси

- **Пароль БД при upgrade.** Postgres застосовує `POSTGRES_PASSWORD` лише
  при першій ініціалізації тому. Якщо змінити `secret.postgresPassword` на
  наявній БД, api і worker перестануть до неї підключатися. При переході
  dev → prod пароль треба передавати той самий.
- **Розмір PVC.** Стандартний storageclass minikube не вміє розширювати
  томи. Тому `pvc.yaml` через `lookup` зберігає розмір наявного PVC, а
  `postgres.persistence.size` діє лише при першому встановленні.
- **pre-upgrade hook** `<fullname>-db-check` — Job з образом postgres. Він
  виконує `psql ... -c 'select 1'` з паролем із Secret (до 20 спроб по 3 с).
  Якщо БД недоступна, Job падає, і `helm upgrade` переривається до зміни
  об'єктів. На `helm rollback` hook не запускається, бо має лише анотацію
  `pre-upgrade`.
- **helm test** `<fullname>-test-health` — Pod з `curl`. Він звертається до
  `http://<fullname>-api/api/health/` і перевіряє `"status":"ok"`. Успішний
  под видаляється (`hook-succeeded`), упалий лишається для `kubectl logs`.
- **Чому hook + test, а не bitnami/postgresql.** Власний postgres-деплоймент
  займає ~50 рядків і повністю прозорий. Залежність від чужого чарта
  принесла б сотні параметрів, власні імена Secret-ів і сервісів та
  залежність від зовнішнього репозиторію і його політики образів. Для
  навчального застосунку з одним інстансом БД це надмірно.
