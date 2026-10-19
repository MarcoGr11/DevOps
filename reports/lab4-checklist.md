# Лабораторна №4 — чекліст скриншотів

Скриншоти класти в `reports/screens/` під точно такими іменами, як у
заголовках `###`. Скрипт `reports/build_report.py` бере звідти PNG і
вставляє їх у звіт у тому ж порядку, що й тут.

Усі команди запускаються з кореня репозиторію.

**Перед початком (обов'язково):** лаба №3 має бути прибрана, бо реліз
ставиться в той самий namespace `coworking-booking`.

```bash
minikube status
kubectl get namespace coworking-booking     # має бути NotFound
# якщо namespace є:
kubectl delete namespace coworking-booking
kubectl wait --for=delete namespace/coworking-booking --timeout=300s

# ОКРЕМИЙ термінал №2, лишити працювати до кінця лаби:
kubectl port-forward -n ingress-nginx svc/ingress-nginx-controller 8081:80
```

> Паролі в кадр не потрапляють: у `values.yaml` dev-заглушки маскуються
> через `sed`, у diff рядки Secret відфільтровано, а на prod-upgrade паролі
> передаються через `$(kubectl get secret ...)`, тож у терміналі видно лише
> саму підстановку. Після prod-upgrade НЕ запускати `helm get values` і
> `helm get manifest` — там будуть секрети.

---

## Пункти 1–2. Helm і Chart.yaml

### 4-01-helm-version.png — Версія Helm

**Що робилось:** Перевірили, що Helm 3 встановлений.

**Команди:**
```bash
helm version
```

**Пояснення:** Встановлено Helm v3. Helm 3 працює без серверного
компонента (Tiller): він звертається до Kubernetes API тими самими
правами, що й kubectl.

### 4-02-chart-yaml.png — Chart.yaml

**Що робилось:** Подивились паспорт чарта.

**Команди:**
```bash
cat chart/Chart.yaml
```

**Пояснення:** `name: booking` — ім'я чарта. `version: 0.1.0` — версія
самого чарта (шаблонів і структури values); її підвищують, коли змінюють
чарт. `appVersion: "1.0.0"` — версія застосунку, тобто образів api і
worker; вона використовується як тег за замовчуванням, якщо тег не задано
у values. Ці дві версії незалежні: можна випустити новий чарт для старої
програми і навпаки.

## Пункти 3–5. Структура чарта, values, helpers, NOTES

### 4-03-chart-tree.png — Структура chart/

**Що робилось:** Показали, з яких файлів складається чарт.

**Команди:**
```bash
find chart -type f ! -name DEMO.md | sort
```

**Пояснення:** `Chart.yaml` — опис чарта; `values.yaml` — значення за
замовчуванням; `values-dev.yaml` і `values-prod.yaml` — значення для
середовищ; у `templates/` — шаблони тих самих об'єктів, що в лабі №3, плюс
`_helpers.tpl` (спільні функції), `NOTES.txt` (підказка після
встановлення), hook `hook-db-check.yaml` і тест `tests/test-health.yaml`.

### 4-04-values.png — values.yaml

**Що робилось:** Показали значення за замовчуванням (паролі замасковано).

**Команди:**
```bash
sed -E 's/(postgresPassword|djangoSecretKey): .*/\1: ********/' chart/values.yaml
```

**Пояснення:** Усе, що в лабі №3 було «зашито» в YAML (образи і теги,
кількість реплік, ресурси, налаштування ConfigMap, Ingress-хост), тепер
винесено в змінні. Порожній `tag` означає «брати appVersion».

### 4-05a-helpers.png — _helpers.tpl

**Що робилось:** Показали шаблони-функції, які використовують усі
маніфести.

**Команди:**
```bash
cat chart/templates/_helpers.tpl
```

**Пояснення:** `booking.fullname` будує імена об'єктів із назви релізу
(`booking-api`), тому два релізи в одному namespace не конфліктують.
`booking.labels` і `booking.selectorLabels` дають стандартні мітки
`app.kubernetes.io/*`. `booking.image` складає `repository:tag` з
підстановкою appVersion.

### 4-05b-notes.png — NOTES.txt

**Що робилось:** Показали шаблон повідомлення, яке Helm друкує після
встановлення.

**Команди:**
```bash
cat chart/templates/NOTES.txt
```

**Пояснення:** Після `helm install` користувач бачить, який образ
встановлено, як дочекатись подів, як відкрити застосунок через Ingress
або port-forward і як запустити `helm test`. Значення підставляються з
релізу.

## Пункт 6. Середовища dev і prod

### 4-06a-values-dev-prod.png — values-dev і values-prod

**Що робилось:** Порівняли файли значень для двох середовищ.

**Команди:**
```bash
cat chart/values-dev.yaml
cat chart/values-prod.yaml
```

**Пояснення:** dev — по 1 репліці, малі ресурси, DEBUG увімкнено, хост
`dev.booking.local`, образи 1.0.0. prod — 3 репліки api і 2 worker,
більші ресурси, DEBUG вимкнено, хост `booking.example.com`, образи 1.1.0.
Паролі в prod порожні: їх передають під час встановлення.

### 4-06b-template-diff.png — Різниця рендеру без встановлення

**Що робилось:** Згенерували маніфести для обох середовищ командою
`helm template` (нічого не встановлюючи) і порівняли.

**Команди:**
```bash
helm template booking chart/ -f chart/values-dev.yaml > /tmp/dev.yaml
helm template booking chart/ -f chart/values-prod.yaml --set secret.postgresPassword=x --set secret.djangoSecretKey=y > /tmp/prod.yaml
diff /tmp/dev.yaml /tmp/prod.yaml | grep -v -E "POSTGRES_PASSWORD|DJANGO_SECRET_KEY"
```

**Пояснення:** Один і той самий чарт дає різні маніфести: відрізняються
`replicas`, `image`, `resources`, `DJANGO_DEBUG`, інтервал worker, розмір
PVC і хост Ingress. `checksum/config` і `checksum/secret` — хеші ConfigMap
і Secret: коли вони змінюються, поди перезапускаються з новими змінними.

### 4-06c-priority.png — Пріоритет values < -f < --set

**Що робилось:** Показали, яке значення перемагає, якщо його задано в
кількох місцях.

**Команди:**
```bash
helm template booking chart/ -s templates/deployment-api.yaml | grep -E "^  replicas:|image:"
helm template booking chart/ -s templates/deployment-api.yaml -f chart/values-dev.yaml | grep -E "^  replicas:|image:"
helm template booking chart/ -s templates/deployment-api.yaml -f chart/values-dev.yaml --set replicaCount.api=4 --set image.api.tag=1.1.0 | grep -E "^  replicas:|image:"
```

**Пояснення:** Лише `values.yaml` → 2 репліки. Додали `-f values-dev.yaml`
→ 1 репліка (файл перекрив значення за замовчуванням). Додали `--set` →
4 репліки і тег 1.1.0 (`--set` має найвищий пріоритет).

## Пункт 7. Встановлення релізу

### 4-07a-lint.png — helm lint

**Що робилось:** Перевірили чарт на помилки перед встановленням.

**Команди:**
```bash
helm lint chart/ -f chart/values-dev.yaml
helm lint chart/ -f chart/values-prod.yaml --set secret.postgresPassword=x --set secret.djangoSecretKey=y
```

**Пояснення:** `0 chart(s) failed` — чарт коректний для обох середовищ.
`[INFO] icon is recommended` — лише порада, не помилка.

### 4-07b-install.png — helm install

**Що робилось:** Встановили реліз `booking` з dev-значеннями.

**Команди:**
```bash
helm install booking chart/ -f chart/values-dev.yaml -n coworking-booking --create-namespace
kubectl rollout status deployment/booking-api -n coworking-booking --timeout=180s
kubectl get pods,svc,ingress,pvc,configmap,secret -n coworking-booking
```

**Пояснення:** `STATUS: deployed`, `REVISION: 1`, нижче надруковано
NOTES. Створено той самий набір об'єктів, що в лабі №3, але з префіксом
релізу (`booking-api`), а Secret тепер теж іде з чарта.

### 4-07c-list-status.png — helm list, status, get values

**Що робилось:** Подивились стан релізу і значення, з якими його
встановлено.

**Команди:**
```bash
helm list -n coworking-booking
helm status booking -n coworking-booking | head -6
helm get values booking -n coworking-booking
curl -s -H "Host: dev.booking.local" http://localhost:8081/api/health/; echo
```

**Пояснення:** Реліз `booking`, ревізія 1, чарт `booking-0.1.0`.
`helm get values` показує лише значення, передані користувачем (вміст
`values-dev.yaml`), а не весь `values.yaml`. Застосунок відповідає через
Ingress з хостом `dev.booking.local`, версія 1.0.0.

### 4-07d-helm-storage.png — Де Helm зберігає стан

**Що робилось:** Знайшли, де Helm тримає інформацію про реліз.

**Команди:**
```bash
kubectl get secrets -n coworking-booking | grep helm
kubectl get secret sh.helm.release.v1.booking.v1 -n coworking-booking -o jsonpath='{.metadata.labels}'; echo
```

**Пояснення:** Helm 3 зберігає кожну ревізію релізу як Secret типу
`helm.sh/release.v1` у namespace релізу. Мітки показують назву релізу,
номер ревізії і статус. Саме з цих Secret працюють `helm history` і
`helm rollback`.

## Пункт 8. Оновлення, історія, відкат, видалення

### 4-08a-upgrade-set.png — upgrade через --set

**Що робилось:** Оновили тільки тег образу api, решту значень лишили як є.

**Команди:**
```bash
helm upgrade booking chart/ -n coworking-booking --reuse-values --set image.api.tag=1.1.0 | head -6
kubectl rollout status deployment/booking-api -n coworking-booking
kubectl get deploy -n coworking-booking -o custom-columns=NAME:.metadata.name,REPLICAS:.spec.replicas,IMAGE:.spec.template.spec.containers[0].image
sleep 10; curl -s -H "Host: dev.booking.local" http://localhost:8081/api/health/; echo
```

**Пояснення:** Ревізія 2. Змінився лише образ api (1.1.0), worker
лишився 1.0.0, реплік так само 1 — `--reuse-values` зберіг dev-значення.
Застосунок відповідає `"version":"1.1.0"`.

### 4-08b-upgrade-prod.png — upgrade з values-prod

**Що робилось:** Перевели реліз на prod-значення. Пароль БД передали той
самий, що вже в Secret, бо postgres встановлює пароль лише при першому
запуску.

**Команди:**
```bash
helm upgrade booking chart/ -n coworking-booking -f chart/values-prod.yaml \
  --set secret.postgresPassword="$(kubectl get secret booking-secret -n coworking-booking -o jsonpath={.data.POSTGRES_PASSWORD} | base64 -d)" \
  --set secret.djangoSecretKey="$(kubectl get secret booking-secret -n coworking-booking -o jsonpath={.data.DJANGO_SECRET_KEY} | base64 -d)" | head -6
kubectl rollout status deployment/booking-api -n coworking-booking --timeout=300s
kubectl get deploy -n coworking-booking -o custom-columns=NAME:.metadata.name,REPLICAS:.spec.replicas,IMAGE:.spec.template.spec.containers[0].image,CPU_REQ:.spec.template.spec.containers[0].resources.requests.cpu
kubectl get pvc,ingress -n coworking-booking
for i in 1 2 3 4 5 6; do curl -s -H "Host: booking.example.com" http://localhost:8081/api/health/; echo; done
```

**Пояснення:** Ревізія 3. api — 3 репліки, worker — 2, обидва образи
1.1.0, більші ресурси, Ingress на `booking.example.com`. Запити
розподіляються між трьома подами. PVC лишився 1Gi: шаблон `pvc.yaml`
зберігає розмір наявного тому, бо storageclass minikube не вміє його
збільшувати.

### 4-08c-history.png — helm history

**Що робилось:** Подивились історію ревізій релізу.

**Команди:**
```bash
helm history booking -n coworking-booking
```

**Пояснення:** Три ревізії: 1 — install, 2 і 3 — upgrade. Актуальна
ревізія має статус `deployed`, попередні — `superseded`.

### 4-08d-rollback.png — helm rollback

**Що робилось:** Відкотили реліз на ревізію 2 (dev, api 1.1.0).

**Команди:**
```bash
helm rollback booking 2 -n coworking-booking
helm history booking -n coworking-booking
kubectl get deploy -n coworking-booking -o custom-columns=NAME:.metadata.name,REPLICAS:.spec.replicas,IMAGE:.spec.template.spec.containers[0].image
kubectl get ingress -n coworking-booking
```

**Пояснення:** З'явилась нова ревізія 4 з описом `Rollback to 2`: історія
не переписується, відкат — це теж ревізія. Повернулись значення ревізії 2:
по 1 репліці, api 1.1.0, worker 1.0.0, хост `dev.booking.local`.

> **Далі виконати пункт 9 (hook і test), поки реліз ще встановлений, і
> тільки потім — 4-08e (uninstall).**

### 4-08e-uninstall.png — helm uninstall і порожній namespace

**Що робилось:** Видалили реліз і перевірили, що після нього нічого не
лишилось.

**Команди:**
```bash
helm uninstall booking -n coworking-booking
sleep 15
kubectl get all -n coworking-booking
kubectl get configmap,secret,pvc,ingress,jobs -n coworking-booking
kubectl get secrets -n coworking-booking | grep helm
helm list -n coworking-booking
```

**Пояснення:** Одна команда прибрала всі об'єкти релізу, включно з PVC і
Secret-ами історії Helm. `helm list` порожній. Лишається тільки
`kube-root-ca.crt` — його Kubernetes сам створює в кожному namespace.

## Пункт 9. Hook і helm test

### 4-09a-hook.png — pre-upgrade hook

**Що робилось:** Показали hook, який перед кожним upgrade перевіряє, що БД
приймає підключення, і події його запусків.

**Команди:**
```bash
sed -n '1,14p' chart/templates/hook-db-check.yaml
kubectl get events -n coworking-booking --field-selector involvedObject.kind=Job --sort-by=.lastTimestamp
```

**Пояснення:** Анотація `helm.sh/hook: pre-upgrade` означає, що Job
запускається перед кожним upgrade; якщо БД недоступна, upgrade
скасовується. `hook-delete-policy: hook-succeeded` прибирає успішний Job,
тому лишаються лише події: по одному `Created pod` + `Completed` на кожен
upgrade (ревізії 2 і 3). На rollback цей hook не запускається.

### 4-09b-helm-test.png — helm test

**Що робилось:** Запустили вбудований у чарт smoke-тест.

**Команди:**
```bash
helm test booking -n coworking-booking
```

**Пояснення:** Helm створив тестовий под (`booking-test-health`), який
робить запит на `/api/health/` через Service і перевіряє
`"status":"ok"`. `Phase: Succeeded` — тест пройдено.

---

## Після лаби

```bash
# зупинити port-forward у терміналі №2 (Ctrl+C)
kubectl delete namespace coworking-booking
kubectl wait --for=delete namespace/coworking-booking --timeout=300s
```
