import client from './client';
import type { AuthTokens, User } from '../types';

export const authApi = {
  login: (email: string, password: string) =>
    client.post<AuthTokens>('/auth/login/', { email, password }),

  register: (name: string, email: string, password: string, password2: string) =>
    client.post<AuthTokens>('/auth/email/register/', { name, email, password, password2 }),

  logout: (refresh: string) =>
    client.post('/auth/logout/', { refresh }),

  me: () => client.get<User>('/users/me/'),

  updateMe: (data: Partial<User> & { profile?: Partial<User['profile']> }) =>
    client.patch<User>('/users/me/', data),
};
