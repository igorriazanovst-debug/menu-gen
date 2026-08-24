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
    // MG_FAMBARCODE: код отсканированной упаковки. Если товар не опознался и
    // название вписали руками, сервер запомнит его для этой семьи.
    barcode?: string;
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

  // freemium: поиск по общему каталогу продуктов (КБЖУ на 100 г) — открыт free,
  // используется ручным добавлением продукта в дневник. Endpoint ждёт ?q=.
  // Ответ пагинирован DRF ({results:[...]}); распаковываем (с запасом на голый массив).
  searchProducts: async (q: string): Promise<Product[]> => {
    const { data } = await client.get<PaginatedResponse<Product> | Product[]>(
      '/fridge/products/search/', { params: { q } },
    );
    return Array.isArray(data) ? data : (data.results ?? []);
  },

  products: (params?: { category?: string | number; seed?: boolean; own?: boolean }) => {
    const query: Record<string, string> = {};
    if (params?.category != null) query.category = String(params.category);
    if (params?.seed) query.seed = '1';
    if (params?.own) query.own = '1';
    return client.get<Product[]>('/fridge/products/', { params: query });
  },

  // MG_PRODOWN: создать пользовательский продукт (owner=текущий, виден только ему).
  createProduct: (data: {
    name: string;
    calories_per_100g?: number | null;
    nutrition?: Record<string, number>;
    category_id?: number | null;
    default_unit?: string;
  }) => client.post<Product>('/fridge/products/', data),

  // MG_MYPRODUCTS: правка и удаление своего продукта. Каталожные защищены на
  // сервере — он ответит 403, даже если что-то дойдёт сюда по ошибке.
  updateProduct: (
    id: number,
    data: {
      name?: string;
      calories_per_100g?: number | null;
      nutrition?: Record<string, number>;
      category_id?: number | null;
      default_unit?: string;
    },
  ) => client.patch<Product>(`/fridge/products/${id}/`, data),

  deleteProduct: (id: number) => client.delete(`/fridge/products/${id}/`),

  history: (limit = 40) =>
    client.get<FridgeHistoryItem[]>('/fridge/products/history/', {
      params: { limit },
    }),
};
