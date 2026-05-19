import client from './client';
import type {
  BarcodeLookupResult,
  FridgeHistoryItem,
  FridgeItem,
  FridgeItemDetailsResponse,
  PaginatedResponse,
  Product,
  ProductCategory,
} from '../types';

export const fridgeApi = {
  list: () => client.get<PaginatedResponse<FridgeItem>>('/fridge/'),

  create: (data: {
    name: string;
    quantity: number;
    unit: string;
    expiry_date: string;
    product?: number | null;
  }) => client.post<FridgeItem>('/fridge/', data),

  delete: (id: number) => client.delete(`/fridge/${id}/`),

  details: (id: number) =>
    client.get<FridgeItemDetailsResponse>(`/fridge/${id}/details/`),

  scanBarcode: (barcode: string) =>
    client.post<BarcodeLookupResult>('/fridge/scan/', { barcode }),

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
