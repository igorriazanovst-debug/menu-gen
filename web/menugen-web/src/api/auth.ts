import client from './client';
import type { AuthTokens, RegisterResult, User, UserProfile } from '../types';

// MG_PHONEVERIFY: подтверждение телефона через мессенджер (Telegram/Max)
export type MessengerProvider = 'telegram' | 'max';

export interface PhoneStartResult {
  token: string;
  provider: MessengerProvider;
  deep_link: string;
  bot_username: string;
  expires_at: string;
}

export type PhoneStatus = 'pending' | 'verified' | 'mismatch' | 'consumed' | 'expired';

export interface PhoneStatusResult {
  status: PhoneStatus;
  messenger_phone?: string;
}

export const authApi = {
  login: (email: string, password: string) =>
    client.post<AuthTokens>('/auth/login/', { email, password }),

  // MG_PHONEVERIFY: вход по телефону + паролю (после разовой верификации номера)
  loginPhone: (phone: string, password: string) =>
    client.post<AuthTokens>('/auth/login/', { phone, password }),

  register: (name: string, email: string, password: string, password2: string) =>
    client.post<RegisterResult>('/auth/email/register/', { name, email, password, password2 }),

  // MG_PHONEVERIFY: старт подтверждения телефона — создаёт заявку, отдаёт deep-link
  phoneStart: (phone: string, provider: MessengerProvider) =>
    client.post<PhoneStartResult>('/auth/phone/start/', { phone, provider }),

  // MG_PHONEVERIFY: опрос статуса подтверждения по token
  phoneStatus: (token: string) =>
    client.get<PhoneStatusResult>('/auth/phone/status/', { params: { token } }),

  // MG_PHONEVERIFY: завершение регистрации после подтверждения — выдаёт токены
  phoneRegister: (token: string, name: string, password: string, password2: string) =>
    client.post<AuthTokens>('/auth/phone/register/', { token, name, password, password2 }),

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
