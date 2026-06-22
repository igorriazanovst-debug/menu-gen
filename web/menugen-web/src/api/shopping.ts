// MG_SHOP002_web_api — shopping lists v2 client
import client from './client';
import type {
  ShoppingV2List,
  ShoppingV2ListBrief,
  ShoppingV2Item,
  ShoppingV2Access,
  ShoppingV2ExportData,
  ShoppingV2HistoryEntry,
  ShoppingV2Source,
  ShoppingV2RubricResponse,
  ShoppingV2RubricResult,
  ShoppingV2PendingList,
} from '../types';

export interface CreateListPayload {
  name: string;
  source?: ShoppingV2Source;
  menu_id?: number;
  subtract_fridge?: boolean;
  text?: string;
  csv_text?: string;
}

// MG_RUBRIC004: add-item payload with rubricator links.
export interface AddItemPayload {
  name: string;
  quantity?: number | null;
  unit?: string;
  product_id?: number | null;
  category_slug?: string;
  price_per_unit?: number | null; // MG_RUBRIC008
}

export interface GrantAccessPayload {
  user_id?: number;
  email?: string;
  can_toggle?: boolean;
  can_export?: boolean;
}

// MG_RUBRICBROWSE
export interface RubricCategory {
  slug: string;
  name_ru: string;
  icon?: string;
  color?: string;
  sort_order?: number;
}

export const shoppingApi = {
  lists: (archived = false) =>
    client.get<ShoppingV2ListBrief[]>('/shopping/lists/', {
      params: { archived: archived ? 'true' : undefined },
    }),

  // MG_T09: per-tab list counts.
  counts: () =>
    client.get<{ active: number; pending: number; archived: number; history: number }>(
      '/shopping/counts/',
    ),

  get: (listId: number) =>
    client.get<ShoppingV2List & { capabilities: ShoppingV2List['capabilities'] }>(
      `/shopping/lists/${listId}/`,
    ),

  create: (payload: CreateListPayload) =>
    client.post<ShoppingV2List>('/shopping/lists/', payload),

  update: (listId: number, payload: { name?: string; is_archived?: boolean }) =>
    client.patch<ShoppingV2List>(`/shopping/lists/${listId}/`, payload),

  remove: (listId: number) => client.delete(`/shopping/lists/${listId}/`),

  // MG_RUBRIC004_addItem
  addItem: (listId: number, item: AddItemPayload) =>
    client.post<ShoppingV2Item>(`/shopping/lists/${listId}/items/`, item),

  updateItem: (listId: number, itemId: number, item: Partial<ShoppingV2Item>) =>
    client.patch<ShoppingV2Item>(`/shopping/lists/${listId}/items/${itemId}/`, item),

  removeItem: (listId: number, itemId: number) =>
    client.delete(`/shopping/lists/${listId}/items/${itemId}/`),

  // MG_SHOP2FRIDGE: removeFromFridge confirms un-checking an item that was
  // already added to the fridge (the linked fridge item is removed).
  toggleItem: (
    listId: number,
    itemId: number,
    isPurchased?: boolean,
    removeFromFridge?: boolean,
  ) =>
    client.patch<ShoppingV2Item>(
      `/shopping/lists/${listId}/items/${itemId}/toggle/`,
      {
        ...(isPurchased === undefined ? {} : { is_purchased: isPurchased }),
        ...(removeFromFridge ? { remove_from_fridge: true } : {}),
      },
    ),

  // MG_SHOP2FRIDGE: push purchased items into the family fridge.
  addToFridge: (listId: number, itemIds?: number[]) =>
    client.post<{ added: number; skipped: number }>(
      `/shopping/lists/${listId}/add-to-fridge/`,
      itemIds && itemIds.length ? { item_ids: itemIds } : {},
    ),

  accesses: (listId: number) =>
    client.get<ShoppingV2Access[]>(`/shopping/lists/${listId}/access/`),

  grantAccess: (listId: number, payload: GrantAccessPayload) =>
    client.post<ShoppingV2Access>(`/shopping/lists/${listId}/access/`, payload),

  revokeAccess: (listId: number, accessId: number) =>
    client.delete(`/shopping/lists/${listId}/access/`, { data: { access_id: accessId } }),

  // MG_SHAREACCEPT: shares awaiting the current user's decision.
  pending: () => client.get<ShoppingV2PendingList[]>('/shopping/pending/'),

  respond: (listId: number, action: 'accept' | 'reject') =>
    client.post(`/shopping/lists/${listId}/respond/`, { action }),

  exportData: (listId: number) =>
    client.get<ShoppingV2ExportData>(`/shopping/lists/${listId}/export/`),

  history: () => client.get<ShoppingV2HistoryEntry[]>('/shopping/history/'),

  addHistory: (entry: { name: string; quantity?: number; unit?: string; category?: string }) =>
    client.post<ShoppingV2HistoryEntry>('/shopping/history/', entry),

  removeHistory: (entryId: number) =>
    client.delete('/shopping/history/', { data: { entry_id: entryId } }),

  // MG_RUBRIC004: rubricator search; classify=1 asks AI for a category when no match.
  rubricSearch: (q: string, classify = false) =>
    client.get<ShoppingV2RubricResponse>('/shopping/rubric/search/', {
      params: { q, classify: classify ? '1' : undefined },
    }),

  // MG_RUBRICBROWSE: active categories for the browse picker (not premium-gated).
  rubricCategories: () =>
    client.get<RubricCategory[]>('/shopping/rubric/categories/'),

  // MG_RUBRICBROWSE: products in a category for the browse picker.
  rubricBrowse: (categorySlug: string) =>
    client.get<{ category: string; results: ShoppingV2RubricResult[] }>(
      '/shopping/rubric/browse/',
      { params: { category: categorySlug || undefined } },
    ),
};
