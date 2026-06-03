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
} from '../types';

export interface CreateListPayload {
  name: string;
  source?: ShoppingV2Source;
  menu_id?: number;
  subtract_fridge?: boolean;
  text?: string;
  csv_text?: string;
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

  addItem: (listId: number, item: Partial<ShoppingV2Item>) =>
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

  exportData: (listId: number) =>
    client.get<ShoppingV2ExportData>(`/shopping/lists/${listId}/export/`),

  history: () => client.get<ShoppingV2HistoryEntry[]>('/shopping/history/'),

  addHistory: (entry: { name: string; quantity?: number; unit?: string; category?: string }) =>
    client.post<ShoppingV2HistoryEntry>('/shopping/history/', entry),

  removeHistory: (entryId: number) =>
    client.delete('/shopping/history/', { data: { entry_id: entryId } }),
};
