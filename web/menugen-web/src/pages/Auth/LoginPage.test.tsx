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
import { LoginPage } from './LoginPage';

const makeStore = (o = {}) => configureStore({
  reducer: { auth: authReducer, specialist: specialistReducer },
  preloadedState: { auth: { user: null, loading: false, error: null, initialized: true, ...o } },
});
const renderLogin = (o = {}) => render(<Provider store={makeStore(o)}><MemoryRouter><LoginPage /></MemoryRouter></Provider>);

describe('LoginPage — render', () => {
  it('brand', () => { renderLogin(); expect(screen.getByText('MenuGen')).toBeInTheDocument(); });
  it('email field', () => { renderLogin(); expect(screen.getByLabelText(/email/i)).toBeInTheDocument(); });
  it('password field', () => { renderLogin(); expect(screen.getByLabelText('Пароль')).toBeInTheDocument(); });
  it('button', () => { renderLogin(); expect(screen.getByRole('button', { name: 'Войти' })).toBeInTheDocument(); });
  it('slogan', () => { renderLogin(); expect(screen.getByText('Бесконечный вкусный мир')).toBeInTheDocument(); });
});
describe('LoginPage — validation', () => {
  it('email error', async () => {
    renderLogin();
    await userEvent.type(screen.getByLabelText(/email/i), 'bad');
    await userEvent.type(screen.getByLabelText('Пароль'), 'password123');
    fireEvent.click(screen.getByRole('button', { name: 'Войти' }));
    await waitFor(() => expect(screen.getByText(/корректный email/i)).toBeInTheDocument());
  });
  it('password error', async () => {
    renderLogin();
    await userEvent.type(screen.getByLabelText(/email/i), 'test@example.com');
    await userEvent.type(screen.getByLabelText('Пароль'), 'short');
    fireEvent.click(screen.getByRole('button', { name: 'Войти' }));
    await waitFor(() => expect(screen.getByText(/минимум 8 символов/i)).toBeInTheDocument());
  });
});
describe('LoginPage — state', () => {
  it('shows error', () => { renderLogin({ error: 'Неверные учётные данные' }); expect(screen.getByText('Неверные учётные данные')).toBeInTheDocument(); });
  it('no error default', () => { renderLogin(); expect(screen.queryByText(/неверные/i)).not.toBeInTheDocument(); });
  it('button disabled loading', () => { renderLogin({ loading: true }); expect(screen.getByRole('button', { name: 'Загрузка...' })).toBeDisabled(); });
});
