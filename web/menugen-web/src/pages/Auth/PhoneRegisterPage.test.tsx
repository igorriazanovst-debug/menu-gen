import '@testing-library/jest-dom';

jest.mock('../../api/auth');

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Provider } from 'react-redux';
import { MemoryRouter } from 'react-router-dom';
import { configureStore } from '@reduxjs/toolkit';
import authReducer from '../../store/slices/authSlice';
import specialistReducer from '../../store/specialistSlice';
import { PhoneRegisterPage } from './PhoneRegisterPage';
import { authApi } from '../../api/auth';

const mockAuthApi = authApi as jest.Mocked<typeof authApi>;

const makeStore = () => configureStore({
  reducer: { auth: authReducer, specialist: specialistReducer },
  preloadedState: { auth: { user: null, loading: false, error: null, initialized: true } },
});
const renderPage = () =>
  render(
    <Provider store={makeStore()}>
      <MemoryRouter><PhoneRegisterPage /></MemoryRouter>
    </Provider>,
  );

describe('PhoneRegisterPage — step 1', () => {
  beforeEach(() => { jest.clearAllMocks(); });

  it('renders brand + phone field + Telegram option', () => {
    renderPage();
    expect(screen.getByText('MenuGen')).toBeInTheDocument();
    expect(screen.getByLabelText('Телефон')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Telegram/i })).toBeInTheDocument();
  });

  it('validates short phone', async () => {
    renderPage();
    await userEvent.type(screen.getByLabelText('Телефон'), '123');
    fireEvent.click(screen.getByRole('button', { name: 'Продолжить' }));
    await waitFor(() => expect(screen.getByText(/корректный номер/i)).toBeInTheDocument());
    expect(mockAuthApi.phoneStart).not.toHaveBeenCalled();
  });

  it('valid phone starts verification and shows bot link', async () => {
    mockAuthApi.phoneStart.mockResolvedValueOnce({
      data: {
        token: 'tok', provider: 'telegram',
        deep_link: 'https://t.me/menuGEN_auth_bot?start=tok',
        bot_username: 'menuGEN_auth_bot', expires_at: '2026-01-01T00:00:00Z',
      },
    } as any);
    mockAuthApi.phoneStatus.mockResolvedValue({ data: { status: 'pending' } } as any);

    renderPage();
    await userEvent.type(screen.getByLabelText('Телефон'), '+79123456789');
    fireEvent.click(screen.getByRole('button', { name: 'Продолжить' }));

    await waitFor(() => expect(mockAuthApi.phoneStart).toHaveBeenCalledWith('+79123456789', 'telegram'));
    await waitFor(() => expect(screen.getByText(/Подтвердите номер/i)).toBeInTheDocument());
    const link = screen.getByRole('link', { name: /Открыть бота/i });
    expect(link).toHaveAttribute('href', 'https://t.me/menuGEN_auth_bot?start=tok');
  });

  it('shows conflict when phone already registered', async () => {
    mockAuthApi.phoneStart.mockRejectedValueOnce({ response: { data: { code: 'phone_taken' } } });
    renderPage();
    await userEvent.type(screen.getByLabelText('Телефон'), '+79123456789');
    fireEvent.click(screen.getByRole('button', { name: 'Продолжить' }));
    await waitFor(() => expect(screen.getByText(/уже есть/i)).toBeInTheDocument());
  });
});
