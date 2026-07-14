import client from './client';
import type { PaginatedResponse, Recipe } from '../types';

export const recipesApi = {
  list: (params?: { search?: string; category?: string; country?: string; food_group?: string; page?: number; page_size?: number }) =>
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

  // MG_MADEPHOTO: фото приготовленного блюда пользователем.
  madePhotos: (recipeId: number) =>
    client.get<MadePhoto[]>(`/recipes/${recipeId}/made-photos/`),
  addMadePhoto: (recipeId: number, imageB64: string) =>
    client.post<MadePhoto>(`/recipes/${recipeId}/made-photos/`, { image_b64: imageB64 }),
  deleteMadePhoto: (recipeId: number, photoId: number) =>
    client.delete(`/recipes/${recipeId}/made-photos/${photoId}/`),
};

export interface MadePhoto {
  id: number;
  image_url: string;
  created_at: string;
}
