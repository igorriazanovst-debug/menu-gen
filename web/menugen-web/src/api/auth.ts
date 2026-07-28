import client from './client';
import type { AuthTokens, RegisterResult, User, UserProfile } from '../types';

export const authApi = {
  login: (email: string, password: string) =>
    client.post<AuthTokens>('/auth/login/', { email, password }),

  register: (name: string, email: string, password: string, password2: string) =>
    client.post<RegisterResult>('/auth/email/register/', { name, email, password, password2 }),

  // MG_EMAILVERIFY
  verifyEmail: (token: string) => client.post<AuthTokens>('/auth/email/verify/', { token }),
  resendVerification: (email: string) =>
    client.post<{ detail: string; verify_link?: string }>('/auth/email/resend/', { email }),

  logout: (refresh: string) =>
    client.post('/auth/logout/', { refresh }),

  me: () => client.get<User>('/users/me/'),

  updateMe: (data: Partial<Omit<User, 'profile'>> & { profile?: Partial<UserProfile> }) =>
    client.patch<User>('/users/me/', data),
};
