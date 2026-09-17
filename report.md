# Звіт: що зроблено в проєкті

У цій розмові я ще нічого не робив — репозиторій уже містить готовий проєкт з одним коммітом (`56b2770`), зробленим до цієї розмови. Нижче повний звіт по тому, що в ньому реалізовано.

## Що зроблено (за коммітом "Lab 1: coworking booking system")

**Суть:** система бронювання коворкінг-ресурсів (кімнати/столи) на часові слоти, Django REST Framework API + окремий worker-сервіс, усе в Docker Compose.

### api/ — Django REST Framework сервіс
- `booking/models.py` — моделі ресурсів і бронювань (статуси pending/confirmed/cancelled)
- `booking/serializers.py` — валідація на рівні серіалізатора, що блокує подвійне бронювання активного слоту
- `booking/views.py`, `urls.py` — REST endpoints
- `booking/migrations/` — дві міграції (початкова + зміна `options` моделі Resource)
- `booking/tests/` — тести моделей, серіалізаторів і API (`test_models.py`, `test_serializers.py`, `test_api.py`)
- `config/` — Django settings, urls, wsgi
- `Dockerfile`, `.dockerignore`, `requirements.txt`

### worker/ — окремий Python-сервіс
- `worker.py` — опитує PostgreSQL і автоматично скасовує pending-бронювання, що прострочили таймаут, звільняючи слот
- `tests/test_worker.py` — тест логіки воркера
- `Dockerfile`, `.dockerignore`, `requirements.txt`

### Інфраструктура
- `docker-compose.yml` — три сервіси: `postgres`, `api`, `worker`
- `README.md` — опис проєкту (181 рядок)
- `.gitignore`

## Підсумок
29 файлів, 985 рядків коду, статус git — чистий (усе закомічено, нових змін немає).

---

# Перевірка запуску проєкту (docker compose)

## 1. `docker compose up --build`
Усі сервіси зібрались і піднялись без помилок:
- `db` (postgres:16-alpine) — Healthy
- `api` (gunicorn на 0.0.0.0:8000) — Up, міграції застосовані
- `worker` — Up, лог: `worker started: interval=60s timeout=15min`

## 2. Curl-сценарій Resource → Slot → Booking
| Крок | Запит | Результат |
|---|---|---|
| Health | `GET /api/resources/` | `200` |
| Create Resource | `POST /api/resources/` `{"name":"Room A","resource_type":"room","capacity":4}` | `201`, `id=2` |
| Create Slot | `POST /api/slots/` `{"resource":2,"start_time":"2026-09-20T10:00:00Z","end_time":"2026-09-20T11:00:00Z"}` | `201`, `id=2`, `is_available: true` |
| Create Booking (перше) | `POST /api/bookings/` `{"slot":2,"customer_name":"Bohdan",...}` | `201`, `status: pending` |
| Create Booking (повторно, той самий slot) | `POST /api/bookings/` `{"slot":2,...}` | **`400`**, `{"slot":["This slot already has an active booking (pending or confirmed)."]}` |

Захист від подвійного бронювання на рівні серіалізатора працює коректно.

## 3. Тести
- **API (у контейнері)**: `docker compose exec api python manage.py test` → **19/19 тестів пройшли (OK)**
- **Worker (локально)**: `python -m unittest discover -s tests` → **2/2 тестів пройшли (OK)** (worker використовує stdlib `unittest`, pytest не потрібен)

## 4. Підсумок
**Усе працює без проблем.** Сервіси піднімаються чисто, API-flow Resource→Slot→Booking коректний, подвійне бронювання правильно відхиляється з `400`, усі 21 тест (19 api + 2 worker) зелені.
