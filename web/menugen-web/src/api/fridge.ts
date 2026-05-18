import client from './client';
import type {
  BarcodeLookupResult,
  FridgeItem,
  FridgeItemDetailsResponse,
  PaginatedResponse,
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

  details: (id: number) => client.get<FridgeItemDetailsResponse>(`/fridge/${id}/details/`),

  scanBarcode: (barcode: string) =>
    client.post<BarcodeLookupResult>('/fridge/scan/', { barcode }),
};
