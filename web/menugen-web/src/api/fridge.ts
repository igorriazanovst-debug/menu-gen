import client from './client';
import type {
  BarcodeLookupResult,
  FridgeHistoryItem,
  FridgeItem,
  FridgeItemDetailsResponse,
  PaginatedResponse,
  Product,
  ProductCategory,
  RecognizePhotoResponse,
} from '../types';

export const fridgeApi = {
  list: () => client.get<PaginatedResponse<FridgeItem>>('/fridge/'),

  create: (data: {
    name: string;
    quantity: number;
    unit: string;
    expiry_date: string;
    product?: number | null;
    category_slug?: string; // MG_B02CAT
  }) => client.post<FridgeItem>('/fridge/', data),

  delete: (id: number) => client.delete(`/fridge/${id}/`),

  // MG_B03: edit an existing fridge item (PATCH).
  update: (
    id: number,
    data: {
      name?: string;
      quantity?: number;
      unit?: string;
      expiry_date?: string;
      category_slug?: string;
      product?: number | null;
    },
  ) => client.patch<FridgeItem>(`/fridge/${id}/`, data),

  details: (id: number) =>
    client.get<FridgeItemDetailsResponse>(`/fridge/${id}/details/`),

  recognizePhoto: (imageB64: string, mode: 'single' | 'multi') =>
    client.post<RecognizePhotoResponse>('/fridge/recognize-photo/', {
      image_b64: imageB64,
      mode,
    }),

  scanBarcode: (barcode: string) =>
    client.post<BarcodeLookupResult>('/fridge/scan/', { barcode }),

  // ── MG-610 ──────────────────────────────────────────────────────────────
  deleteExpired: (payload: { ids?: number[]; all?: boolean; drop_history?: boolean }) =>
    client.post<{ deleted: number }>('/fridge/expired/delete/', payload),

  deleteHistoryEntry: (name: string, dropFridge = false) =>
    client.delete<{ deleted: number }>(
      `/fridge/products/history/${encodeURIComponent(name)}/`,
      { params: dropFridge ? { drop_fridge: 1 } : {} },
    ),

  // ── MG-609 ──────────────────────────────────────────────────────────────
  categories: () =>
    client.get<ProductCategory[]>('/fridge/categories/'),

  products: (params?: { category?: string | number; seed?: boolean }) => {
    const query: Record<string, string> = {};
    if (params?.category != null) query.category = String(params.category);
    if (params?.seed) query.seed = '1';
    return client.get<Product[]>('/fridge/products/', { params: query });
  },

  history: (limit = 40) =>
    client.get<FridgeHistoryItem[]>('/fridge/products/history/', {
      params: { limit },
    }),
};
