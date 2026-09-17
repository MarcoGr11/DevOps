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
| GET | `/api/health/` | health-check |
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
