import client from './client';
import type { PaginatedResponse, Recipe } from '../types';

export const recipesApi = {
  list: (params?: { search?: string; category?: string; country?: string; page?: number }) =>
    client.get<PaginatedResponse<Recipe>>('/recipes/', { params }),

  get: (id: number) => client.get<Recipe>(`/recipes/${id}/`),

  create: (data: Partial<Recipe>) => client.post<Recipe>('/recipes/', data),

  update: (id: number, data: Partial<Recipe>) =>
    client.patch<Recipe>(`/recipes/${id}/`, data),

  delete: (id: number) => client.delete(`/recipes/${id}/`),

  uploadMedia: (file: File, mediaType: 'image' | 'video') => {
    const form = new FormData();
    form.append('file', file);
    form.append('media_type', mediaType);
    return client.post<{ url: string }>('/recipes/upload-media/', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  countries: () => client.get<string[]>('/recipes/countries/'),
};
