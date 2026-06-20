# MG_SKIN — Handoff (резюме для следующей сессии)

**Дата:** 2026-06-20
**Ветка разработки:** `claude/nifty-rubin-h90pfg`
**Последний коммит:** `71d10d3`
**Свежий APK:** артефакт `menugen-debug-apk-87` →
https://github.com/igorriazanovst-debug/menu-gen/actions/runs/27876197684 (раздел Artifacts, ~176 МБ, истекает 2026-07-04)

---

## 🎯 Задача следующей сессии
**Переделать сетку экранов и дизайн веба.** Это работа уровня layout/UX, а не точечные
правки цветов. Цветовая/скин-инфраструктура уже готова — её НЕ нужно изобретать заново,
на неё нужно опираться.

---

## ✅ Что уже сделано (Phase 0 + Phase 1)

### Инфраструктура скинов (фундамент, готов)
- **Веб — design tokens:** `web/menugen-web/src/index.css` — CSS-переменные `--c-*`
  (RGB-каналы для альфы). Два скина: `:root`/`[data-skin='main']` и `[data-skin='second']`.
  Токены: `bg, surface, surface-alt, text, muted, border, primary, primary-fg, secondary,
  accent, danger, success, warning, sidebar, sidebar-fg, sidebar-muted`.
- **Веб — Tailwind:** `tailwind.config.*` маппит токены в утилиты
  (`bg-surface`, `text-muted`, `border-border`, `bg-primary`, `text-primary` и т.д.).
  Legacy-алиасы для плавной миграции: `tomato→--c-primary`, `chocolate→--c-text`,
  `rice→--c-bg` (старые классы продолжают работать и реагируют на скин).
- **Веб — переключение:** `src/theme/skins.ts` (реестр `main`/`second`, `applySkin`
  ставит `data-skin` на `<html>`, хранение в `localStorage` ключ `ui_skin`),
  компонент `src/components/ui/SkinSwitcher.tsx` (в Профиле).
- **Веб — UI-примитивы на токенах:** `components/ui/Card.tsx`, `Button.tsx`, `Input.tsx`.
- **Мобайл (Flutter):** `mobile/menugen_app/lib/core/theme/` —
  `app_skin.dart`, `app_theme.dart`, `skin_selector.dart`, `theme_cubit.dart`.
  Все бренд-цвета в feature-экранах уведены в тему (прямых `AppColors` brand-ссылок
  в экранах не осталось).

### Миграция веба на токены (Phase 1, готово)
- Тёмный сайдбар (`Sidebar.tsx`) — токены `sidebar*`, hover = `white/5` (намеренно).
- Card/Button/Input, dashboard, логин, лоадер — на семантические токены.
- **Глобально по вебу:** `bg-white→bg-surface`, `border-gray-100/200→border-border`
  (25 файлов: все страницы + модалки). Карточные фоны и разделители — токен-driven.

### Сознательно НЕ трогали
- `text-gray-*` (вторичный текст) на вебе — это типографическая иерархия; в обоих
  светлых скинах визуально идентично. Слепая замена «сплющила» бы градации.
- Семантика: ошибки (red), сроки годности, категории, premium-золото.

---

## ⏳ Что осталось (вне задачи редизайна, но в бэклоге)
1. **Second-скин** — сейчас рабочее приближение палитры (`[data-skin='second']` и
   мобильный аналог). Нужна точная подгонка под референс `second_theme`.
2. **Логотип** — ассета ещё нет. Слоты под вставку размечены: web-сайдбар, web-логин,
   mobile-логин.

---

## 🧭 Ориентиры в коде для редизайна веба
- Страницы: `web/menugen-web/src/pages/` — `Menu/`, `Recipes/`, `Shopping/`, `Fridge/`,
  `Diary/`, `Family/`, `Profile/`, `Subscriptions/`, `specialist/`.
- Layout: `web/menugen-web/src/components/layout/` (Sidebar и обёртки).
- UI-примитивы: `web/menugen-web/src/components/ui/`.
- **При редизайне использовать токены** (`bg-surface`, `border-border`, `text-muted`,
  `bg-primary`…), а не литералы — тогда оба скина продолжат работать автоматически.

## 🔧 Проверка перед коммитом (веб)
```
cd web/menugen-web
./node_modules/.bin/tsc --noEmit
CI=false npm run build
CI=true npx react-scripts test --watchAll=false --passWithNoTests
```
(сейчас зелёные: tsc 0, build 0, 47/47 тестов)

## ⚠️ Заметки по CI
- **CI / Backend Lint** на ветке — пред­существующий долг бэкенда, падает независимо
  от наших web/mobile коммитов. На веб-изменения не реагировать.
- **Web CI** и **Flutter CI** — зелёные.

## Git / процесс
- Разработка и пуш только в `claude/nifty-rubin-h90pfg` (`git push -u origin <branch>`).
- PR не создавать без явной просьбы.
