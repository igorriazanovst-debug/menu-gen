# MenuGen — Резюме для нового чата

**Проект:** Генератор меню (MenuGen)
**Дата:** Апрель 2026
**Репозиторий:** https://github.com/igorriazanovst-debug/menu-gen

---

## Правила работы

1. Диалог на русском языке
2. Если непонятно — задавай вопрос
3. Исправления через скрипт где возможно
4. Файлы проекта в Project Knowledge (GitHub)
5. Не объясняй. Не извиняйся. Только код.
6. НИКОГДА не хардкодь URL, токены, пароли
7. Резюме для нового чата — в виде файла
8. В начале нового чата: резюме → файлы проекта → вопрос если нужен

---

## Статус этапов

| Этап | Описание | Статус |
|---|---|---|
| 1 | Бэкенд (Django + PostgreSQL) | ✅ |
| 2 | Flutter мобильное приложение | ✅ |
| 3 | React веб-приложение | ✅ |
| 3.5 | Локальный стенд Windows 11 | ✅ |
| 4 | Интеграции (VK, FCM, доставка) | ⏳ |
| 5 | Кабинет специалиста (React) | ✅ |
| 6 | Тестирование и релиз | 🔄 |

---

## Локальный стенд Windows 11

**Путь проекта:** `C:\Temp\2026\menu-gen\menu-gen`

### Запуск докера
```powershell
cd C:\Temp\2026\menu-gen\menu-gen
docker compose up -d
cd web\menugen-web
npm start
```

### Сервисы
| Сервис | URL |
|---|---|
| Swagger | http://localhost:8000/api/v1/docs/ |
| Django Admin | http://localhost:8000/admin/ |
| React web | http://localhost:3000 |

### ⚠️ IP меняется после рестарта (DHCP)
После каждого рестарта нужно:
1. Узнать новый IP: `ipconfig | findstr "192.168"`
2. Обновить `.env`: `ALLOWED_HOSTS=localhost,127.0.0.1,<новый_IP>`
3. Перезапустить **полностью**: `docker compose down && docker compose up -d` (НЕ просто restart!)
4. Пересобрать APK: `flutter build apk --debug --dart-define=API_BASE_URL=http://<новый_IP>:8000/api/v1`

### ⚠️ ALLOWED_HOSTS — важно
`docker compose restart backend` НЕ подхватывает изменения `.env`.
Всегда использовать `docker compose down && docker compose up -d`.

---

## Сборка APK

```powershell
cd C:\Temp\2026\menu-gen\menu-gen\mobile\menugen_app
flutter build apk --debug --dart-define=API_BASE_URL=http://<IP>:8000/api/v1
```
APK: `mobile\menugen_app\build\app\outputs\flutter-apk\app-debug.apk`

### Конфиг URL в Flutter
`lib/core/config/app_config.dart` — читает `API_BASE_URL` из `dart-define`

### ⚠️ PowerShell и кодировка
PS-скрипты с кириллицей в строках портят кодировку dart-файлов.
Dart-файлы с кириллицей создавать напрямую как файл-артефакт и копировать вручную.

---

## Android конфигурация

| Файл | Значение |
|---|---|
| `android/settings.gradle` | AGP `8.3.2`, Kotlin `1.9.0` |
| `gradle-wrapper.properties` | Gradle `8.4` |
| `app/build.gradle` | `compileSdk=34`, `minSdk=21`, `targetSdk=34` |
| `app/build.gradle` | `sourceCompatibility=VERSION_17`, `targetCompatibility=VERSION_17` |
| `app/build.gradle` | `kotlinOptions { jvmTarget = "17" }` |
| `pubspec.yaml` | `dependency_overrides: sqlite3_flutter_libs: 0.5.20` |
| `gradle.properties` | `android.jetifier.enabled=true` |

**Java:** Android Studio JBR 21
```powershell
flutter config --jdk-dir "C:\Program Files\Android\Android Studio\jbr"
```

---

## Этап 1: Бэкенд — ✅

**Стек:** Python 3.11, Django 4.2, DRF, JWT, PostgreSQL 15, Redis 7, Celery

---

## Этап 2: Flutter мобильное приложение — ✅

**Стек:** Flutter 3.22, Dart, BLoC, Drift, flutter_secure_storage, go_router, dio

### Важные особенности
- `lib/` был в `.gitignore` — исправлено добавлением `!mobile/menugen_app/lib/`
- `.freezed.dart` и `.g.dart` удалены, модели переписаны как plain Dart классы
- `AppDatabase` — абстрактный интерфейс для мокирования в тестах
- `ApiClient` — абстрактный интерфейс с `Future<dynamic>`
- Bloc-файлы НЕ используют `ApiException.fromDio` — только `e.toString()`

### Архитектура роутера (app_router.dart)
- `FamilyBloc` НЕ в `MultiBlocProvider` в `main.dart`
- `FamilyBloc` создаётся прямо в роутере через `BlocProvider` с `..add(FamilyLoadRequested())`
- `FamilyScreen` — `StatelessWidget` без `initState`, загрузка через `BlocProvider.create` в роутере
- Аналогично нужно поступать с любым экраном вне `ShellRoute`, которому нужен свой Bloc

```dart
GoRoute(
  path: '/family',
  builder: (_, __) => BlocProvider(
    create: (_) => FamilyBloc(apiClient: apiClient)..add(const FamilyLoadRequested()),
    child: const FamilyScreen(),
  ),
),
```
