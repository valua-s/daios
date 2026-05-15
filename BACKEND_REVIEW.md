# Backend Review — DAIOS

Послойный аудит бэкенда на соответствие Clean Architecture / DDD / SOLID / DRY,
с проверкой импортов, циклических зависимостей и стоимости запросов.

Легенда:
- 🔴 critical — нарушает архитектуру или ломает прод
- 🟠 major — серьёзный долг
- 🟡 minor — улучшение/гигиена
- 🟢 ok — отмечено как корректное

---

## План итераций

1. **Core** — config, db, redis, minio_client, providers (инфраструктура)
2. **Models** — SQLAlchemy ORM, домен
3. **Repositories** — доступ к данным
4. **Services** — прикладная логика
5. **Agents** — оркестрация и domain services
6. **Integrations** — внешние API клиенты
7. **API** — Litestar контроллеры
8. **Auth module** — вертикальный модуль
9. **Scheduler** — APScheduler jobs
10. **Bot** — Telegram bot (отдельный entry)
11. **Composition root** — `__main__.py`, `providers.py`

---

## Итерация 1 — Core (`backend/core/`)

Файлы: `config.py`, `db.py`, `redis.py`, `minio_client.py`, `providers.py`.

### Архитектура слоя

🟢 Каркас в целом верный: `config` — конфиг, `db/redis/minio_client` — фабрики ресурсов, `providers.py` — Dishka DI как composition root для бизнес-слоёв.

🟠 **Нарушение Clean Architecture / DIP в `providers.py`.** Файл лежит в `core/`, но импортирует **все** верхние слои: `agents/*`, `auth/service/*`, `integrations/*`, `repositories/*`, `services/*`. Получается, что нижний слой (`core`) знает о верхних — это «инверсия зависимостей наоборот». Это конкретный composition root, не «инфраструктура».
- *Fix:* перенести `providers.py` в отдельный модуль `backend/composition/` (или `backend/bootstrap/`), а `core/` оставить только с примитивами (settings + фабрики ресурсов). Это уберёт неявную цикличность через `core`.

🟠 **`core/` импортируется снизу — но при текущей структуре `providers.py` сам потянет за собой всё дерево.** Любой импорт `from backend.core.providers import ...` тянет 30+ модулей. На юнит-тестах это даст и тормоза, и кучу обязательных env-переменных.

### `config.py`

🟠 **Module-level singleton `settings = Settings()` на строке 137.** При `from backend.core.config import settings` Pydantic сразу читает `.env`, и если нет `postgres_password`/`redis_password`/`jwt_secret_key`/`admin_*`/`google_sheets_workout_id`/`bus_schedule_url`/`openweather_api_key`/`openai_api_key`/`telegram_*` — `ImportError` поднимется на этапе импорта в любом тесте/скрипте.
- *Fix:* функция `get_settings()` с `@lru_cache`, либо инициализация только в composition root и проброс через DI. В Dishka уже есть `@provide get_settings`, так что прямой импорт `settings` нужно искоренить.

🟡 `allow_origins`: при `is_production=False` возвращает `["*"]` — в новых браузерах с `credentials` это сломается; но для dev ок.

🟡 `allows_ips: list[AnyHttpUrl]` — название во множественном числе через `s` (вместо `allowed_ips`). Гигиена.

🟡 `model_orchestrator`, `model_agents`, `model_summary` — одинаковая строка по умолчанию, повторение. Должно быть одно «default model» и спец-оверрайды (либо словарь `models: dict[str, str]`).

### `db.py`

🟠 **Нет настроек пула.** `pool_size`, `max_overflow`, `pool_recycle` — на дефолтах SQLAlchemy (5/10/-1). Для APScheduler + uvicorn + бот это может стать узким местом. Вынести в `settings` (`db_pool_size`, `db_max_overflow`) и проставить `pool_recycle=1800` для долгих соединений к Postgres.

🟠 `engine` и `AsyncSessionFactory` — module-level. Создаются на импорт. Это значит, что любой импорт `backend.core.db` сразу открывает пул, даже если код не использует БД (например, скрипты, тесты).
- *Fix:* лениво в Dishka-провайдере, как уже сделано с `redis` (factory).

### `redis.py`


🟡 Нет `socket_timeout`/`socket_connect_timeout`/`health_check_interval` — на проде висящий Redis потенциально подвиснет все хэндлеры.

### `minio_client.py`

🔴 **`make_bucket(bucket)` закомментирован, вместо этого `logger.error("Bucket not exists")`** (строка 23-24). Старт приложения проходит, но загрузки/чтения в Minio будут падать. Молчаливая поломка.
- *Fix:* либо `minio_client.make_bucket(bucket)`, либо честный `raise RuntimeError(...)`.

🟠 **`minio_client = Minio(...)` на module-level (строка 11).** Та же проблема, что и с `db.engine` — выполняется на импорт, требует env. Завернуть в фабрику и провайдер.

🟠 **Sync SDK в async-приложении.** `ensure_bucket` вызывается из `_main` (async) — `bucket_exists` блокирует event loop. Сейчас не критично (один раз на старте), но если будут вызовы из хэндлеров — обернуть в `asyncio.to_thread` или взять `aioboto3`.


### `providers.py`

🟠 См. выше — лежит не в том слое.

🟠 **`get_settings` (строка 44) возвращает module-level `settings`.** Это значит, что DI-провайдер на самом деле не контролирует жизненный цикл — `Settings()` уже был создан на импорте. Сделать `return Settings()` (и убрать импорт `settings`).

🟠 **`get_redis` (строка 48) — APP-scope, но возвращает `Redis()` без `await client.aclose()`** при завершении. Утечка соединений на shutdown. Сделать `AsyncIterator[Redis]` с `try/finally`.

🟠 **`get_http_client` (строка 52) — один на всё приложение, APP-scope.** Это правильно для пула, но `httpx.AsyncClient(timeout=30.0)` — общий timeout 30 сек на каждый запрос; для медленных RSS/новостей это ок, а для критических ручек хочется отдельных клиентов с разными timeout. Не баг, но дизайнерское решение зафиксировать.

🟠 **`get_session` (строка 92) делает `await session.commit()` после `yield`** — это автокоммит на каждый HTTP-запрос. Удобно, но скрытно: сервисы и репозитории не вызывают commit явно, и тестировать транзакционные сценарии тяжело. По DDD коммит должен делать application service (Unit of Work). Документировать как осознанный выбор либо переписать через UoW.

🟠 **`SettingsService` принимает `redis: Redis`, всё остальное — `session`-only.** Сейчас не баг, но `SettingsService` отвечает и за БД, и за кэш — отдельная итерация это разберёт.

🟡 **DRY: 11 однострочных `@provide` для репозиториев/сервисов**, каждый `def get_X(self, session) -> X: return X(session)`. У Dishka есть `provide(X, scope=Scope.REQUEST)` — короче. Сократит файл вдвое.

🟡 **Длина файла 219 строк, 11 импортов из `services/`, 6 из `agents/`, 8 из `integrations/`** — становится «god module». При вынесении в `composition/` стоит разбить на под-провайдеры: `RepoProvider`, `ServiceProvider`, `AgentProvider`, `IntegrationProvider`.

### Импорты / цикличность

Зависимости `core/`:
- `config.py` — без внутренних импортов ✅
- `db.py` → `core/config` ✅
- `redis.py` → `core/config` ✅
- `minio_client.py` → `core/config` ✅
- `providers.py` → `core/{config,db,redis}` + `agents/*` + `services/*` + `repositories/*` + `integrations/*` + `auth/service/*`

🟠 **Потенциальная цикличность через `providers.py`.** Сейчас её нет, потому что верхние слои не импортируют `core/providers`. Но это хрупко — `providers.py` должен жить в отдельном модуле выше core.

### Перформанс

- 🟠 нет настроек пула БД (см. `db.py`)
- 🟡 нет таймаутов/health-check у Redis
- 🟠 синхронный Minio SDK в async-приложении
- 🟡 один общий `httpx.AsyncClient` — без отдельных таймаутов на критичные ручки

### План фиксов для Core (приоритет)

1. 🔴 **`ensure_bucket`** — раскомментировать `make_bucket` или явно `raise`.
2. 🟠 **`settings`-singleton** — `@lru_cache`-фабрика, искоренить прямые импорты `settings`.
3. 🟠 **Перенос `providers.py`** в `backend/composition/` и разбиение на под-провайдеры.
4. 🟠 **`engine`/`AsyncSessionFactory`/`minio_client`** — ленивые фабрики через DI.
5. 🟠 **`get_redis`** — `AsyncIterator` с `aclose` на shutdown.
6. 🟠 **Пул БД** — `pool_size`, `max_overflow`, `pool_recycle` из конфига.
7. 🟠 **Убрать поле `docker`** из `Settings`, использовать env-vars напрямую.
8. 🟡 DRY в `database_url`/`local_database_url`, в module-defaults для трёх моделей LLM.
9. 🟡 Redis timeouts/health-check.
10. 🟡 Очистить region/комменты в `minio_client.py`.

---

## Итерация 2 — Models (`backend/models/`)

Файлы: `base.py`, `task.py`, `backlog.py`, `focus.py`, `note.py`, `schedule.py`, `settings.py`, `content.py`, `workout_cache.py`, `__init__.py`.
(Также `backend/auth/models/user.py` — формально другой модуль, разобран в Итерации 8, но влияет на агрегат через `models/__init__.py`.)

### Архитектура слоя / DDD

🟠 **Анемичная доменная модель.** Все классы — это голые SQLAlchemy-таблицы без поведения, инвариантов и фабрик. С точки зрения DDD это не сущности и не агрегаты, а DAO/persistence-модель. Сейчас «домен» в проекте отсутствует — вся логика размазана по сервисам и агентам.
- *Решение по выбору архитектуры:* либо
  - (а) принять, что проект CRUD-ориентирован, и переименовать `models/` → `db/` (это будут persistence-модели), а сервисы оставить как application layer — это честнее и устраняет претензию к DDD;
  - (б) ввести отдельный domain-слой (dataclass-сущности + value objects + правила) и маппер на ORM. На текущем размере проекта (а) — реалистичнее, (б) — оверинжиниринг.

🟠 **Нет логического разделения по агрегатам.** Связь `Note ↔ NoteItem` — единственный пример агрегата, остальные модели «плоские». При этом каскад на удаление настроен и на ORM-уровне (`cascade="all, delete-orphan"`), и на БД (`ondelete="CASCADE"`) — хорошо, но `passive_deletes=True` для relationship не выставлено, поэтому SQLAlchemy всё равно может делать дополнительные SELECT'ы перед удалением. См. перформанс.

🟠 **`UserSetting` как key-value store** (строки 18-22 в `settings.py`) — антипаттерн: типы значений теряются, нет валидации, ключи перечислены в комментариях. Сложно держать инварианты («интерес — boolean», «pace — float»). Для долгосрочной поддержки — заменить на типизированные таблицы (например, `user_interests`, `workout_profile`).

### Base / общая часть

🟡 `Base` не задаёт `MetaData`-namingconvention. У Alembic при автогенерации миграций имена индексов/констрейнтов будут случайные — рано или поздно появятся конфликтные миграции. Добавить:
```python
naming_convention = {
  "ix": "ix_%(table_name)s_%(column_0_name)s",
  "uq": "uq_%(table_name)s_%(column_0_name)s",
  "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
  "pk": "pk_%(table_name)s",
  "ck": "ck_%(table_name)s_%(constraint_name)s",
}
metadata = MetaData(naming_convention=naming_convention)
```

🟡 `created_at` / `updated_at` — `Mapped[datetime]`, но без `timezone=True`. Postgres хранит `TIMESTAMP WITHOUT TIME ZONE`. При работе с `app_timezone=Europe/Moscow` это даст путаницу UTC/local. Перейти на `DateTime(timezone=True)` и хранить UTC.

🟡 `Mapped[datetime]` без явного типа — SQLAlchemy сам подставит `DateTime`. Для прозрачности лучше явно `mapped_column(DateTime(timezone=True), ...)`.

🟠 **DRY:** колонки `created_at/updated_at` определены в `Base`, и **унаследованы во все модели — включая `UserSetting` с PK по `key` и `WorkoutCache`**, где они логически не нужны (только `fetched_at`). Это ок (накладные расходы малы), но вынесите в **mixin** `TimestampMixin`, а `Base` оставьте минимальным. Это даст возможность сделать «таблицу без timestamps» там, где они мешают.

### `task.py`

🟢 enum-ы `TaskStatus`/`TaskPriority` через `str, enum.Enum` — корректно (хорошая сериализация).

🟠 **Колонка БД называется `date` (см. `mapped_column("date", sa.Date, ...)` строка 36),** а атрибут — `scheduled_date`. Это создаёт две проблемы:
1. Импорт `from datetime import date` в этом же файле и колонка с именем `date` в БД — ловушка для будущей правки (легко натолкнуться на `Task.date` через `__table__.c.date`).
2. Любые сырые SQL-запросы должны помнить про переименование. Алиас стоит того только если у вас уже была миграция; иначе лучше выровнять имена через миграцию.

🟠 Нет уникального констрейнта/композитного индекса по `(scheduled_date, title)` или хотя бы индекса по `(scheduled_date, status)` — а сервисы фильтруют по «сегодня + статус». См. репозитории, но фундамент закладывается здесь.

🟡 Поле `source: Mapped[str | None] = mapped_column(Text)` — без enum, хотя в комменте перечислены три значения. Использовать `Enum(...)` или хотя бы `CheckConstraint`.

🟡 Нет `__repr__` ни на одной модели — для отладки/логов полезно.

### `backlog.py`

🟢 Минимально и адекватно.

🟡 Нет ссылки на `Task` (если из бэклога создаётся задача — нет трассировки). Если функционально нужно — добавить `created_task_id` FK.

### `focus.py`

🟢 enum `FocusPeriod`, `period_key: index=True` — корректно.

🟠 **Нет уникального констрейнта `(period, period_key)` или `(period, period_key, is_active)`.** «Активный фокус недели» по факту должен быть единственным. Иначе можно вставить два активных фокуса на одну неделю — гонки и неконсистентность на UI.
- *Fix:* `UniqueConstraint("period", "period_key", name="uq_focus_period_key")` + (если нужно) `Index(... where is_active = true)` через partial unique.

### `note.py`

🟢 Агрегат `Note → NoteItem`, каскад на двух уровнях, `order_by` в relationship.

🟠 **N+1 риск:** `items` — это lazy='select' по умолчанию. Любой `note.items` в API триггерит дополнительный запрос. См. репозитории — там должно быть `selectinload(Note.items)` или `lazy="selectin"` прямо в `relationship`.

🟡 `passive_deletes=True` не выставлен на `relationship("items", ...)` — при delete SQLAlchemy сделает SELECT на детях. Поскольку `ondelete="CASCADE"` уже стоит на FK, эффективнее доверить удаление БД: `passive_deletes=True`.

🟡 На `NoteItem` нет уникальности `(note_id, sort_order)` — при ручной правке `sort_order` могут быть дубли.

### `schedule.py`

🟢 `event_name unique`, `cron_expr`, опциональный weekend.

🟠 Тип `cron_expr: Text` без валидации формата на уровне домена/сервиса — ошибочный cron упадёт только в момент регистрации job. См. сервис-слой.

🟡 `event_name` — голая строка. Логичнее `Enum(EventName)` или хотя бы константы; иначе опечатка в одном месте — и job не зарегистрируется. Сервис должен валидировать.

### `settings.py` (UserSetting)

🟠 PK по `key: Text` — для очень частых лукапов это нормально (key — uniq и так), но Postgres любит integer PK, плюс это «семантический PK», который изменить нельзя. Лучше отдельный `id` + `key UNIQUE`.

🟠 См. выше: ключевой антипаттерн «таблица настроек как dict». Хорошо для прототипа, плохо для долгой жизни.

### `content.py`

🟢 Два enum-а, индекс по `topic` и `status` — корректно.

🟠 **Запросы к ленте фильтруют по `status` + `topic` + сортируют по `shown_at`/`created_at`**, а индекса по `(status, topic)` или составному нет — будут seq-сканы при росте таблицы. См. репозитории/сервисы.

🟡 `topic: Text` (строка 32) — захардкоженные значения в комменте (`python | ai | running | economics`). Те же claims что и про `source` в Task. Хороший кандидат на отдельную таблицу `topics` или Enum.

🟡 `url` — `unique=True` без `index=True` (uniq автоматически создаёт индекс — ок). Но `Text` для URL: длина не ограничена, индекс может расти. Для Postgres это не критично (TOAST), но `String(2048)` + uniq был бы безопаснее.

🟡 `duration_minutes: Mapped[int | None] = mapped_column()` — без типа. SQLAlchemy подставит `INTEGER`, ок, но явный `Integer` улучшает читаемость.

🟡 `shown_at: DateTime` без timezone — то же замечание про TZ.

### `workout_cache.py`

🟢 Один тип кэша на дату, `unique=True` на `workout_date`.

🟠 **`data_json: Text` вместо `JSONB`.** Postgres умеет JSONB, индексирует, валидирует, фильтрует — а сейчас всё парсится в Python. Заменить на `JSONB` (`from sqlalchemy.dialects.postgresql import JSONB`).

🟡 `fetched_at: DateTime` — без `timezone=True`, без `server_default=now()`.

🟡 Алиас колонки `date` (через `mapped_column("date", ...)`) — то же, что в `Task`.

### `__init__.py`

🟢 Импорт всех моделей нужен Alembic'у — корректно. Комментарий это объясняет.

🟠 **Этот файл импортирует `backend.auth.models.user.User`** (строка 4). Сейчас `auth/` — отдельный «вертикальный модуль», но его модель привязана к общему `Base` и регистрируется здесь. Это **скрытая связь**: `models/` знает про `auth/`. Если хотите по-настоящему модульный `auth`, у него должна быть своя `metadata`/своя миграционная стрелка, либо нейтральный `models/user.py`. Архитектурное противоречие, но прагматично работает.

### Импорты / цикличность

- Все модели → только `backend.models.base`. ✅
- `models/__init__.py` → `auth.models.user`. Однонаправленная связь.
- `auth.models.user` → `backend.models.base`. ✅ Цикличности нет.
- Внешние слои импортируют модели свободно — ожидаемо.

### Перформанс — выводы для слоя

- 🟠 Отсутствуют составные индексы: `(scheduled_date, status)` для `tasks`, `(status, topic)`/`(status, shown_at)` для `content_items`.
- 🟠 `data_json: Text` в `workout_cache` — нужен JSONB.
- 🟠 `Note.items` без `lazy="selectin"`/`passive_deletes=True` — потенциальные N+1 и лишние SELECT при delete.
- 🟡 Нет `MetaData(naming_convention=...)` → миграции будут давать имена-сюрпризы.
- 🟡 Все таблицы наследуют `created_at`/`updated_at`, в части моделей это лишний overhead (минимальный).

### План фиксов для Models (приоритет)

1. 🟠 Решить: persistence-модели vs. честный domain layer. На MVP — оставить как есть, но переименовать модули мысленно как DAO.
2. 🟠 Уникальный констрейнт `(period, period_key)` (+ partial unique по `is_active`) на `Focus`.
3. 🟠 Композитный индекс `(scheduled_date, status)` на `tasks`; `(status, topic)` / `(status, shown_at desc)` на `content_items`.
4. 🟠 `workout_cache.data_json` → `JSONB`.
5. 🟠 `Note.items`: `lazy="selectin"`, `passive_deletes=True`.
6. 🟠 `Base.metadata = MetaData(naming_convention=...)`.
7. 🟠 Все `datetime`-колонки → `DateTime(timezone=True)`, хранить UTC.
8. 🟠 `UserSetting`: добавить integer `id`, рассмотреть переезд на типизированные таблицы.
9. 🟡 Enum для `Task.source`, `ContentItem.topic`, `Schedule.event_name`.
10. 🟡 Выровнять имя колонки `date` ↔ атрибут `scheduled_date` / `workout_date` через миграцию.
11. 🟡 Вынести timestamps в `TimestampMixin`.
12. 🟡 `Note.id` `__repr__`, `String(2048)` для url и т.п.

---

## Итерация 3 — Repositories (`backend/repositories/`)

Файлы: `base.py`, `task_repo.py`, `backlog_repo.py`, `focus_repo.py`, `note_repo.py`, `content_repo.py`, `settings_repo.py`.
(`auth/repos/*` — отдельно в Итерации 8.)

### Архитектура слоя / DDD

🟠 **Repository pattern реализован как «обёртка над сессией», без абстракции.** Сервисы зависят от **конкретных** классов (`TaskRepository`, ...), а не от интерфейсов / protocol-ов. Это нарушает DIP: верхний слой знает про SQLAlchemy через тип репозитория. По SOLID — `Protocol` для каждого репо был бы честнее, особенно если планируются юнит-тесты с подменой. На текущем размере проекта — допустимо, но зафиксировать как осознанный долг.

🟠 **Возвращают ORM-сущности `Task`/`Focus`/... наружу.** Это значит: сервисы и (через возврат) даже API работают с persistence-моделями. Утечка инфраструктуры в домен. Альтернатива: возвращать domain dataclass'ы или хотя бы DTO — но это пока расход без выгоды, если домена нет (см. итерацию 2).

🟠 **Несогласованность дизайна.** `BaseRepository` есть, но `UserSettingRepository` и `ScheduleRepository` в `settings_repo.py` **не наследуют** его и не используют generic-API. Дополнительно `settings_repo.py` хранит **два разных репозитория в одном файле** — нарушение SRP файла.

🟠 **Логика домена просачивается в репозитории.** `_PRIORITY_ORDER` (case) — это правило **домена** «high > medium > low > else», заданное на уровне SQL. Лучше — Enum c числовым весом / column в БД / value-object на стороне домена; репозиторий не должен помнить, что high < medium. То же касается `mark_done` — это сервис, а не репо.

🟠 **`ContentRepository` отсутствует в DI (`providers.py`).** Файл есть, но в `providers.py` нет `get_content_repo`. См. `ContentService` — он, скорее всего, обращается к БД напрямую (это разберётся в итерации 4). То есть пайплайн содержимого «обходит» собственный репозиторий — мёртвый код или незавершённая фича.

🟠 **`ScheduleRepository` и `UserSettingRepository` не зарегистрированы в `providers.py`** — повторяет ту же проблему. Сервис `SettingsService` берёт `session` и работает в обход репозиториев (это будет видно дальше).

### `base.py`

🟢 Generic `BaseRepository[ModelT]` — норм.

🟠 **`create(**kwargs)` / `update(**kwargs)`** — приём произвольных kwargs ломает типобезопасность: можно вписать любой атрибут, IDE/Mypy ничего не словят. Передавать DTO/TypedDict или явные параметры (на CRUD‑уровне это критично меньше, но это причина потенциальных багов).

🟠 **`update` делает `get` → setattr → flush.** Это два запроса вместо одного (SELECT, потом UPDATE). Для одиночных обновлений ок, для горячих путей — `UPDATE ... RETURNING` одним запросом.

🟠 **`delete` тоже `get` → `session.delete` → flush.** Лишний SELECT. Можно `DELETE ... WHERE id=:id` одним запросом. Особенно важно для `Note` — там `cascade="all, delete-orphan"` без `passive_deletes=True` догрузит детей.

🟡 **`get_all()` без `limit/offset`** — на любой таблице, которая может вырасти (content_items, tasks), это будет проблемой. Удалить или превратить в `_get_all_unbounded` с комментарием «использовать только в фоне». Сейчас наследуется автоматически — соблазн вызвать высокий.

🟡 **`flush()` после каждого `create/update/delete`** — корректно, но при batch-операциях избыточно (несколько `flush`-ей подряд). Можно сделать опциональным.

🟡 Нет `__slots__` / прозрачного интерфейса (`Protocol`). Минорно.

### `task_repo.py`

🟠 **`_PRIORITY_ORDER` — модульный CASE** (строки 10-15). Каждый раз компилируется в SQL `CASE WHEN priority='high' THEN 0 ...`. Postgres всё равно его кеширует, но это не оптимальный путь сортировки.
- *Альтернатива:* добавить колонку `priority_weight: int` с триггером/computed-column в БД, и сортировать по ней. Или сделать enum с числовыми значениями (но тогда теряется человекочитаемость).

🟠 **`get_by_date` / `get_pending_by_date`** — фильтрация по `scheduled_date` + `status`, индекса композитного нет (см. итерацию 2). Под нагрузкой будет seq scan.

🟠 **`get_overdue_pending(today)` — без `limit`.** При накоплении прошлогодних pending — выгрузит весь хвост в память. Добавить limit + явно «за N дней назад».

🟠 **`bulk_postpone` — `update(...).values(scheduled_date=to_date)`** — корректный bulk, но **не обновляет `updated_at`**. SQLAlchemy `onupdate=func.now()` срабатывает на ORM-level операциях; чистый bulk `update()` его обходит. Это значит, после массового переноса все строки имеют старый `updated_at`. Добавить явно `.values(scheduled_date=to_date, updated_at=func.now())`. Та же проблема во всех bulk-update'ах ниже.

🟢 `mark_done` делегирует в `update` — ок, но это «доменное действие», лучше вынести в сервис.

### `backlog_repo.py`

🟢 Один метод, чистый. Сортировка по `created_at desc` — нужен индекс при росте, сейчас не нужен.

🟡 Нет limit/offset. См. выше.

### `focus_repo.py`

🟠 **`get_active`** — `order_by(Focus.created_at.desc())`. Это намёк, что **в БД может быть несколько активных** записей для одного периода. Защита от инварианта на уровне приложения. Уникальный partial index на `(period) where is_active = true` решит проблему (см. итерацию 2).

🟠 **`deactivate_period`** — bulk `update(...).values(is_active=False)` без `updated_at=func.now()`. Тот же баг.

🟢 `is_(True)` вместо `== True` — правильный стиль для SQLAlchemy.

### `note_repo.py`

🟢 `selectinload(Note.items)` — N+1 закрыт.

🟢 `get_max_sort_order` с `COALESCE(MAX, -1)` — чистая идея для «положить в конец списка».

🟠 `NoteItemRepository.get_max_sort_order(note_id)` дублирует часть логики, которая должна быть в `NoteService.append_item()`. Сейчас это лежит в репо — допустимо, но граница «репо vs. сервис» здесь размыта.

🟡 Нет метода `reorder(note_id, item_ids)` — если он есть в сервисе, то по N апдейтов на каждую перестановку — медленно. Лучше CASE-based batch.

### `content_repo.py`

🟠 **`mark_shown`**: `shown_at=datetime.now(tz=UTC).replace(tzinfo=None)` (строка 47) — берёт UTC и **выкидывает tzinfo**, чтобы вписать в `TIMESTAMP WITHOUT TIME ZONE`. Это симптом проблемы из Итерации 2 (поля без `timezone=True`). После перехода на TZ-aware колонки — убрать `.replace(tzinfo=None)`. Сейчас работает, но опасно: если в каком-то месте появится наивный `datetime.now()` (local), смешаются часовые пояса.

🟠 **`get_new_by_topic`** — фильтр `topic=... AND status=...`, сортировка `created_at desc`, limit. Индекса `(status, topic, created_at desc)` нет — на 100k+ строк будет дорого. См. итерацию 2.

🟡 `get_existing_urls` через `IN (...)` — для очень длинных списков (>1000) PostgreSQL может потерять план. Если будут массовые fetch'и — резать на чанки или использовать `ANY(:urls)` с массивом. Сейчас не критично.

🟢 `mark_shown` обновляет и `updated_at=func.now()` — хорошо. **Но в других репо это забыто** (см. focus/task bulk).

### `settings_repo.py`

🟠 **Два разных репозитория в одном файле** — нарушение SRP файла. Разделить: `user_settings_repo.py`, `schedule_repo.py`.

🟠 **Не наследуют `BaseRepository`** — несогласованность стиля.

🟠 `ScheduleRepository.upsert` — ручной `get → set / else add` вместо Postgres `INSERT ... ON CONFLICT` (как в `UserSettingRepository.upsert`). Это два разных подхода к идемпотентному upsert в одном файле — DRY и консистентность нарушены. Заменить на `insert(Schedule).on_conflict_do_update(index_elements=["event_name"], set_={...})` одним запросом вместо двух.

🟠 **Не зарегистрированы в DI.** Если используются — то через прямой `Repository(session)` в сервисе. Это разорвёт DI-цепочку.

🟡 `UserSettingRepository.delete` — имя `delete` shadow'ит builtin/имя метода `BaseRepository.delete(record_id)`. Сигнатуры разные (там id, тут key). Не баг, но конфузит, если позже унифицируете.

### Импорты / цикличность

- `base.py` → `models.base` ✅
- `*_repo.py` → `models.*` + `base` ✅
- `settings_repo.py` напрямую `AsyncSession` (без `BaseRepository`) — это ок, но почему не унифицировано — см. выше.
- Цикличности нет.
- 🟠 `content_repo.py` и `settings_repo.py` не упомянуты в `providers.py` — формально не цикл, но «висящие» модули.

### Перформанс — выводы для слоя

- 🟠 `update`/`delete` в `BaseRepository` — 2 запроса вместо 1.
- 🟠 Bulk updates (`bulk_postpone`, `deactivate_period`) не обновляют `updated_at`.
- 🟠 Нет составных индексов под фактические фильтры (см. итерацию 2 — это парная проблема).
- 🟠 `get_overdue_pending` без limit.
- 🟢 `selectinload` в `NoteRepository` — корректное закрытие N+1.
- 🟡 `get_all()` без limit/offset — на больших таблицах ловушка.
- 🟡 `IN (urls)` в `get_existing_urls` — для очень длинных списков.

### План фиксов для Repositories (приоритет)

1. 🟠 Зарегистрировать `ContentRepository`, `UserSettingRepository`, `ScheduleRepository` в `providers.py` и использовать их в сервисах (или удалить, если мёртвый код).
2. 🟠 Все bulk-update'ы: добавить `updated_at=func.now()` в `.values()`.
3. 🟠 `BaseRepository.update/delete` → один запрос (`update(...).returning(...)`, `delete(...)`).
4. 🟠 Унифицировать `ScheduleRepository.upsert` через `insert(...).on_conflict_do_update(...)`.
5. 🟠 `settings_repo.py` → разделить на два файла, наследовать `BaseRepository`.
6. 🟠 Вынести `_PRIORITY_ORDER` из репозитория в домен (или в колонку `priority_weight`).
7. 🟠 `mark_done` → переместить в `TaskService` (репо — только данные).
8. 🟠 `get_overdue_pending` — добавить `limit` и/или окно дней.
9. 🟠 `mark_shown`: убрать `.replace(tzinfo=None)` после перехода на TZ-aware datetime.
10. 🟡 `BaseRepository.get_all` → опциональные `limit/offset` или удалить из базы.
11. 🟡 Ввести `Protocol`-интерфейсы для репозиториев, чтобы сервисы зависели от абстракций.
12. 🟡 `get_existing_urls` — чанковать при больших списках.

---

## Итерация 4 — Services (`backend/services/`)

Файлы: `task_service.py`, `focus_service.py`, `note_service.py`, `settings_service.py`, `workout_service.py`, `content_service.py`, `focus_resolver.py`, `llm_service.py`.

### Архитектура слоя / DDD

🟠 **Сервисы инстанцируют репозитории в `__init__` через `Repo(session)`** во всех «БД-сервисах» (`TaskService`, `FocusService`, `NoteService`, `SettingsService`, `ContentService`). DI у нас уже есть (Dishka), но сервисы пользуются им только для `AsyncSession`, а репозитории создают вручную.
- Последствия: невозможно подменить репозиторий в тестах; теряется смысл регистрации репо в `providers.py` (которая и так выполнена непоследовательно — см. итерацию 3); явная зависимость от конкретного класса.
- *Fix:* сервис принимает уже сконструированные репо.

🟠 **Смешение слоёв: сервис держит и репо, и `_session`** (см. `TaskService.__init__`, `NoteService.__init__`, `WorkoutService.__init__`). Сервис не должен напрямую работать с `AsyncSession` — это утечка инфраструктуры. Сейчас `WorkoutService` сам пишет `select(WorkoutCache)` и `insert(...).on_conflict_do_update(...)` мимо репо (которого даже нет). Это нарушение DIP/SRP.

🟠 **`_today()` дублируется в `task_service.py`, `focus_service.py`, `workout_service.py`** — три копии одной функции «текущая дата в TZ приложения». DRY. Вынести в `backend/core/time.py` (или `clock.py`) + сделать инжектируемым `Clock`-протоколом, чтобы тестировать «сегодня» детерминированно.

🟠 **Сервисы импортируют `settings` напрямую** (`task_service.py:9`, `focus_service.py:8`, `workout_service.py:13`, `_today` берёт `app_timezone`). Это нарушает DIP: сервис тянет глобальный singleton. Должен идти через `Settings` (или `Clock`) из DI.

🟠 **Сервисы возвращают ORM-объекты наружу** (`Task`, `Focus`, `Note`, `ContentItem`). Сервис уровня application должен возвращать DTO/доменные объекты. Как и с репозиториями, это решение зафиксируется и в API.

🟠 **Бизнес-логика и инфраструктура перемешаны в `SettingsService`**: одно и то же место отвечает за интересы, расписания, кэш Redis-publish, дефолты, сериализацию DTO, и парсинг `cron ↔ HH:MM`. По SRP это минимум 2 сервиса: `InterestService`, `ScheduleService` (+ выделить `CronTimeParser`).

### `task_service.py`

🟠 **`move_pending_to_backlog` — N+1 на запись.** Цикл:
```python
for task in pending:
    await self._backlog.create(...)
    await self._tasks.delete(task.id)
```
На N задач = 2N запросов + ещё SELECT внутри `delete` (см. `BaseRepository.delete` — он делает `get` + `delete`). Итого 3N. Заменить на:
- bulk `INSERT INTO backlog SELECT ... FROM tasks WHERE ...` и `DELETE FROM tasks WHERE ...` — два запроса всего.

🟠 **`postpone_pending_to_tomorrow` использует bulk-update, но не апдейтит `updated_at`** (см. итерацию 3, `bulk_postpone`). Та же история.

🟠 **`create_task(priority="medium")` — priority как строка**, потом `TaskPriority(priority)`. Это перенос валидации в момент конструирования enum (упадёт ValueError). Лучше принимать `TaskPriority`, валидировать на границе (Pydantic-DTO в API).

🟠 **`source: str = "telegram"`** — магическая строка как дефолт. Если этот сервис вызывается из API/HTTP, то source — не «telegram». Делать «telegram» источником по умолчанию для всех — баг. Тестировать. Source должен приходить от контекста вызова явно (telegram-bot, web, scheduler).

🟠 **`update_task(**kwargs)`** — снова приём произвольных kwargs (передача из API в репо в БД). Любое поле, включая `id` и `created_at`, можно проставить. Mass-assignment уязвимость на уровне сервиса.

🟡 Хвостовые `return updated` в каждом методе после переменной — мёртвая стилистика, можно `return await ...`. DRY.

🟡 `move_from_backlog_to_today` теряет `notes` бэклога при создании задачи (передаёт только title) — баг или дизайнерское решение? Если решение — комментарий.

🟢 Чёткое деление «задачи / бэклог», секции выделены — читабельно.

### `focus_service.py`

🟢 Простой, очевидный.

🟠 **`set_week_focus`**: сначала `deactivate_period`, потом `create`. Это **две транзакционные операции**, но коммит делает middleware в `providers.py` (один на запрос). Если между ними произойдёт `await` с ошибкой — ничего страшного, всё откатится. Это работает только из-за «request-level» транзакции — если позже вынести в фоновый таск, поведение поменяется. Зафиксировать как pre-condition «выполнять внутри одной транзакции».

🟠 `_week_key`/`_month_key` — value-объекты, должны жить в `domain/value_objects/period_key.py` (если будет домен) или хотя бы в `models/focus.py` рядом с моделью. Сейчас «вычисление ключа недели» завязано на сервис; репозиторий не сможет фильтровать по корректному ключу без знания про этот код.

### `note_service.py`

🟠 **`add_item`: `get_max_sort_order(note_id) + 1`** — race condition. Два параллельных запроса на add_item одной ноте создадут две записи с одинаковым `sort_order`. Решения: `SELECT ... FOR UPDATE`, либо `INSERT ... RETURNING sort_order` с `MAX+1` в одном запросе, либо partial unique по `(note_id, sort_order)` + retry.

🟠 **`update_note` после `update` делает второй `get_with_items` ради items** — два запроса вместо одного. Можно `update(...).returning(*)` + догрузить items одним `selectinload`. Или просто пересобрать `Note` с уже знакомыми items в памяти.

🟠 **`create_note` вызывает `await session.refresh(note, ["items"])`** — лишний запрос. После создания у ноты гарантированно нет items, можно просто `note.items = []` без обращения к БД (если `lazy="selectin"` не выставлен, sqlalchemy сам ничего не сделает; но обращение к `note.items` без refresh упадёт). Зафиксировать в моделях `lazy="selectin"` (см. итерацию 2) — этот хак уйдёт.

🟡 `update_item(**fields)` если оба `text/checked` is None → лишний `get(item_id)` ради no-op возврата. Можно вернуть None или `await self._items.get(item_id)` оптимизировать. Минор.

### `settings_service.py`

🔴 **`_DELETED = "__deleted__"` magic value** (строка 16). Удалённые дефолтные интересы помечаются строкой `"__deleted__"` в той же колонке value. Это «soft-delete» через значение — ломает фильтры (`val.lower() == "true"` для удалённого даст False, но запись остаётся, она «отрицательно живая»). Семантика хрупкая, плюс при поиске «все интересы из DB» придётся фильтровать вручную. Лучше отдельная колонка `is_deleted: bool` или вообще таблица `disabled_default_interests`.

🟠 **`get_schedules` / `update_schedule` — оба строят `ScheduleDTO` с практически идентичной логикой**, отличается только источник полей (`s if s else default`). Дубль. Вынести в `ScheduleDTO.from_models(default, db)`.

🟠 **`_cron_to_time`/`_time_to_cron`** — низкоуровневая логика, лежит в файле сервиса. По SRP — это `CronParser`, выделить в `backend/services/cron_parser.py` (или `domain/cron.py`).

🟠 **`get_interests` — двойной проход по `all_settings`**: сначала по `DEFAULT_INTERESTS.items()` ищет в dict, потом по `all_settings.items()` ищет кастомные. Полная фильтрация массивных префиксов через `if db_key.startswith("interests."):` каждый запрос. Микрооптимизация, но дизайн раскрашен через if/elif/else. Стоит хранить интересы отдельной таблицей (см. итерацию 2) — half этого кода исчезнет.

🟠 **`update_schedule` публикует в Redis, но обёрнуто в `try/except Exception` с `logger.warning`** (строки 154-157). Это «silently swallow» — если шина сломалась, сервис вернёт успех, а scheduler не перезагрузится. Должно быть либо явное переподключение, либо хотя бы возврат флага `reload_requested`. На текущий момент — приемлемо, но фикс зафиксировать.

🟠 **`DEFAULT_SCHEDULES` — список словарей**: типы не проверяются (нет TypedDict), события дублируются константами в коде scheduler'а. Хорошо бы вынести в `schedule_catalog.py` как dataclass'ы.

🟢 `SPLIT_EVENTS: frozenset` — корректно (immutable).

🟢 `ScheduleDTO` через `@dataclass` — хорошо.

### `workout_service.py`

🟠 **Структура импортов нарушена.** Сверху файла объявлен `_tz` и `_today` (строки 15-19), а *после* — импорт `GoogleSheetsClient` и `WorkoutCache` (строки 22-26). Все импорты должны быть в начале файла (PEP 8). Это либо случайность, либо «защита от циклической зависимости» — но тогда это симптом проблемы, которую надо чинить структурно.

🟠 **`_today` определена тут же.** Дублирует код из `task_service.py` и `focus_service.py`.

🟠 **`get_workout_for_date` пишет SQL прямо в сервисе** (`select(WorkoutCache)...`) — нет репозитория. Должен быть `WorkoutCacheRepository`.

🟠 **`sync_week`: внутри цикла `parse_workout_text(raw["raw"] if raw else "")`** — а если `raw` есть, но `raw["raw"]` пустой? `parse_workout_text("")` всё равно вернёт plan? Если возвращает «отдых», это ок, если падает — ловится общим `except Exception` на строке 75. Молчаливое глотание ошибок без логирования отдельных кейсов — затрудняет отладку.

🟠 **`_upsert_cache`**: `datetime.now(tz=_tz).replace(tzinfo=None)` (строка 93) — снова tz-aware → naive, потому что колонка без timezone. Симптом из итерации 2.

🟡 `parse_workout_text` — функция импортируется из `integrations.google_sheets`, но логика парсинга — доменная. Перевести в `services/`/`domain/`.

### `content_service.py`

🔴 **DRY catastrophe — 4 метода `collect_rss/youtube/vk/news`** — практически идентичны по структуре:
- собрать кандидатов,
- получить existing urls,
- зациклиться, создать с разным `type`/`source`,
- логировать.

Это просится в обобщение:
```python
async def _collect(self, items, source, content_type) -> int: ...
```
Сейчас 100+ строк дубля.

🔴 **`collect_dynamic` дублирует логику ещё раз** — внутри if/elif для `newsapi`/`youtube` повторяет паттерн «existing + create». 40+ строк дубля.

🟠 **`select_for_morning` / `get_new_candidates` — почти идентичны.** Первая после выбора помечает items как queued. По SRP это `select` + `mark_queued`, вторая — `select`. Объединить.

🟠 **`mark_shown(item_ids)` — цикл `for item_id in item_ids: await self._repo.mark_shown(item_id)`** — N запросов вместо одного. Сделать `bulk_mark_shown`.

🟠 **Списки `_RSS_FEEDS`, `_YOUTUBE_QUERIES`, `_VK_QUERIES`, `_NEWS_QUERIES`, `ALL_TOPICS`** — это конфигурация контента, захардкоженная в сервис. По SRP это должно жить в `data/content_sources.yml`/`config`/таблице БД и грузиться через настройки. Сейчас изменение списка требует деплоя.

🟠 **`ALL_TOPICS = list(_RSS_FEEDS.keys())`** — топики берутся из ключей RSS-фидов. Это значит, что если у топика нет RSS, его не будет в ALL_TOPICS. Скрытая связь. См. `focus_resolver.py:6` — он импортирует `ALL_TOPICS` из `content_service.py`, что создаёт прямую зависимость двух сервисов через **константу**.

🟠 **`logger.info` для KPI («saved %d items»)** — это метрика, а не лог. Если у вас есть Prometheus/metrics — отдавать туда. Сейчас неприемлемо для прода (только лог).

🟡 В `collect_youtube`/`collect_vk`/`collect_news` нет фильтра «if url is empty» — у YouTube/VK `url` всегда есть, но интерфейс не гарантирует. См. интеграции (итерация 6).

🟡 Хардкод `max_results=3` в каждом методе — почему не настраивается?

### `focus_resolver.py`

🟠 **Импортирует `ALL_TOPICS` из `content_service`** — связь сервис ↔ сервис. Это плохо для модульности. Решение: вынести `ALL_TOPICS` (а лучше — таблицу/конфиг контент-источников) в отдельный модуль.

🟠 **`_extract_topics` — наивный подстрочный матч**: `if t in desc_lower`. Если фокус — «no python today», топик «python» матчнётся. Если описание на русском — ничего не матчнётся (топики на английском). Нужна явная схема (теги/выбор из списка) либо нормальный NLP-разбор.

🟢 Сам resolver — короткий, чистый, без побочек. Хорошее использование fallback цепочки.

### `llm_service.py`

🟠 **Принимает `Settings` целиком** (строка 11, конструктор) — LSP/ISP: достаточно подмножества полей (`openai_api_key`, `openai_base_url`, `model_agents`). Это известный «code smell» Service depends on God Object. Создать `LLMConfig`-dataclass либо передавать только нужные строки.

🟠 **`temperature=0.3`, `max_tokens=1024` захардкожены** — не настраиваются. Должны идти из config.

🟠 **`generate_search_queries`** — промпт-инжиниринг с захардкоженной строкой `"EXACTLY 6"`, но параметр `n` не принимается, а возвращаемое число фильтруется по факту (валидные топики/sources). Если LLM вернёт 4 валидных и 2 невалидных — на выходе 4, и контроль над количеством теряется. Стоит ретраить или докидывать дефолты.

🟠 **`_extract_json_array`** через regex `\[.*]` — жадный матч с `re.DOTALL`. Если в ответе LLM два массива (например, markdown с примером + ответ), захватит «от первой `[` до последней `]`» — может склеить мусор. На JSON-парсере это упадёт и вернёт None. Не критично, но хрупко. Использовать LangChain `JsonOutputParser`/`PydanticOutputParser`.

🟡 `valid_ids = {c.id for c in candidates}` собирается на каждый вызов — ок, но это намёк, что `select_content` могла бы принимать `set[int]` от вызывающего.

🟢 Дедупликация с сохранением порядка, явные ограничения через ID/topic — корректно.

### Импорты / цикличность

- `task_service` → `core.config`, `models.*`, `repositories.*` ✅
- `focus_service` → `core.config`, `models.focus`, `repositories.focus_repo` ✅
- `note_service` → `models.note`, `repositories.note_repo` ✅
- `settings_service` → `repositories.settings_repo` ✅
- `workout_service` → `core.config`, `integrations.google_sheets`, `models.workout_cache` ✅
- `content_service` → `integrations.*`, `models.content`, `repositories.content_repo`, **`services.llm_service`** (импортирует `SearchQuery`).
- `focus_resolver` → `services.content_service` (ALL_TOPICS), `services.focus_service`, `services.settings_service`.
- 🟠 **`focus_resolver` → `content_service`** — сервис-к-сервису через константу. Не цикл (content_service ничего не знает про focus_resolver), но создаёт **связь high-level (focus) с low-level (content collection)** в одну сторону.
- 🟠 **`content_service` → `llm_service`** — то же. Сейчас `SearchQuery` — DTO для общения между ними. Это нормально, если DTO будет жить в нейтральном месте (например, `services/_dto.py`), а не в одном из сервисов.

Циклов нет, но есть «константа-как-конфиг» между сервисами.

### Перформанс — сводка слоя

- 🔴 `ContentService.collect_dynamic` и `select_for_morning/get_new_candidates` зовут `get_new_by_topic` в цикле — N запросов по топикам. Можно одним запросом `WHERE topic = ANY(...)`.
- 🟠 `TaskService.move_pending_to_backlog` — 3N запросов.
- 🟠 `NoteService.add_item` — race + 2 запроса (max+insert).
- 🟠 `ContentService.mark_shown(item_ids)` — N запросов.
- 🟠 `WorkoutService.sync_week` — последовательно (await) 7 дней. Если sheets-клиент позволяет — `asyncio.gather`.
- 🟠 `NoteService.update_note` — 2 запроса вместо одного.

### План фиксов для Services (приоритет)

1. 🔴 `ContentService` — общий метод `_collect(items, source, content_type)`, устранить 4× дубль.
2. 🔴 `SettingsService._DELETED` — заменить на нормальное удаление + соседнюю таблицу/колонку.
3. 🟠 Вынести `_today` в `core/clock.py`; добавить `Clock`-протокол.
4. 🟠 Все сервисы — принимать репозитории через DI (а не создавать в `__init__`).
5. 🟠 Сервисы не должны держать `_session` (кроме случаев, когда есть честное UoW).
6. 🟠 `TaskService.move_pending_to_backlog` → один `INSERT ... SELECT` + один `DELETE`.
7. 🟠 `ContentService.mark_shown` → bulk update.
8. 🟠 `ContentService.get_new_by_topic`-цикл → один запрос с `topic = ANY(...)` и сортировкой по приоритету топика (`CASE` в order by).
9. 🟠 `NoteService.add_item` — атомарный insert через подзапрос `MAX+1` или unique-retry.
10. 🟠 `WorkoutService` — выделить `WorkoutCacheRepository`, перенести SQL из сервиса.
11. 🟠 `WorkoutService.sync_week` — `asyncio.gather` по 7 дням.
12. 🟠 `SettingsService` → разбить на `InterestService` и `ScheduleService`; `cron_parser` в отдельный модуль.
13. 🟠 `LLMService` — принимать `LLMConfig`, не `Settings`; вынести temperature/max_tokens.
14. 🟠 `ContentService` — список фидов/запросов в конфиг/таблицу, не в код.
15. 🟠 `focus_resolver._extract_topics` — явный матч по тегам, а не подстрока.
16. 🟠 `TaskService.update_task(**kwargs)` — заменить на явные параметры; mass-assignment.
17. 🟡 Импорты в `workout_service.py` — собрать в начало файла.
18. 🟡 `ContentService.mark_queued`/`select_for_morning` — устранить дубль.
19. 🟡 Все «save N items» логи — превратить в метрики (если есть Prom).

---

## Итерация 5 — Agents (`backend/agents/`)

Файлы: `base.py`, `orchestrator.py`, `context_agent.py`, `task_agent.py`, `workout_agent.py`, `content_agent.py`, `evening_agent.py`.

### Архитектура слоя / DDD

🟠 **«Агенты» по факту — не LangGraph-агенты, а узлы конвейера.** Имя и docstring `BaseAgent` («нода в графе LangGraph») вводят в заблуждение: LangGraph здесь нет, `Orchestrator._run_agents` — это голый `for agent in (...): state = await agent.run(state)`. Это просто **pipeline / chain of responsibility**. Назвать честно: `PipelineStep`, `BriefStep`. Сейчас имя обещает фичу, которой нет → плохая навигация по коду.

🟠 **`state: dict[str, Any]` — типизация отсутствует.** Каждый агент кладёт/читает ключи по имени:
- `context_agent` → `weather`, `bus_schedule`, `is_weekend`
- `workout_agent` → `workout`; читает `date`
- `task_agent` → `tasks`
- `content_agent` → `content_items`
- `evening_agent` → `done_tasks`, `pending_tasks`

Любая опечатка ключа — silent KeyError/None. Контракт «что в state» — нигде не зафиксирован. Сделать `TypedDict` или `@dataclass MorningState/EveningState`. Это даст type-check и читабельность.

🟠 **`Orchestrator` нарушает SRP.** Делает одновременно:
1. Цепочку агентов (`_run_agents`).
2. Сборку текстов (`build_morning_brief`/`build_evening_brief`).
3. Отправку в Telegram (`notifier.send`).
4. Бизнес-логику вечера: отдельные сообщения по каждой невыполненной задаче + клавиатуры с действиями.

То есть оркестратор знает про Telegram (`evening_task_keyboard`, `evening_postpone_all_keyboard`) и форматтеры из `bot/`. Это **обратная зависимость** `agents/ → bot/`. См. импорты.

🔴 **`agents/orchestrator.py` импортирует `backend.bot.*`** (строки 14-22). Это нарушает направление зависимостей: `bot/` — entry point / адаптер презентации, `agents/` — application/domain. Сейчас оркестратор знает про `evening_task_keyboard` и формат сообщения для Telegram. Если завтра появится Discord/WebPush, orchestrator придётся переписывать. Логику «как показать вечерний итог» вынести в `NotificationService` (или в адаптер), который знает про каналы. Orchestrator должен возвращать структурированный результат, а адаптер — отображать.

🟠 **`Orchestrator` сам наследует `BaseAgent`** — но имеет три метода (`run`, `run_evening_brief`, `run_evening`), а интерфейс предусматривает только один `run()`. ISP/LSP: подкласс расширяет интерфейс, нарушая контракт `BaseAgent`. Сделать `Orchestrator` отдельным классом, без наследования.

🟠 **`Orchestrator._run_agents` гоняет всех 4 агентов последовательно**, хотя они независимы:
- `context` ↔ погода+автобусы
- `workout` ↔ workout_cache
- `tasks` ↔ tasks
- `content` ↔ content_items + LLM

Можно `asyncio.gather` для context/workout/tasks/content одновременно. Сейчас они дёргают одну `AsyncSession`, поэтому параллельность ограничена — но `weather`/`bus`/LLM — это внешние сетевые вызовы, их точно можно параллелить. См. перформанс.

🟠 **`Orchestrator` зависит от **6** конструкторных параметров.** Это «god service». Можно собрать в `BriefDependencies`-dataclass, либо разделить `MorningOrchestrator` и `EveningOrchestrator`.

🟠 **`Orchestrator` принимает `TaskService`, но использует его только… ну, он не использует его** в этом файле (введён как зависимость, в коде не дёргается). 🔴 Реально **мёртвая зависимость** — параметр `task_service: TaskService` объявлен, но не вызывается. См. строку 40, 48 — записан в `self._task_service`, ни разу не использован. Удалить.

### `base.py`

🟢 `ABC + @abstractmethod` — корректный интерфейс.

🟡 `from typing import Any` — `state: dict[str, Any]` — слишком слабо. См. выше про TypedDict.

🟡 `name` property через `__class__.__name__` — для логов; разумно.

### `context_agent.py`

🟢 Аккуратное разделение «будни/выходные», логирование исключений.

🟠 **`datetime.now(ZoneInfo(settings.app_timezone)).date()`** — снова дубль (см. итерацию 4). Использовать `Clock`.

🟠 **`settings.bus_schedule_url`** — параметр URL берётся прямо из глобального `settings` и передаётся в `_bus.get_next_departures(url=...)`. Это значит, что `BusScheduleParser` не знает свой URL и каждый вызов получает его извне. По SRP это должно жить в самом `BusScheduleParser` (передать в его конструкторе) либо в `Settings`-секции, принимаемой парсером. Сейчас агент знает «вот тебе URL» — лишний уровень.

🟠 **`try/except Exception` × 2** — глотает любые ошибки. Сейчас оправдано (агент должен пережить падение внешнего сервиса), но не отличает «нет интернета» от «битый XML» — без типизированных исключений и без алертинга. Минимально — счётчики/метрика по типам ошибок.

🟡 `START_WEEKEND_DAY = 5` — магия. `from calendar import SATURDAY` — читается лучше. Альтернатива: вынести в config `weekend_starts_on: int` (или enum).

### `task_agent.py`

🟠 **Lazy initialize `tasks = []` + try/except → return** — паттерн повторяется в 4 агентах буквально. Можно вынести базовый `_safe_run` в `BaseAgent`.

🟢 Простой, понятный.

### `workout_agent.py`

🟠 Считывает `state.get("date", datetime.now(...))` — то есть `date` может приходить из state (другой агент мог положить), но по факту его никто не кладёт. Это «потенциальная фича», которая в коде висит как dead branch. Либо ввести `ContextAgent → state["date"] = today`, либо убрать чтение из state.

🟠 То же замечание про `datetime.now(ZoneInfo(settings.app_timezone))` — дубль.

### `content_agent.py`

🟢 Корректное использование fallback цепочки (LLM → fallback).

🟠 **`await self._content.mark_queued(selected)` + `selected[:6]`** — но в `_select_with_llm` уже передали `n=6` в LLM. Если LLM вернул 4, mark_queued пометит 4, selected[:6] вернёт 4 — ок. Но `fallback_select` помечает items в `ContentService.select_for_morning` (там есть свой mark_queued внутри). Так что fallback ветка и LLM-ветка имеют **разные побочки** (внешний vs внутренний `mark_queued`). Унифицировать.

🟠 **`logger.info("Focus resolved: ...")` на каждый запуск** — нормально, но если оркестратор бежит часто, заспамит логи.

🟡 Импорт `from backend.models.content import ContentItem` — снова утечка ORM в агент. Если бы сервис возвращал DTO, не пришлось бы.

### `evening_agent.py`

🟠 **Бизнес-фильтр `[t for t in tasks if t.status == TaskStatus.done]`** живёт в агенте. Это та же логика, что в `TaskService.get_today_tasks`/`get_pending_today` (последний уже есть). Можно вызвать `task_service.get_today_tasks()` и `task_service.get_pending_today()` — два целевых запроса, но без in-memory фильтрации. Либо добавить в `TaskService.split_today_by_status() -> (done, pending)`.

🟢 Короткий, читаемый.

### `orchestrator.py` — детально

🔴 **Дублируется код сборки даты**: строки 104 и 117 — оба `datetime.now(ZoneInfo(settings.app_timezone)).date()`. + ещё контекст-агент. Дубль x3 в одном модуле.

🟠 **`all_items[:3]` / `all_items[3:]`** (строки 110, 122). «3+3» жёстко зашито: первые 3 — утром, последние — вечером. Если LLM вернул не 6 — баг (утро 3, вечер 0 или меньше). Эта логика — доменная (digest split), её место в `ContentService` или в новом `BriefBuilder`, с явным контрактом и тестами.

🟠 **`run_evening` отправляет N+1 сообщений в Telegram** в цикле (`for task in pending: await ...`) — последовательно. При 10 невыполненных это 10 сетевых вызовов в Telegram → 10 округлений RTT. Использовать `asyncio.gather` либо API Telegram batchSendMessage (если их формат подходит). Минимально — параллелить.

🟠 **`run_evening` — кросс-слой**: format_evening_summary, notifier.send, keyboards. Это «evening-flow controller», а не агент.

🟠 **Названия методов запутанные**: `run` (утренняя сводка), `run_evening_brief` (вечерняя сводка), `run_evening` (вечерний итог). Глядя на код, легко перепутать `evening_brief` и `evening`. Дать осмысленные имена: `run_morning_brief`, `run_evening_brief`, `run_evening_summary`.

🟠 **`{**state, "morning_brief": text}` / `{**state, ...}`** — каждый раз создаётся новый dict. Если state большой — лишние аллокации, плюс **mutable state без иммутабельной модели**. С TypedDict стало бы яснее.

🟡 `_notifier.send(...)` ждётся последовательно — нет таймаута/ретрая. Если Telegram лагает, утренняя сводка просто заблокируется. Wrap в `wait_for`/retry с backoff.

### Импорты / цикличность

- `agents/base` — без импортов проекта ✅
- `context_agent` → `core.config`, `integrations.{weather,bus_schedule}` ✅
- `workout_agent` → `core.config`, `services.workout_service` ✅
- `task_agent` → `services.task_service` ✅
- `content_agent` → `models.content`, `services.{content,focus_resolver,llm}` ✅
- `evening_agent` → `models.task`, `services.task_service` ✅
- `orchestrator` → `agents.*`, `bot.formatters`, `bot.keyboards`, `core.config`, `integrations.telegram`, `services.task_service`

🔴 **`orchestrator → bot.*`** — agents знает про bot. Это поломанное направление. Граф зависимостей: должно быть `bot → agents`, а у нас сейчас 2-way.

🟠 Циклов нет, но **`bot/handlers/*` тоже зовут `orchestrator.run_evening` через ioc** (см. итерацию 10) → опасность реального цикла, если `bot/` потянут что-то из `agents` на module-level.

### Перформанс — сводка слоя

- 🟠 `Orchestrator._run_agents` — последовательное выполнение 4 независимых задач (особенно внешние сетевые: weather/bus/LLM).
- 🟠 `Orchestrator.run_evening` — N последовательных `notifier.send` для pending tasks.
- 🟠 Дублирующий `datetime.now(...)` в 3 агентах + оркестраторе.
- 🟠 `evening_agent` фильтрует tasks in-memory вместо двух целевых запросов (или одного с group by).
- 🟢 `selectinload` в `ContentService → content_repo` закрывает N+1 для content (см. итерации 2-3).

### План фиксов для Agents (приоритет)

1. 🔴 Вынести `bot.formatters`/`bot.keyboards` из `Orchestrator` — ввести `NotificationService` (адаптер), agents возвращают данные.
2. 🔴 Удалить мёртвую зависимость `task_service` из `Orchestrator`.
3. 🟠 Переименовать «Agents» в «PipelineSteps»; убрать наследование `Orchestrator(BaseAgent)`.
4. 🟠 Типизировать state: `MorningState`, `EveningState` TypedDict / dataclass.
5. 🟠 `Orchestrator._run_agents` → `asyncio.gather`, где зависимости независимы (минимум context/workout/tasks/content — кроме общего DB-session-conflict’а; см. ниже).
6. 🟠 `Orchestrator.run_evening` — параллелить `notifier.send` через `gather` + ретрай/таймаут.
7. 🟠 Хардкод «3+3» — вынести в `BriefBuilder.split_for_morning_evening(items)`.
8. 🟠 Имена: `run_morning_brief`, `run_evening_brief`, `run_evening_summary`.
9. 🟠 `_safe_run` в `BaseAgent` для общего паттерна try/except + log.
10. 🟠 `EveningAgent` — заменить in-memory split на два запроса/один с агрегацией.
11. 🟠 `ContextAgent` — `bus_schedule_url` инкапсулировать в `BusScheduleParser` (без передачи URL через метод).
12. 🟡 `START_WEEKEND_DAY` → `calendar.SATURDAY` или config.

⚠️ **Замечание про параллельный gather с общей AsyncSession.** `AsyncSession` *не* потокобезопасна для одновременных запросов — если все 4 агента используют одну сессию (через DI Scope.REQUEST), `asyncio.gather` упадёт с `InvalidRequestError`. Чтобы реально распараллелить агентов, нужны:
- либо отдельные сессии под каждый параллельный шаг (новый scope),
- либо параллелить только те агенты, которые **не** ходят в БД (context-agent делает только сеть, workout/tasks/content — БД).

Это разруливать вместе со слоем DI (итерация 11).

---

> Следующая итерация — **Integrations**.
