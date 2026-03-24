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
};
