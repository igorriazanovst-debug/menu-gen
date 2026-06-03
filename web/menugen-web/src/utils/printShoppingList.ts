// MG_SHOP002_web_print — client-side print (browser → Save as PDF)
import type { ShoppingV2ExportData } from '../types';

export function printShoppingList(data: ShoppingV2ExportData) {
  const esc = (s: string) =>
    s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

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
          const mark = it.is_purchased ? '☑' : '☐';
          const cls = it.is_purchased ? ' class="done"' : '';
          return `<li${cls}>${mark} ${esc(it.name)}${q}</li>`;
        })
        .join('');
      return `${head}<ul>${items}</ul>`;
    })
    .join('');

  const html = `<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">
<title>${esc(data.title)}</title>
<style>
  body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; padding: 24px; color: #1a1a1a; }
  h1 { font-size: 22px; margin: 0 0 4px; }
  .meta { color: #666; font-size: 13px; margin-bottom: 16px; }
  h2 { font-size: 15px; margin: 16px 0 6px; border-bottom: 1px solid #ddd; padding-bottom: 2px; }
  ul { list-style: none; padding: 0; margin: 0; }
  li { padding: 3px 0; font-size: 14px; }
  li.done { color: #999; text-decoration: line-through; }
  @media print { body { padding: 0; } }
</style></head><body>
<h1>${esc(data.title)}</h1>
<div class="meta">${new Date(data.created_at).toLocaleDateString('ru-RU')}</div>
${rows}
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
