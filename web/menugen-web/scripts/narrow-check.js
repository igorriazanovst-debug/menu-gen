/*
 * MG_WEBMOBILE: проверка ширины на экране 360×740.
 *
 * Не входит в CI и не тянет зависимость в package.json: playwright ставится
 * отдельно, браузер в рабочем окружении уже стоит. Запуск целиком:
 *
 *   cd web/menugen-web
 *   npm run build
 *   node scripts/serve-build.js &          # раздаёт build/ на 4173
 *   PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm i playwright --prefix /tmp/pw
 *   PLAYWRIGHT_PATH=/tmp/pw/node_modules/playwright \
 *     CHROME=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
 *     node scripts/narrow-check.js
 *
 * Выход 0 — ни один элемент не вылезает за правый край.
 *
 * Считаем не прокрутку документа: у <main> стоит overflow-auto, и широкое
 * содержимое прокручивается внутри него, не трогая документ, — scrollWidth при
 * этом остаётся 360, хотя страница непригодна. Поэтому считаем сами элементы,
 * вылезающие за правый край, и отдельно отмечаем те, что лежат внутри
 * намеренно прокручиваемой полосы (overflow-x: auto) — там это норма.
 *
 * API подменён целиком: проверяется вёрстка, а не данные.
 */
// playwright ставится вне проекта, поэтому путь к нему передаётся явно.
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');

const USER = {
  id: 1,
  email: 'tester@example.com',
  name: 'Проверяющий',
  role: 'head',
  allergies: [],
  disliked_products: [],
  family: { id: 1, name: 'Семья' },
  is_specialist: false,
  subscription_status: {
    is_premium: true,
    is_active_premium: true,
    has_ever_had_premium: true,
    plan: 'premium',
    expires_at: '2030-01-01T00:00:00Z',
    menu_quota: { limit: 4, used: 0, left: 4 },
  },
};

const MENU = {
  id: 7,
  start_date: '2026-09-21',
  end_date: '2026-09-27',
  period_days: 7,
  status: 'active',
  meal_plan_type: '3',
  mode: 'family',
  items: [0, 1, 2, 3, 4, 5, 6].flatMap((day) =>
    ['breakfast', 'lunch', 'dinner'].map((slot, i) => ({
      id: day * 10 + i,
      day_offset: day,
      meal_type: slot,
      meal_slot: slot,
      member: null,
      component_role: 'main',
      is_cooked: false,
      recipe: {
        id: 100 + day * 10 + i,
        title: 'Запеканка творожная с изюмом и ванильным соусом',
        image_url: null,
        nutrition: { calories: { value: 420, unit: 'ккал' } },
      },
    })),
  ),
};

const PLANS = [
  { id: 1, code: 'premium', name: 'Премиум', price: '399', currency: 'RUB', period_days: 30, features: ['Холодильник'] },
  { id: 2, code: 'premium_year', name: 'Премиум на год', price: '3990', currency: 'RUB', period_days: 365, features: [] },
];

const PAGE = { count: 0, next: null, previous: null, results: [] };

function stub(url) {
  if (url.includes('/users/me/')) return USER;
  if (/\/menu\/\d+\/$/.test(url)) return MENU;
  if (url.includes('/menu/')) return { ...PAGE, count: 1, results: [MENU] };
  if (url.includes('/quarantine')) return [];
  if (url.includes('/fridge/categories')) return [];
  if (url.includes('/subscriptions/plans')) return PLANS;
  if (url.includes('/subscriptions/offers')) return [];
  if (url.includes('/subscriptions/current')) return null;
  if (url.includes('/diary/')) return [];
  if (url.includes('/shopping')) return [];
  return PAGE;
}

const ROUTES = [
  ['/menu', 'Меню'],
  ['/fridge', 'Холодильник'],
  ['/shopping', 'Списки покупок'],
  ['/diary', 'Дневник питания'],
  ['/subscriptions', 'Подписка'],
];

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROME || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
  const context = await browser.newContext({ viewport: { width: 360, height: 740 } });
  await context.route('**/api/v1/**', (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(stub(route.request().url())),
    });
  });
  await context.addInitScript(() => {
    localStorage.setItem('access_token', 'stub');
    localStorage.setItem('refresh_token', 'stub');
  });

  const page = await context.newPage();
  let failures = 0;
  for (const [route, heading] of ROUTES) {
    await page.goto('http://127.0.0.1:4173' + route, { waitUntil: 'networkidle' });
    await page.waitForTimeout(600);
    const seen = (await page.content()).includes(heading);
    const m = await page.evaluate(() => {
      const inScroller = (el) => {
        // До <main>, но не включая его: у самого main стоит overflow-auto,
        // и с ним «внутри прокрутки» оказывалось бы вообще всё.
        for (let p = el.parentElement; p && p.tagName !== 'MAIN'; p = p.parentElement) {
          const ox = getComputedStyle(p).overflowX;
          if (ox === 'auto' || ox === 'scroll') return true;
        }
        return false;
      };
      const over = [...document.querySelectorAll('main *')].filter(
        (el) => el.getBoundingClientRect().right > window.innerWidth + 1,
      );
      const bad = over.filter((el) => !inScroller(el));
      return {
        allowed: over.length - bad.length,
        badCount: bad.length,
        bad: bad.slice(0, 5).map((el) => (el.className || el.tagName).toString().slice(0, 80)),
      };
    });
    const ok = m.badCount === 0 && seen;
    if (!ok) failures++;
    console.log(
      `${ok ? 'OK   ' : 'ПЛОХО'} ${route.padEnd(15)} вылезает=${m.badCount} ` +
        `(в прокручиваемой полосе: ${m.allowed}) заголовок=${seen ? 'есть' : 'НЕТ'}` +
        (m.bad.length ? '\n      ' + m.bad.join('\n      ') : ''),
    );
  }
  await browser.close();
  process.exit(failures ? 1 : 0);
})();
