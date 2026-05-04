# Резюме для следующего чата (MenuGen) — после MG-204 (web) ✅

## Контекст

Проект **MenuGen** — рецепты с расчётом КБЖУ + генератор меню.
**Спринт 2:** MG-201, 202, 203, 205 закрыты ранее. **MG-204 web — закрыт в этом чате.**
Остаётся: **MG-204 mobile** (Flutter, отложен по решению пользователя) и **MG-205-UI**.

---

## ⚠️ КРИТИЧНО: соглашения по работе с пользователем

(перенесено из RESUME-13 + дельты из этого чата)

- **Диалог на русском.**
- Пользователь скачивает файлы Claude в `/tmp` на хосте → `cp /tmp/<имя> /opt/menugen/backend/scripts/<имя>`.
- Backend и БД — в Docker compose: `docker compose -f /opt/menugen/docker-compose.yml exec -T backend ...`
- **Перед apply** — gzip-бэкап БД и `.bak_<task>_<TS>` для файлов.
- Идемпотентность скриптов обязательна (маркеры `MG_<ID>_V_<part>`).
- `python3 <<'PYEOF'` для сохранения табов вместо heredoc.
- При деструктивных операциях — выводить команду отката в конце скрипта.
- **Только код, без рассуждений** в ответах.
- Резюме нового чата — отдельным файлом.
- НИКОГДА не хардкодить URL, токены, пароли (пароль admin для smoke тестов = `Admin1234!` — пользователь подтвердил).

### ⚠️ КРИТИЧНО — деплой web (зафиксировано в этом чате!)

**См. отдельный файл `/opt/menugen/DEPLOY_web.md` (приложен к Project Knowledge).**

Кратко:

| Что | Путь |
|---|---|
| Исходники CRA | `/opt/menugen/web/menugen-web/` |
| `npm run build` создаёт | `/opt/menugen/web/menugen-web/build/` |
| **nginx раздаёт из** | **`/opt/menugen/web-dist/`** |
| nginx конфиг | `/etc/nginx/sites-enabled/menugen-debug` |
| URL фронта | `http://31.192.110.121:8081/` |
| API proxy | `http://31.192.110.121:8081/api/` → `127.0.0.1:8003` |

**Полный цикл деплоя web:**
```bash
cd /opt/menugen/web/menugen-web
npx tsc --noEmit            # type check
CI=false npm run build      # CI=false → не падать на eslint warnings
rm -rf /opt/menugen/web-dist
mkdir -p /opt/menugen/web-dist
cp -a /opt/menugen/web/menugen-web/build/. /opt/menugen/web-dist/
nginx -t && nginx -s reload
# браузер: Ctrl+Shift+R
```

**Если изменения не видны после Ctrl+Shift+R** — почти всегда забыли скопировать `build → web-dist`. Проверка:
```bash
diff <(grep -oE 'src="[^"]*\.js[^"]*"' /opt/menugen/web/menugen-web/build/index.html) \
     <(curl -sH 'Cache-Control: no-cache' "http://31.192.110.121:8081/?nocache=$(date +%s)" | grep -oE 'src="[^"]*\.js[^"]*"')
```
Если хеши `main.<HASH>.js` отличаются — деплой не выполнен.

### Сборка фронта
- Node v20.19.6, npm 11.7.0
- React 19, react-router-dom 7, @tanstack/react-query 5, axios, zod, react-hook-form, tailwindcss 3.4
- typescript 4.9.5, react-scripts 5.0.1 (CRA)
- `CI=false` обязателен, иначе CRA трактует eslint warnings как errors

### Backend (без изменений с RESUME-13)
- Django + DRF, PostgreSQL, Redis, Celery
- БД пользователь: `menugen_user`, БД: `menugen`
- В compose сервис называется `backend` и `db`
- Бэкап БД: `pg_dump | gzip > /opt/menugen/backups/before_<task>_<TS>.sql.gz`

---

## Что сделано в этом чате

### MG-204 web ✅ — фронт: показ КБЖУ + выбор meal_plan_type

**Файлы:**

#### `web/menugen-web/src/types/index.ts`
- `FamilyMember` расширен: `profile?: UserProfile | null`, `allergies?`, `disliked_products?`, `role: 'head' | 'member' | 'owner'` (добавлен `'owner'` — встречается в БД)
- Маркер: `// MG_204_V_types = 1`

#### `web/menugen-web/src/api/family.ts`
Полностью переписан, добавлен метод:
```ts
updateMember: (memberId: number, payload: FamilyMemberUpdatePayload) =>
  client.patch<FamilyMember>(`/family/members/${memberId}/update/`, payload)
```
Тип `FamilyMemberUpdatePayload`: `{ name?, allergies?, disliked_products?, profile?: Partial<UserProfile> }`.
Маркер: `// MG_204_V_api = 1`

#### `web/menugen-web/src/components/family/FamilyMemberEditModal.tsx` (НОВЫЙ)
Модалка редактирования члена семьи. Поля:
- Имя (Input)
- Read-only пилюли КБЖУ (Ккал/Белок/Жиры/Углев/Клетч) — `MacroPill`
- Toggle «3 приёма / 5 приёмов» (radio-style buttons, выбранный — `bg-tomato text-white`)
- Сохранить → `familyApi.updateMember(member.id, { name, profile: { meal_plan_type } })`

Маркер: `// MG_204_V_family = 1`

#### `web/menugen-web/src/pages/Family/FamilyPage.tsx`
- Добавлен state `editing: FamilyMember | null`
- В карточке участника: `email · {calorie_target} ккал · {meal_plan_type} прм`
- Кнопка ✎ открывает `FamilyMemberEditModal`
- После save — `load()` (перезагрузка `/family/`)
- Учтена роль `'owner'` (как `'head'` для UI бейджа)

#### `web/menugen-web/src/components/menu/DayNutritionSummary.tsx` (НОВЫЙ)
Компонент: блок «Итог за день» под заголовком дня.
- Принимает `items: MenuItem[]` (за день) + `targets: NutritionTargets | null`
- Суммирует `n.calories/proteins/fats/carbs/fiber × quantity`
- 5 строк с прогресс-барами (label + actual/target unit + % + bar)
- Цвет полоски: зелёный 85-115%, жёлтый 60-130%, красный иначе. Если `target=0` — серая.
- Маркер: `// MG_204_V_summary = 1`

#### `web/menugen-web/src/pages/Menu/MenuPage.tsx`
- Импорт `DayNutritionSummary` и `NutritionTargets`
- В `MenuGrid` добавлен `targets` из `useAppSelector(state => state.auth.user?.profile)` (берёт сначала `calorie_target` и явные поля, fallback — `targets_calculated`)
- `<DayNutritionSummary items={dayItems} targets={targets} />` — после `<h3>{dayLabel}</h3>`, до `<div grid>` с `<MealCard/>`
- Маркеры: `// MG_204_V_menu = 1`, `// MG_204_V_menu_inner`

### Бэкапы (TS=20260504_125136 / 132232)

```
/opt/menugen/backups/index.ts.bak_mg204_20260504_125136
/opt/menugen/backups/family.ts.bak_mg204_20260504_125136
/opt/menugen/backups/FamilyPage.tsx.bak_mg204_20260504_125136
/opt/menugen/backups/MenuPage.tsx.bak_mg204_20260504_125136
/opt/menugen/backups/MenuPage.tsx.bak_mg204fix_20260504_125341
/opt/menugen/backups/MenuPage.tsx.bak_mg204fix2_20260504_125536
/opt/menugen/backups/menugen-web-build.tar.gz.bak_mg204_20260504_131710
/opt/menugen/backups/web-dist.tar.gz.bak_mg204_20260504_132232
```

### Скрипты в `/opt/menugen/backend/scripts/` (новые)

| Файл | Назначение |
|---|---|
| `mg_204_diagnose_web.sh` | разведка: types, ProfilePage, FamilyPage, MenuPage, api, baseline tsc |
| `mg_204_diagnose_web2.sh` | дамп Family/Menu, типы, api/family, реальный JSON /family |
| `mg_204_diagnose_web3.sh` | backend: FamilyMember*Serializer fields, urls, FamilyPage целиком |
| `mg_204_apply_web.sh` | основной apply (types, api, FamilyMemberEditModal, DayNutritionSummary, FamilyPage, MenuPage) |
| `mg_204_diagnose_menu_inject.sh` | разведка кривой вставки `<DayNutritionSummary>` |
| `mg_204_fix_menu_inject.sh` | фикс: убрать кривую вставку, поставить после `<h3>{dayLabel}</h3>` |
| `mg_204_diag_targets.sh` | проверка: где targets и MenuGrid |
| `mg_204_fix_targets.sh` | вставка `useAppSelector` + декларации `targets` в начало MenuGrid |
| `mg_204_diag_runtime.sh` | проверка файлов на диске + процессов dev-server |
| `mg_204_diag_nginx.sh` | проверка nginx root vs build/ — **обнаружил web-dist!** |
| `mg_204_build.sh` | `CI=false npm run build` + nginx reload + verify |
| `mg_204_deploy.sh` | `cp -a build/. → /opt/menugen/web-dist/` (правильный деплой) |
| `mg_204_smoke_backend.sh` | curl PATCH `/family/members/3/update/` (логин Admin1234!) — 3 кейса прошли |

### Smoke-тесты (✅ все прошли)

1. PATCH `/family/members/3/update/` `{profile:{meal_plan_type:'5'}}` → 200, БД обновлена
2. PATCH `meal_plan_type:'3'` (откат) → 200
3. PATCH `calorie_target:1900` → 200, БД=1900, `ProfileTargetAudit` записал `source=user`, `by_user_id=4`
4. `fill_profile_targets(force=True)` → calorie вернулся в 2077

### Откат всего MG-204 (web)

```bash
# 1. Файлы
cp /opt/menugen/backups/index.ts.bak_mg204_20260504_125136          /opt/menugen/web/menugen-web/src/types/index.ts
cp /opt/menugen/backups/family.ts.bak_mg204_20260504_125136         /opt/menugen/web/menugen-web/src/api/family.ts
cp /opt/menugen/backups/FamilyPage.tsx.bak_mg204_20260504_125136    /opt/menugen/web/menugen-web/src/pages/Family/FamilyPage.tsx
cp /opt/menugen/backups/MenuPage.tsx.bak_mg204_20260504_125136      /opt/menugen/web/menugen-web/src/pages/Menu/MenuPage.tsx
rm -f /opt/menugen/web/menugen-web/src/components/family/FamilyMemberEditModal.tsx
rm -f /opt/menugen/web/menugen-web/src/components/menu/DayNutritionSummary.tsx
rmdir /opt/menugen/web/menugen-web/src/components/family 2>/dev/null || true

# 2. Пересобрать и задеплоить (см. DEPLOY_web.md)
cd /opt/menugen/web/menugen-web
CI=false npm run build
rm -rf /opt/menugen/web-dist
cp -a build/. /opt/menugen/web-dist/

# 3. Откат БД (calorie_target=2077, audit очищен) — обычно не нужен
# gunzip -c /opt/menugen/backups/<dump>.sql.gz | docker compose ... psql ...
```

---

## ⏭ Следующие задачи

### Опции на выбор пользователя

1. **MG-204 mobile** (Flutter, отложен) — Profile screen + Meal plan toggle + дневные цели КБЖУ
2. **MG-205-UI** (P2, 4ч) — бейджи источника КБЖУ + кнопка «Сбросить к авто» + история
3. **Старт Спринта 3** — MG-301..304, P0, 30ч, генератор по методу тарелки

### Открытые вопросы для пользователя при старте

- Если **MG-204 mobile**: подтвердить, что Flutter-проект в `/opt/menugen/mobile/menugen_app/`. Сначала diagnose Flutter-кода.
- Если **MG-205-UI**: добавить два endpoint'а (`GET /users/me/targets/{field}/history` + `POST /users/me/targets/{field}/reset`), затем UI компонент `<TargetField>` с бейджем + dropdown'ом-историей.

---

## Бэклог Спринта 2 (актуальный)

| ID | Приоритет | Часов | Статус | Описание |
|---|---|---|---|---|
| MG-201 | P1 | 2 | ✅ | поля Profile + meal_plan_type (BE+FE) |
| MG-202 | P1 | 4 | ✅ | Mifflin-St Jeor + Profile.save() |
| MG-203 | P1 | 1 | ✅ | API возвращает БЖУ (users + family) |
| MG-205 | P1 | 8 | ✅ | Отслеживание источника правок (auto/user/specialist) |
| MG-204 | P1 | 4 | ✅ (web) | фронт: показ БЖУ + выбор meal_plan_type. **Mobile отложен.** |
| MG-205-UI | P2 | 4 | ⏳ | бейджи источника + кнопка «Сбросить к авто» + история |
| MG-204 mobile | P1 | 2 | ⏳ | Flutter: Profile + Meal plan + дневные цели КБЖУ |

---

## Состояние БД на 2026-05-04 (после smoke-тестов MG-204)

```
profiles:
  pid=1 (igor):    calorie=?  без изменений
  pid=4 (admin):   calorie_target=2077, mp=3 (восстановлено после теста)

profile_target_audit:
  AUDIT count для admin = 1 (после reset force=True добавилась запись source=auto)
  для остальных profiles — без изменений с RESUME-13

audit_log:
  +2 записи action='profile_target.update' от smoke-теста (PATCH calorie 2077→1900, reset 1900→2077)
```

---

## Структура файлов проекта (изменения)

```
/opt/menugen/web/menugen-web/src/
├── types/index.ts                          ← MG_204_V_types: FamilyMember расширен
├── api/family.ts                           ← MG_204_V_api: + updateMember
├── pages/
│   ├── Family/FamilyPage.tsx               ← MG_204_V_family: кнопка ✎ + модалка
│   └── Menu/MenuPage.tsx                   ← MG_204_V_menu: + DayNutritionSummary в MenuGrid
└── components/
    ├── family/
    │   └── FamilyMemberEditModal.tsx       ← НОВЫЙ
    └── menu/
        └── DayNutritionSummary.tsx         ← НОВЫЙ

/opt/menugen/
├── DEPLOY_web.md                           ← НОВЫЙ — постоянная памятка про деплой web
└── web-dist/                               ← собранный фронт (раздаётся nginx)
```

---

## Команды для типовых проверок

### Проверка деплоя web (что отдаётся)
```bash
diff <(grep -oE 'src="[^"]*\.js[^"]*"' /opt/menugen/web/menugen-web/build/index.html) \
     <(curl -sH 'Cache-Control: no-cache' "http://31.192.110.121:8081/?nocache=$(date +%s)" | grep -oE 'src="[^"]*\.js[^"]*"')
```

### Логин и получение JWT (для curl-тестов)
```bash
curl -s -X POST "http://31.192.110.121:8081/api/v1/auth/login/" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@dev.local","password":"Admin1234!"}'
```

### PATCH члена семьи
```bash
ACCESS=...
curl -s -X PATCH "http://31.192.110.121:8081/api/v1/family/members/3/update/" \
  -H "Authorization: Bearer ${ACCESS}" -H "Content-Type: application/json" \
  -d '{"profile":{"meal_plan_type":"5"}}'
```

(Остальные команды — см. RESUME-13.)

---

## Известные проблемы / уроки чата

1. **nginx раздаёт `/opt/menugen/web-dist`, а не `web/menugen-web/build/`!** ← главный урок чата. Зафиксировано в `DEPLOY_web.md`.
2. **CRA build с `CI=true`** падает на eslint warnings (несуществующие импорты типа `useRef`, `addDays` и т.п.). Использовать `CI=false`.
3. **Браузерный кеш CRA bundle** — без `Ctrl+Shift+R` старый JS остаётся в памяти даже после nginx reload.
4. **Пароль admin@dev.local** = `Admin1234!` (для smoke-тестов и UI).
5. **Регулярка вставки в MenuPage** — при первой попытке Python-скрипт не вставил декларацию `targets` в `MenuGrid`, потому что маркер `MG_204_V_menu` был уже в импорте → проверял только наличие маркера в файле, а не в конкретном месте. Урок: маркеры должны быть **уникальными** на каждое место вставки (`MG_204_V_menu` для импорта, `MG_204_V_menu_inner` для внутри MenuGrid).
6. (всё остальное — см. RESUME-13)

---

## Git состояние

Не закоммичено в этом чате. К коммиту готовы:
- `web/menugen-web/src/types/index.ts`
- `web/menugen-web/src/api/family.ts`
- `web/menugen-web/src/components/family/FamilyMemberEditModal.tsx` (новый)
- `web/menugen-web/src/components/menu/DayNutritionSummary.tsx` (новый)
- `web/menugen-web/src/pages/Family/FamilyPage.tsx`
- `web/menugen-web/src/pages/Menu/MenuPage.tsx`
- `web-dist/` (собранный артефакт; обычно git-ignore, но если хранится — обновить)
- `MenuGen_Backlog.xlsx` (закрыть MG-204 как ✅ web)
- `DEPLOY_web.md` (новый)
- скрипты `backend/scripts/mg_204_*` (12 шт)

Предлагаемое сообщение коммита:
```
MG-204: web — show targets + meal_plan_type select (Profile + Family + Menu)

- types/index.ts: FamilyMember.profile + allergies + role 'owner'
- api/family.ts: updateMember (PATCH /family/members/{id}/update/)
- components/family/FamilyMemberEditModal: name + read-only macros + 3/5 toggle
- components/menu/DayNutritionSummary: per-day totals vs targets, color-coded bars
- FamilyPage: ✎ button + modal integration; show calorie/meal_plan in row
- MenuPage: DayNutritionSummary above each day, targets from auth.user.profile

+ DEPLOY_web.md: critical note about /opt/menugen/web-dist (nginx root)
+ MenuGen_Backlog.xlsx: MG-204 closed (web), mobile deferred

Smoke: PATCH meal_plan_type & calorie_target → 200, audit recorded source=user.
```

---

## Что делать в начале следующего чата

1. Прочитать этот файл (`RESUME_next_chat-14.md`).
2. Прочитать `DEPLOY_web.md` (приложен к Project Knowledge).
3. Прочитать `MenuGen_Backlog.xlsx`.
4. Спросить пользователя что дальше:
   - MG-204 mobile (Flutter)?
   - MG-205-UI (бейджи + история)?
   - Старт Спринта 3 (MG-301..)?
