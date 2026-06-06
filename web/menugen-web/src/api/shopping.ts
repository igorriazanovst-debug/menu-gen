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

export const shoppingApi = {
  lists: (archived = false) =>
    client.get<ShoppingV2ListBrief[]>('/shopping/lists/', {
      params: { archived: archived ? 'true' : undefined },
    }),

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

  toggleItem: (listId: number, itemId: number, isPurchased?: boolean) =>
    client.patch<ShoppingV2Item>(
      `/shopping/lists/${listId}/items/${itemId}/toggle/`,
      isPurchased === undefined ? {} : { is_purchased: isPurchased },
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
};
