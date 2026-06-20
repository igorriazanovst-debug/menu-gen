// MG_SHOP002_web_page — Shopping lists page
// MG_RUBRIC009_imports
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { shoppingApi, CreateListPayload } from '../../api/shopping';
import { menuApi } from '../../api/menu';
import { fridgeApi } from '../../api/fridge';
import { familyApi } from '../../api/family'; // MG_HISTWEB001
import { Card } from '../../components/ui/Card';
import { Input } from '../../components/ui/Input';
import { Button } from '../../components/ui/Button';
import { PageSpinner } from '../../components/ui/Spinner';
import { printShoppingList } from '../../utils/printShoppingList';
import { enqueueToggle, flushQueue, SYNC_FLUSHED_EVENT } from '../../utils/syncQueue'; // MG_T08
import { ItemAutocomplete } from './ItemAutocomplete';
import type {
  ShoppingV2ListBrief,
  ShoppingV2List,
  ShoppingV2Access,
  ShoppingV2PendingList, // MG_SHAREACCEPT
  ShoppingV2HistoryEntry,
  ShoppingV2Source,
  Menu,
  ProductCategory, // MG_RUBRIC009
} from '../../types';

const SOURCE_LABEL: Record<ShoppingV2Source, string> = {
  empty: 'Пустой',
  menu: 'Из меню',
  fridge: 'Меню − холодильник',
  ai_text: 'ИИ из текста',
  csv: 'CSV',
};

type Tab = 'active' | 'pending' | 'archived' | 'history'; // MG_SHAREACCEPT

export const ShoppingPage: React.FC = () => {
  const [tab, setTab] = useState<Tab>('active');
  const [lists, setLists] = useState<ShoppingV2ListBrief[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<ShoppingV2List | null>(null);
  const [history, setHistory] = useState<ShoppingV2HistoryEntry[]>([]);
  const [pending, setPending] = useState<ShoppingV2PendingList[]>([]); // MG_SHAREACCEPT
  const [loading, setLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [showAccess, setShowAccess] = useState(false);
  // MG_T09: per-tab list counts.
  const [counts, setCounts] = useState<{ active: number; pending: number; archived: number; history: number }>(
    { active: 0, pending: 0, archived: 0, history: 0 },
  );
  const loadCounts = useCallback(async () => {
    try {
      const { data } = await shoppingApi.counts();
      setCounts(data);
    } catch {
      /* non-fatal */
    }
  }, []);

  const loadLists = useCallback(async (t: Tab) => {
    setLoading(true);
    try {
      if (t === 'history') {
        const { data } = await shoppingApi.history();
        setHistory(data);
      } else if (t === 'pending') {
        const { data } = await shoppingApi.pending(); // MG_SHAREACCEPT
        setPending(data);
      } else {
        const { data } = await shoppingApi.lists(t === 'archived');
        setLists(data);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadLists(tab);
    loadCounts(); // MG_T09
  }, [tab, loadLists, loadCounts]);

  const loadDetail = useCallback(async (id: number) => {
    const { data } = await shoppingApi.get(id);
    setDetail(data);
    setSelectedId(id);
  }, []);

  // MG_T08: flush queued offline toggles on (re)connect and on mount; reload
  // the open list after a successful flush so it reflects the server state.
  useEffect(() => {
    const onOnline = () => void flushQueue();
    const onFlushed = () => {
      if (selectedId != null) loadDetail(selectedId);
    };
    window.addEventListener('online', onOnline);
    window.addEventListener(SYNC_FLUSHED_EVENT, onFlushed);
    void flushQueue();
    return () => {
      window.removeEventListener('online', onOnline);
      window.removeEventListener(SYNC_FLUSHED_EVENT, onFlushed);
    };
  }, [selectedId, loadDetail]);

  const caps = detail?.capabilities;

  const onToggle = async (itemId: number, val: boolean) => {
    if (!detail) return;
    // MG_T08: optimistic local update first (instant UI, offline-first).
    setDetail((d) =>
      d
        ? { ...d, items: d.items.map((it) => (it.id === itemId ? { ...it, is_purchased: val } : it)) }
        : d,
    );
    if (navigator.onLine) {
      try {
        await shoppingApi.toggleItem(detail.id, itemId, val);
        await loadDetail(detail.id);
      } catch {
        enqueueToggle(detail.id, itemId, val); // request failed mid-flight -> queue (LWW)
      }
    } else {
      enqueueToggle(detail.id, itemId, val); // offline -> queue, sync on reconnect
    }
  };

  const onDeleteList = async () => {
    if (!detail || !window.confirm('Удалить список?')) return;
    await shoppingApi.remove(detail.id);
    setDetail(null);
    setSelectedId(null);
    loadLists(tab);
    loadCounts(); // MG_T09
  };

  const onArchive = async (archived: boolean) => {
    if (!detail) return;
    await shoppingApi.update(detail.id, { is_archived: archived });
    setDetail(null);
    setSelectedId(null);
    loadLists(tab);
    loadCounts(); // MG_T09
  };

  const onPrint = async () => {
    if (!detail) return;
    const { data } = await shoppingApi.exportData(detail.id);
    printShoppingList(data);
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold text-chocolate">🛒 Списки покупок</h1>
        <Button onClick={() => setShowCreate(true)}>+ Новый список</Button>
      </div>

      <div className="flex gap-2 mb-4">
        {(['active', 'pending', 'archived', 'history'] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => {
              setTab(t);
              setDetail(null);
              setSelectedId(null);
            }}
            className={[
              'px-4 py-1.5 rounded-xl text-sm transition-colors',
              tab === t ? 'bg-tomato/10 text-tomato font-semibold' : 'text-gray-600 hover:bg-gray-50',
            ].join(' ')}
          >
            {t === 'active' ? 'Активные' : t === 'pending' ? 'Ожидают' : t === 'archived' ? 'Архив' : 'История'}
            {counts[t] > 0 ? ` (${counts[t]})` : ''}
          </button>
        ))}
      </div>

      {loading ? (
        <PageSpinner />
      ) : tab === 'pending' ? (
        <PendingView pending={pending} onReload={() => loadLists('pending')} />
      ) : tab === 'history' ? (
        <HistoryView history={history} onReload={() => loadLists('history')} />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="space-y-2">
            {lists.length === 0 && <p className="text-sm text-gray-400">Списков нет.</p>}
            {lists.map((l) => (
              <Card
                key={l.id}
                className={[
                  'p-3 cursor-pointer transition-colors',
                  selectedId === l.id ? 'ring-2 ring-tomato' : 'hover:bg-gray-50',
                ].join(' ')}
                onClick={() => loadDetail(l.id)}
              >
                <div className="font-semibold text-sm">{l.name}</div>
                <div className="text-xs text-gray-500 mt-0.5">
                  {SOURCE_LABEL[l.source]} · {l.items_purchased ?? 0}/{l.items_total ?? 0}
                </div>
              </Card>
            ))}
          </div>

          <div className="md:col-span-2">
            {detail ? (
              <ListDetail
                detail={detail}
                caps={caps}
                onToggle={onToggle}
                onReload={() => loadDetail(detail.id)}
                onDelete={onDeleteList}
                onArchive={onArchive}
                onPrint={onPrint}
                onManageAccess={() => setShowAccess(true)}
              />
            ) : (
              <p className="text-sm text-gray-400">Выберите список.</p>
            )}
          </div>
        </div>
      )}

      {showCreate && (
        <CreateModal
          onClose={() => setShowCreate(false)}
          onCreated={(id) => {
            setShowCreate(false);
            setTab('active');
            loadLists('active');
            loadCounts(); // MG_T09
            loadDetail(id);
          }}
        />
      )}

      {showAccess && detail && (
        <AccessModal listId={detail.id} onClose={() => setShowAccess(false)} />
      )}
    </div>
  );
};

// ── Детализация списка ───────────────────────────────────────────────────────
const ListDetail: React.FC<{
  detail: ShoppingV2List;
  caps?: ShoppingV2List['capabilities'];
  onToggle: (itemId: number, val: boolean) => void;
  onReload: () => void;
  onDelete: () => void;
  onArchive: (archived: boolean) => void;
  onPrint: () => void;
  onManageAccess: () => void;
}> = ({ detail, caps, onToggle, onReload, onDelete, onArchive, onPrint, onManageAccess }) => {
  // MG_RUBRIC005_state_removed: add-item state moved into ItemAutocomplete.
  // MG_SHOPBUG_EDITMODE: global edit mode (delete + inline fields gated).
  const [editMode, setEditMode] = useState(false);
  const [onlyUnpurchased, setOnlyUnpurchased] = useState(false); // MG_T09
  const UNITS = ['шт','г','кг','мл','л','упак','банка','пучок','головка','бутылка','тюбик'];

  // MG_RUBRIC011_fmt: money formatter (2 decimals).
  const fmtMoney = (v: string | number | null | undefined) => {
    if (v == null || v === '') return '';
    const n = typeof v === 'number' ? v : parseFloat(String(v));
    return Number.isFinite(n) ? n.toFixed(2) : '';
  };
  // MG_RUBRIC009_cats: category metadata for colored zones.
  const [cats, setCats] = useState<ProductCategory[]>([]);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await fridgeApi.categories();
        if (!cancelled) setCats(data ?? []);
      } catch {
        /* non-fatal */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);
  const currency = detail.currency ?? 'RUB';

  // MG_RUBRIC005_addItem: add via rubricator autocomplete payload.
  const handleAdd = async (payload: import('../../api/shopping').AddItemPayload) => {
    await shoppingApi.addItem(detail.id, payload);
    onReload();
  };

  // MG_RUBRIC009: inline price edit.
  const setPrice = async (itemId: number, raw: string) => {
    // MG_RUBRIC009b: send as string|null (DRF DecimalField accepts both).
    const n = raw.trim() ? parseFloat(raw.replace(',', '.')) : null;
    const v = n != null && Number.isFinite(n) ? String(n) : null;
    await shoppingApi.updateItem(detail.id, itemId, { price_per_unit: v });
    onReload();
  };

  // MG_SHOPBUG_EDITMODE: inline name edit.
  const setName = async (itemId: number, raw: string) => {
    const v = raw.trim();
    if (!v) return;
    await shoppingApi.updateItem(detail.id, itemId, { name: v });
    onReload();
  };
  // MG_SHOPBUG_EDITMODE: inline unit edit.
  const setUnit = async (itemId: number, raw: string) => {
    await shoppingApi.updateItem(detail.id, itemId, { unit: raw });
    onReload();
  };
  // MG_RUBRIC010_setQty: inline quantity edit.
  const setQuantity = async (itemId: number, raw: string) => {
    const n = raw.trim() ? parseFloat(raw.replace(',', '.')) : null;
    const v = n != null && Number.isFinite(n) ? n : null;
    await shoppingApi.updateItem(detail.id, itemId, { quantity: v });
    onReload();
  };

  // MG_RUBRIC009: group items by category, ordered by category sort_order.
  const grouped = useMemo(() => {
    const order = new Map<string, number>();
    const meta = new Map<string, ProductCategory>();
    cats.forEach((c, i) => {
      order.set(c.slug, c.sort_order ?? i);
      meta.set(c.slug, c);
    });
    const buckets = new Map<string, ShoppingV2List['items']>();
    // MG_T09: in view-mode optionally show only unpurchased items.
    const src = !editMode && onlyUnpurchased
      ? detail.items.filter((it) => !it.is_purchased)
      : detail.items;
    for (const it of src) {
      const key = it.category_slug ?? '__none__';
      if (!buckets.has(key)) buckets.set(key, []);
      buckets.get(key)!.push(it);
    }
    return Array.from(buckets.entries())
      .map(([slug, items]) => ({
        slug,
        meta: meta.get(slug) ?? null,
        name: meta.get(slug)?.name_ru ?? (items[0]?.category || 'Без категории'),
        items,
        ord: order.get(slug) ?? 9999,
      }))
      .sort((a, b) => a.ord - b.ord);
  }, [detail.items, cats, editMode, onlyUnpurchased]);

  const delItem = async (itemId: number) => {
    await shoppingApi.removeItem(detail.id, itemId);
    onReload();
  };

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-bold text-lg">{detail.name}</h2>
        <div className="flex gap-2 flex-wrap">
          {/* MG_T09: filter to unpurchased items (view-mode) */}
          {!editMode && detail.items.length > 0 && (
            <Button variant="secondary" onClick={() => setOnlyUnpurchased((v) => !v)}>
              {onlyUnpurchased ? '☑ Только некупленные' : '☐ Только некупленные'}
            </Button>
          )}
          {/* MG_SHOPADDEDIT3: enter-edit only; Готово lives in add-bar */}
          {caps?.manage && !editMode && (
            <Button variant="secondary" onClick={() => setEditMode(true)}>✎ Редактировать</Button>
          )}
          {caps?.export && !editMode && (
            <Button variant="secondary" onClick={onPrint}>🖨 Печать</Button>
          )}
          {caps?.manage && !editMode && (
            <>
              <Button variant="secondary" onClick={onManageAccess}>👥 Доступ</Button>
              {!detail.is_archived ? (
                <Button variant="secondary" onClick={() => onArchive(true)}>📦 В архив</Button>
              ) : (
                <Button variant="secondary" onClick={() => onArchive(false)}>↩ Из архива</Button>
              )}
              <Button variant="danger" onClick={onDelete}>🗑</Button>
            </>
          )}
        </div>
      </div>

      {/* MG_SHOPADDEDIT2: add-item bar pinned above an internally-scrolling list */}
      {caps?.manage && editMode && (
        <div className="mb-2 pb-3 border-b border-border flex gap-2 items-start">
          <div className="flex-1 min-w-0">
            <ItemAutocomplete onAdd={handleAdd} currency={currency} />
          </div>
          <Button onClick={() => { setEditMode(false); onReload(); }}>✓ Готово</Button>
        </div>
      )}
      {/* MG_RUBRIC009_zones: grouped colored category zones */}
      <div className={editMode ? 'space-y-3 max-h-[60vh] overflow-y-auto pr-1' : 'space-y-3'}>
        {grouped.map((g) => (
          <div
            key={g.slug}
            className="rounded-xl p-2"
            style={{ background: g.meta?.color || '#F5F5F5' }}
          >
            <div className="flex items-center gap-1 px-1 pb-1 text-xs font-semibold text-chocolate/80">
              <span>{g.meta?.icon || '📦'}</span>
              <span>{g.name}</span>
            </div>
            <ul className="space-y-1">
              {g.items.map((it) => (
                <li key={it.id} className="flex items-center gap-2 py-1 bg-surface/60 rounded-lg px-2">
                  {/* MG_SHOPBUG_EDITMODE: hide checkbox in edit mode */}
                  {!editMode && (
                    <input
                      type="checkbox"
                      checked={it.is_purchased}
                      disabled={!caps?.toggle}
                      onChange={(e) => onToggle(it.id, e.target.checked)}
                      className="w-4 h-4"
                    />
                  )}
                  {editMode && caps?.manage ? (
                    /* MG_SHOPBUG_EDITMODE: editable name */
                    <input
                      defaultValue={it.name}
                      onBlur={(e) => { if (e.target.value !== it.name) setName(it.id, e.target.value); }}
                      placeholder="Продукт"
                      className="flex-1 rounded-lg border border-border px-2 py-0.5 text-sm"
                    />
                  ) : (
                    <span className={it.is_purchased ? 'line-through text-gray-400 flex-1' : 'flex-1'}>
                      {it.name}
                      {it.quantity != null && (
                        <span className="text-gray-500 text-sm"> — {it.quantity}{it.unit ? ` ${it.unit}` : ''}</span>
                      )}
                    </span>
                  )}
                  {editMode && caps?.manage && (
                    <>
                      {/* MG_SHOPBUG_EDITMODE: qty + unit + price inputs */}
                      <input
                        defaultValue={it.quantity ?? ''}
                        onBlur={(e) => {
                          const cur = it.quantity ?? '';
                          if (e.target.value !== String(cur)) setQuantity(it.id, e.target.value);
                        }}
                        inputMode="decimal"
                        placeholder="кол."
                        className="w-14 rounded-lg border border-border px-2 py-0.5 text-xs text-right"
                      />
                      <select
                        defaultValue={it.unit ?? ''}
                        onChange={(e) => { if (e.target.value !== (it.unit ?? '')) setUnit(it.id, e.target.value); }}
                        className="rounded-lg border border-border px-1 py-0.5 text-xs"
                      >
                        {(UNITS.includes(it.unit ?? '') ? UNITS : [it.unit ?? '', ...UNITS]).map((u) => (
                          <option key={u} value={u}>{u || '—'}</option>
                        ))}
                      </select>
                      <input
                        defaultValue={fmtMoney(it.price_per_unit)}
                        onBlur={(e) => {
                          const cur = fmtMoney(it.price_per_unit);
                          if (e.target.value !== cur) setPrice(it.id, e.target.value);
                        }}
                        inputMode="decimal"
                        placeholder="цена"
                        className="w-16 rounded-lg border border-border px-2 py-0.5 text-xs text-right"
                      />
                    </>
                  )}
                  {!editMode && it.price_per_unit != null && (
                    <span className="text-xs text-gray-500">{fmtMoney(it.price_per_unit)} {currency}</span>
                  )}
                  {it.line_total != null && (
                    <span className="text-xs text-chocolate font-medium w-20 text-right">
                      {fmtMoney(it.line_total)} {currency}
                    </span>
                  )}
                  {/* MG_SHOPBUG_EDITMODE: delete only in edit mode */}
                  {editMode && caps?.manage && (
                    <button onClick={() => delItem(it.id)} className="text-red-400 hover:text-red-600 text-sm">✕</button>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
        {detail.items.length === 0 && <p className="text-sm text-gray-400">Список пуст.</p>}
        {detail.items.length > 0 && grouped.length === 0 && (
          <p className="text-sm text-gray-400">Все товары куплены.</p>
        )}
      </div>

      {/* MG_RUBRIC009: grand total */}
      {detail.total_price != null && (
        <div className="mt-3 pt-2 border-t border-border flex justify-between items-center">
          <span className="text-sm text-gray-500">Итого</span>
          <span className="text-lg font-bold text-chocolate">{fmtMoney(detail.total_price)} {currency}</span>
        </div>
      )}

    </Card>
  );
};

// ── История ──────────────────────────────────────────────────────────────────
const HistoryView: React.FC<{
  history: ShoppingV2HistoryEntry[];
  onReload: () => void;
}> = ({ history, onReload }) => {
  // MG_HISTWEB001: family currency for price display.
  const [currency, setCurrency] = useState('RUB');
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await familyApi.get();
        if (!cancelled) setCurrency(data.currency ?? 'RUB');
      } catch {
        /* non-fatal */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);
  const fmtMoney = (v: string | number | null | undefined) => {
    if (v == null || v === '') return '';
    const n = typeof v === 'number' ? v : parseFloat(String(v));
    return Number.isFinite(n) ? n.toFixed(2) : '';
  };
  const del = async (id: number) => {
    await shoppingApi.removeHistory(id);
    onReload();
  };
  return (
    <Card className="p-4">
      {history.length === 0 && <p className="text-sm text-gray-400">История пуста.</p>}
      <ul className="space-y-1">
        {history.map((h) => (
          <li key={h.id} className="flex items-center gap-2 py-1 text-sm">
            <span className="flex-1">
              {h.name}
              {h.quantity != null && <span className="text-gray-500"> — {h.quantity}{h.unit ? ` ${h.unit}` : ''}</span>}
              {h.price_per_unit != null && (
                <span className="text-gray-500 ml-2">· {fmtMoney(h.price_per_unit)} {currency}</span>
              )}
              <span className="text-gray-400 ml-2">{new Date(h.purchased_at).toLocaleDateString('ru-RU')}</span>
            </span>
            <button onClick={() => del(h.id)} className="text-gray-300 hover:text-red-500">✕</button>
          </li>
        ))}
      </ul>
    </Card>
  );
};

// ── MG_SHAREACCEPT: ожидающие принятия общие списки ──────────────────────────
const PendingView: React.FC<{ pending: ShoppingV2PendingList[]; onReload: () => void }> = ({
  pending,
  onReload,
}) => {
  if (pending.length === 0) {
    return <p className="text-sm text-gray-400">Нет списков, ожидающих принятия.</p>;
  }
  return (
    <div className="space-y-3 max-w-2xl">
      {pending.map((p) => (
        <PendingCard key={p.id} p={p} onReload={onReload} />
      ))}
    </div>
  );
};

const PendingCard: React.FC<{ p: ShoppingV2PendingList; onReload: () => void }> = ({ p, onReload }) => {
  const [preview, setPreview] = useState<ShoppingV2List | null>(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const togglePreview = async () => {
    if (open) {
      setOpen(false);
      return;
    }
    if (!preview) {
      const { data } = await shoppingApi.get(p.id);
      setPreview(data);
    }
    setOpen(true);
  };

  const respond = async (action: 'accept' | 'reject') => {
    setBusy(true);
    try {
      await shoppingApi.respond(p.id, action);
      onReload();
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="p-4">
      <div className="font-semibold">{p.name}</div>
      <div className="text-xs text-gray-500 mt-0.5">
        {p.shared_by_name ? `Поделился: ${p.shared_by_name}` : 'Общий список'}
        {' · '}
        {p.items_total ?? 0} поз.
        {p.granted_at ? ` · ${new Date(p.granted_at).toLocaleDateString('ru-RU')}` : ''}
      </div>

      {open && preview && (
        <ul className="mt-3 border-t border-border pt-2 space-y-1 max-h-60 overflow-auto">
          {preview.items.length === 0 && <li className="text-sm text-gray-400">Список пуст.</li>}
          {preview.items.map((it) => (
            <li key={it.id} className="text-sm flex gap-2">
              <span className="flex-1">{it.name}</span>
              {it.quantity != null && (
                <span className="text-gray-500">
                  {it.quantity}
                  {it.unit ? ` ${it.unit}` : ''}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      <div className="flex gap-2 mt-3">
        <Button variant="secondary" onClick={togglePreview} disabled={busy}>
          {open ? 'Скрыть' : 'Просмотреть'}
        </Button>
        <Button onClick={() => respond('accept')} disabled={busy}>
          Принять
        </Button>
        <Button variant="secondary" onClick={() => respond('reject')} disabled={busy}>
          Отклонить
        </Button>
      </div>
    </Card>
  );
};

// ── Модалка создания ───────────────────────────────────────────────────────
const CreateModal: React.FC<{
  onClose: () => void;
  onCreated: (id: number) => void;
}> = ({ onClose, onCreated }) => {
  const [name, setName] = useState('');
  const [source, setSource] = useState<ShoppingV2Source>('empty');
  const [menus, setMenus] = useState<Menu[]>([]);
  const [menuId, setMenuId] = useState<number | ''>('');
  const [subtractFridge, setSubtractFridge] = useState(false);
  const [text, setText] = useState('');
  const [csvText, setCsvText] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  useEffect(() => {
    if (source === 'menu' || source === 'fridge') {
      menuApi.list().then(({ data }) => setMenus(data.results || []));
    }
  }, [source]);

  const submit = async () => {
    setErr('');
    if (!name.trim()) {
      setErr('Введите название.');
      return;
    }
    const payload: CreateListPayload = { name: name.trim(), source };
    if (source === 'menu' || source === 'fridge') {
      if (!menuId) {
        setErr('Выберите меню.');
        return;
      }
      payload.menu_id = Number(menuId);
      payload.subtract_fridge = source === 'fridge' || subtractFridge;
    }
    if (source === 'ai_text') payload.text = text;
    if (source === 'csv') payload.csv_text = csvText;

    setBusy(true);
    try {
      const { data } = await shoppingApi.create(payload);
      onCreated(data.id);
    } catch (e: any) {
      setErr(e?.response?.data?.detail || 'Ошибка создания.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal onClose={onClose} title="Новый список покупок">
      <div className="space-y-3">
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Название" />
        <select
          value={source}
          onChange={(e) => setSource(e.target.value as ShoppingV2Source)}
          className="w-full border border-border rounded-xl px-3 py-2 text-sm"
        >
          <option value="empty">Пустой</option>
          <option value="menu">Из меню</option>
          <option value="fridge">Из меню (минус холодильник)</option>
          {/* MG_NOIMPORT: ai_text & csv removed from create UI */}
        </select>

        {(source === 'menu' || source === 'fridge') && (
          <select
            value={menuId}
            onChange={(e) => setMenuId(e.target.value ? Number(e.target.value) : '')}
            className="w-full border border-border rounded-xl px-3 py-2 text-sm"
          >
            <option value="">— выберите меню —</option>
            {menus.map((m: any) => (
              <option key={m.id} value={m.id}>
                {/* MG_B09 */(() => {
                  const dm = (iso?: string) => (iso && iso.length >= 10) ? `${iso.slice(8,10)}.${iso.slice(5,7)}` : '';
                  const name = (m.creator_name || '').trim();
                  const a = dm(m.start_date), b = dm(m.end_date);
                  const dates = a && b ? `${a}–${b}` : '';
                  return [name, dates].filter(Boolean).join(' ') || `Меню #${m.id}`;
                })()}
              </option>
            ))}
          </select>
        )}

        {source === 'menu' && (
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={subtractFridge} onChange={(e) => setSubtractFridge(e.target.checked)} />
            Вычесть то, что есть в холодильнике
          </label>
        )}

        {source === 'ai_text' && (
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Вставьте произвольный текст со списком…"
            className="w-full border border-border rounded-xl px-3 py-2 text-sm h-28"
          />
        )}

        {source === 'csv' && (
          <textarea
            value={csvText}
            onChange={(e) => setCsvText(e.target.value)}
            placeholder="name,quantity,unit,category"
            className="w-full border border-border rounded-xl px-3 py-2 text-sm h-28 font-mono"
          />
        )}

        {err && <p className="text-red-500 text-sm">{err}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Отмена</Button>
          <Button onClick={submit} disabled={busy}>Создать</Button>
        </div>
      </div>
    </Modal>
  );
};

// ── Модалка доступа ──────────────────────────────────────────────────────────
const AccessModal: React.FC<{ listId: number; onClose: () => void }> = ({ listId, onClose }) => {
  const [accesses, setAccesses] = useState<ShoppingV2Access[]>([]);
  const [email, setEmail] = useState('');
  const [canToggle, setCanToggle] = useState(false);
  const [canExport, setCanExport] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  const load = useCallback(async () => {
    const { data } = await shoppingApi.accesses(listId);
    setAccesses(data);
  }, [listId]);

  useEffect(() => {
    load();
  }, [load]);

  const grant = async () => {
    setErr('');
    if (!email.trim()) {
      setErr('Введите email.');
      return;
    }
    setBusy(true);
    try {
      await shoppingApi.grantAccess(listId, { email: email.trim(), can_toggle: canToggle, can_export: canExport });
      setEmail('');
      setCanToggle(false);
      setCanExport(false);
      load();
    } catch (e: any) {
      setErr(e?.response?.data?.email?.[0] || e?.response?.data?.detail || 'Ошибка.');
    } finally {
      setBusy(false);
    }
  };

  const revoke = async (id: number) => {
    await shoppingApi.revokeAccess(listId, id);
    load();
  };

  return (
    <Modal onClose={onClose} title="Доступ к списку">
      <div className="space-y-3">
        <ul className="space-y-1">
          {accesses.map((a) => (
            <li key={a.id} className="flex items-center gap-2 text-sm border-b border-gray-50 py-1">
              <span className="flex-1">{a.user_name || a.user_email}</span>
              <span className="text-xs text-gray-400">
                {a.can_toggle ? '✓отметка ' : ''}{a.can_export ? '✓печать' : ''}
              </span>
              <button onClick={() => revoke(a.id)} className="text-gray-300 hover:text-red-500">✕</button>
            </li>
          ))}
          {accesses.length === 0 && <p className="text-sm text-gray-400">Доступ ещё не выдан.</p>}
        </ul>

        <div className="pt-2 border-t border-border space-y-2">
          <Input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email пользователя" />
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={canToggle} onChange={(e) => setCanToggle(e.target.checked)} />
            Может отмечать покупки
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={canExport} onChange={(e) => setCanExport(e.target.checked)} />
            Может печатать / экспортировать
          </label>
          {err && <p className="text-red-500 text-sm">{err}</p>}
          <div className="flex justify-end">
            <Button onClick={grant} disabled={busy}>Выдать доступ</Button>
          </div>
        </div>
      </div>
    </Modal>
  );
};

// ── Простая модалка ──────────────────────────────────────────────────────────
const Modal: React.FC<{ title: string; onClose: () => void; children: React.ReactNode }> = ({
  title,
  onClose,
  children,
}) => (
  <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={onClose}>
    <div className="bg-surface rounded-2xl p-5 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-bold text-lg">{title}</h3>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600">✕</button>
      </div>
      {children}
    </div>
  </div>
);
