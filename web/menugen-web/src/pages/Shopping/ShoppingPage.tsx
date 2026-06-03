// MG_SHOP002_web_page — Shopping lists page
import React, { useCallback, useEffect, useState } from 'react';
import { shoppingApi, CreateListPayload } from '../../api/shopping';
import { menuApi } from '../../api/menu';
import { Card } from '../../components/ui/Card';
import { Input } from '../../components/ui/Input';
import { Button } from '../../components/ui/Button';
import { PageSpinner } from '../../components/ui/Spinner';
import { printShoppingList } from '../../utils/printShoppingList';
import type {
  ShoppingV2ListBrief,
  ShoppingV2List,
  ShoppingV2Access,
  ShoppingV2HistoryEntry,
  ShoppingV2Source,
  Menu,
} from '../../types';

const SOURCE_LABEL: Record<ShoppingV2Source, string> = {
  empty: 'Пустой',
  menu: 'Из меню',
  fridge: 'Меню − холодильник',
  ai_text: 'ИИ из текста',
  csv: 'CSV',
};

type Tab = 'active' | 'archived' | 'history';

export const ShoppingPage: React.FC = () => {
  const [tab, setTab] = useState<Tab>('active');
  const [lists, setLists] = useState<ShoppingV2ListBrief[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<ShoppingV2List | null>(null);
  const [history, setHistory] = useState<ShoppingV2HistoryEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [showAccess, setShowAccess] = useState(false);

  const loadLists = useCallback(async (t: Tab) => {
    setLoading(true);
    try {
      if (t === 'history') {
        const { data } = await shoppingApi.history();
        setHistory(data);
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
  }, [tab, loadLists]);

  const loadDetail = useCallback(async (id: number) => {
    const { data } = await shoppingApi.get(id);
    setDetail(data);
    setSelectedId(id);
  }, []);

  const caps = detail?.capabilities;

  const onToggle = async (itemId: number, val: boolean) => {
    if (!detail) return;
    await shoppingApi.toggleItem(detail.id, itemId, val);
    await loadDetail(detail.id);
  };

  const onDeleteList = async () => {
    if (!detail || !window.confirm('Удалить список?')) return;
    await shoppingApi.remove(detail.id);
    setDetail(null);
    setSelectedId(null);
    loadLists(tab);
  };

  const onArchive = async (archived: boolean) => {
    if (!detail) return;
    await shoppingApi.update(detail.id, { is_archived: archived });
    setDetail(null);
    setSelectedId(null);
    loadLists(tab);
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
        {(['active', 'archived', 'history'] as Tab[]).map((t) => (
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
            {t === 'active' ? 'Активные' : t === 'archived' ? 'Архив' : 'История'}
          </button>
        ))}
      </div>

      {loading ? (
        <PageSpinner />
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
  const [newName, setNewName] = useState('');
  const [adding, setAdding] = useState(false);

  const addItem = async () => {
    if (!newName.trim()) return;
    setAdding(true);
    try {
      await shoppingApi.addItem(detail.id, { name: newName.trim() });
      setNewName('');
      onReload();
    } finally {
      setAdding(false);
    }
  };

  const delItem = async (itemId: number) => {
    await shoppingApi.removeItem(detail.id, itemId);
    onReload();
  };

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-bold text-lg">{detail.name}</h2>
        <div className="flex gap-2 flex-wrap">
          {caps?.export && (
            <Button variant="secondary" onClick={onPrint}>🖨 Печать</Button>
          )}
          {caps?.manage && (
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

      <ul className="space-y-1">
        {detail.items.map((it) => (
          <li key={it.id} className="flex items-center gap-2 py-1">
            <input
              type="checkbox"
              checked={it.is_purchased}
              disabled={!caps?.toggle}
              onChange={(e) => onToggle(it.id, e.target.checked)}
              className="w-4 h-4"
            />
            <span className={it.is_purchased ? 'line-through text-gray-400 flex-1' : 'flex-1'}>
              {it.name}
              {it.quantity != null && (
                <span className="text-gray-500 text-sm"> — {it.quantity}{it.unit ? ` ${it.unit}` : ''}</span>
              )}
            </span>
            {caps?.manage && (
              <button onClick={() => delItem(it.id)} className="text-gray-300 hover:text-red-500 text-sm">✕</button>
            )}
          </li>
        ))}
        {detail.items.length === 0 && <p className="text-sm text-gray-400">Список пуст.</p>}
      </ul>

      {caps?.manage && (
        <div className="flex gap-2 mt-3">
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addItem()}
            placeholder="Добавить позицию…"
            className="flex-1 rounded-xl border border-gray-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-tomato/40 focus:border-tomato"
          />
          <Button onClick={addItem} disabled={adding}>+</Button>
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
              <span className="text-gray-400 ml-2">{new Date(h.purchased_at).toLocaleDateString('ru-RU')}</span>
            </span>
            <button onClick={() => del(h.id)} className="text-gray-300 hover:text-red-500">✕</button>
          </li>
        ))}
      </ul>
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
          className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm"
        >
          <option value="empty">Пустой</option>
          <option value="menu">Из меню</option>
          <option value="fridge">Из меню (минус холодильник)</option>
          <option value="ai_text">Импорт из текста (ИИ)</option>
          <option value="csv">Импорт CSV</option>
        </select>

        {(source === 'menu' || source === 'fridge') && (
          <select
            value={menuId}
            onChange={(e) => setMenuId(e.target.value ? Number(e.target.value) : '')}
            className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm"
          >
            <option value="">— выберите меню —</option>
            {menus.map((m: any) => (
              <option key={m.id} value={m.id}>
                {m.title || `Меню #${m.id}`}
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
            className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm h-28"
          />
        )}

        {source === 'csv' && (
          <textarea
            value={csvText}
            onChange={(e) => setCsvText(e.target.value)}
            placeholder="name,quantity,unit,category"
            className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm h-28 font-mono"
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

        <div className="pt-2 border-t border-gray-100 space-y-2">
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
    <div className="bg-white rounded-2xl p-5 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-bold text-lg">{title}</h3>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600">✕</button>
      </div>
      {children}
    </div>
  </div>
);
