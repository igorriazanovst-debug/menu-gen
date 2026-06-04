// MG_SHOP002_web_print — client-side print (browser → Save as PDF)
// MG_PRINTWEB001: render prices, per-line totals, grand total and currency.
import type { ShoppingV2ExportData } from '../types';

// MG_SHOPBUG_WEB: format Decimal-string as money with 2 decimal places.
function fmtMoney(raw: string | number | null | undefined): string {
  if (raw == null || raw === '') return '';
  const n = typeof raw === 'number' ? raw : Number(raw);
  if (!Number.isFinite(n)) return String(raw);
  return n.toFixed(2);
}

function currencySymbol(code?: string): string {
  switch ((code || 'RUB').toUpperCase()) {
    case 'RUB':
      return '₽';
    case 'USD':
      return '$';
    case 'EUR':
      return '€';
    case 'GBP':
      return '£';
    case 'KZT':
      return '₸';
    case 'UAH':
      return '₴';
    case 'BYN':
      return 'Br';
    default:
      return code || '';
  }
}

export function printShoppingList(data: ShoppingV2ExportData) {
  const esc = (s: string) =>
    s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const sym = currencySymbol(data.currency);

  const rows = data.categories
    .map((cat) => {
      const head = cat.category
        ? `<h2>${esc(cat.category)}</h2>`
        : '<h2>Без категории</h2>';
      const items = cat.items
        .map((it) => {
          const q =
            it.quantity != null
              ? ` — ${esc(String(it.quantity))}${it.unit ? ' ' + esc(it.unit) : ''}`
              : '';
          // MG_SHOPBUG_WEB: format money to 2 decimal places.
          const price =
            it.line_total != null
              ? `<span class="price">${esc(fmtMoney(it.line_total))} ${sym}</span>`
              : it.price_per_unit != null
                ? `<span class="price">${esc(fmtMoney(it.price_per_unit))} ${sym}/ед.</span>`
                : '';
          const mark = it.is_purchased ? '☑' : '☐';
          const cls = it.is_purchased ? ' class="done"' : '';
          return `<li${cls}><span>${mark} ${esc(it.name)}${q}</span>${price}</li>`;
        })
        .join('');
      return `${head}<ul>${items}</ul>`;
    })
    .join('');

  const total =
    data.total_price != null
      ? `<div class="total">Итого: ${esc(fmtMoney(data.total_price))} ${sym}</div>` // MG_SHOPBUG_WEB
      : '';

  const html = `<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">
<title>${esc(data.title)}</title>
<style>
  body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; padding: 24px; color: #1a1a1a; }
  h1 { font-size: 22px; margin: 0 0 4px; }
  .meta { color: #666; font-size: 13px; margin-bottom: 16px; }
  h2 { font-size: 15px; margin: 16px 0 6px; border-bottom: 1px solid #ddd; padding-bottom: 2px; }
  ul { list-style: none; padding: 0; margin: 0; }
  li { padding: 3px 0; font-size: 14px; display: flex; justify-content: space-between; gap: 12px; }
  li.done { color: #999; text-decoration: line-through; }
  .price { color: #444; white-space: nowrap; }
  .total { margin-top: 16px; padding-top: 8px; border-top: 2px solid #333; font-size: 16px; font-weight: 700; text-align: right; }
  @media print { body { padding: 0; } }
</style></head><body>
<h1>${esc(data.title)}</h1>
<div class="meta">${new Date(data.created_at).toLocaleDateString('ru-RU')}</div>
${rows}
${total}
<script>window.onload = function(){ window.print(); };</script>
</body></html>`;

  const iframe = document.createElement('iframe');
  iframe.style.position = 'fixed';
  iframe.style.right = '0';
  iframe.style.bottom = '0';
  iframe.style.width = '0';
  iframe.style.height = '0';
  iframe.style.border = '0';
  document.body.appendChild(iframe);

  const doc = iframe.contentWindow?.document;
  if (doc) {
    doc.open();
    doc.write(html);
    doc.close();
  }
  setTimeout(() => {
    document.body.removeChild(iframe);
  }, 60000);
}
