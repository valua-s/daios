# Прогресс: UI-фичи и баг-фиксы DAIOS

## Выполнено

### 1. ✅ Merge conflict в task_service.py
- Разрешён в пользу `_today()` (timezone-aware через `ZoneInfo(settings.app_timezone)`)
- Файл: `backend/services/task_service.py`

### 2. ✅ Backend: эндпоинт GET /api/tasks/range
- `TaskRepository.get_by_date_range(from_date, to_date)` — `WHERE date >= from AND date <= to`
- `TaskService.get_tasks_by_range(from_date, to_date)`
- `GET /api/tasks/range?from=YYYY-MM-DD&to=YYYY-MM-DD` → TaskDTO[]
- Файлы: `backend/repositories/task_repo.py`, `backend/services/task_service.py`, `backend/api/tasks.py`

### 3. ✅ CSS: перенос текста задачи на мобилке
- `.task-title { white-space: normal; word-break: break-word; }` в `@media (max-width: 768px)`
- Файл: `frontend/src/style.css`

### 4. ✅ CSS: инпуты даты/времени на мобилке
- `.modal-date-grid { grid-template-columns: 1fr !important; }`
- `input[type="date"], input[type="time"] { max-width: 100%; box-sizing: border-box; }`
- Файл: `frontend/src/style.css`

### 5. ✅ Доработка detail-modal (просмотр задачи)
- Добавлены data-атрибуты `data-date`, `data-status` на `.task-title`
- Модал теперь показывает: статус (badge), дату (DD.MM.YYYY), время
- Файл: `frontend/src/routes/today.ts`

### 6. ✅ Страница календаря
- Новый роут `/calendar` → `frontend/src/routes/calendar.ts`
- Десктоп: месячный грид 7 колонок, навигация ← Месяц →
- Мобилка: недельный вид (7 дней вертикально)
- Ячейка: число + цветные точки (зелёная=done, оранжевая=pending) + счётчик
- Клик по дню: раскрытие inline со списком задач
- Сегодня подсвечен accent-цветом (#7c6aff)
- API: `getTasksByRange(from, to)` в `api.ts`
- Навигация: пункт "Календарь" добавлен в сайдбар
- Файлы: calendar.ts (новый), api.ts, index.ts, base.ts, style.css

### 7. ✅ CSS: правая граница инпутов даты/времени обрезалась
- Уменьшены `padding` (10px 8px) и `font-size` (13px) инпутов в `.modal-date-grid`, чтобы влезали в контейнер
- Файл: `frontend/src/style.css`

### 8. ✅ Компиляция CSS
- `bunx tailwindcss -i src/style.css -o public/style.css` — OK

### 9. ✅ Редактирование задачи из карточки
- Backend: `PATCH /api/tasks/:id` — обновление title, date, scheduled_time, notes
- `UpdateTaskRequest` в schemas.py с `clear_time`/`clear_notes` для обнуления
- `TaskService.update_task()` — generic update через repo
- Frontend: detail-modal с кнопкой "Изменить" → режим редактирования (title, date, time, notes)
- Кнопка "Сохранить" делает PATCH через клиентский JS
- Добавлен API-прокси `/api/*` в index.ts для клиентских запросов

### 10. ✅ Fix: notes не сохранялись при создании задачи
- `POST /api/tasks/` не передавал `notes` в `TaskService.create_task()`
- Добавлен параметр `notes` в `TaskService.create_task()` и передача в `_tasks.create()`
- Добавлена передача `data.notes` в контроллере `TaskController.create_task()`
- Файлы: `backend/api/tasks.py`, `backend/services/task_service.py`

## Изменённые файлы
- `backend/services/task_service.py` — conflict resolved + get_tasks_by_range
- `backend/repositories/task_repo.py` — get_by_date_range
- `backend/api/tasks.py` — GET /api/tasks/range endpoint
- `frontend/src/api.ts` — getTasksByRange
- `frontend/src/routes/today.ts` — detail-modal с датой/статусом
- `frontend/src/routes/calendar.ts` — NEW: страница календаря
- `frontend/src/index.ts` — подключён calendarRouter
- `frontend/src/layouts/base.ts` — пункт "Календарь" в навигации
- `frontend/src/style.css` — calendar стили, mobile-фиксы
- `frontend/public/style.css` — скомпилированный CSS
