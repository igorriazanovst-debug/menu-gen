import '@testing-library/jest-dom';

jest.mock('../../api/auth');

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { Provider } from 'react-redux';
import { MemoryRouter } from 'react-router-dom';
import { configureStore } from '@reduxjs/toolkit';
import authReducer from '../../store/slices/authSlice';
import specialistReducer from '../../store/specialistSlice';
import { Sidebar } from './Sidebar';

const makeStore = (user: any = null) => configureStore({
  reducer: { auth: authReducer, specialist: specialistReducer },
  preloadedState: { auth: { user, loading: false, error: null, initialized: true } },
});
const renderSidebar = (user: any = null) => render(<Provider store={makeStore(user)}><MemoryRouter><Sidebar /></MemoryRouter></Provider>);
const mockUser = { id: 1, name: 'Иван Иванов', email: 'ivan@example.com', profile: {} };

describe('Sidebar', () => {
  it('brand', () => { renderSidebar(); expect(screen.getByText('MenuGen')).toBeInTheDocument(); });
  it('nav links', () => { renderSidebar(); ['Главная','Меню','Рецепты','Семья','Дневник','Подписка','Профиль'].forEach(l => expect(screen.getByText(l)).toBeInTheDocument()); });
  it('logout button', () => { renderSidebar(); expect(screen.getByText(/выйти/i)).toBeInTheDocument(); });
  it('user name', () => { renderSidebar(mockUser); expect(screen.getByText('Иван Иванов')).toBeInTheDocument(); });
  it('no crash null user', () => { renderSidebar(null); expect(screen.getByText('MenuGen')).toBeInTheDocument(); });
  it('logout clickable', () => { renderSidebar(mockUser); fireEvent.click(screen.getByText(/выйти/i)); });
});
