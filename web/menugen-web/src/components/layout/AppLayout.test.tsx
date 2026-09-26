import '@testing-library/jest-dom';

jest.mock('../../api/auth');

/*
 * Индикатор синхронизации подменяется целиком. Он тянет очередь, та —
 * `api/shopping`, а тот внутри `src/api` подключает клиент как `./client` —
 * путь, который правила подмены в `moduleNameMapper` не ловят (они написаны на
 * `../api/client`). Расширять правило на `./client` нельзя: тогда его поймает и
 * `api/client.test.ts`, который проверяет как раз настоящий клиент. Здесь
 * индикатор всё равно не проверяется — речь про выдвижную панель.
 */
jest.mock('./SyncIndicator', () => ({ SyncIndicator: () => null }));

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { Provider } from 'react-redux';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { configureStore } from '@reduxjs/toolkit';
import authReducer from '../../store/slices/authSlice';
import specialistReducer from '../../store/specialistSlice';
import { AppLayout } from './AppLayout';

/**
 * MG_WEBMOBILE: оболочка на узком экране.
 *
 * Проверяется поведение, а не вёрстка: ширину и точку перелома задаёт Tailwind,
 * и в тестах медиазапросы не работают — там нет настоящего окна. Зато можно
 * проверить то, из-за чего сайт был непригоден на телефоне: кнопка меню есть,
 * панель открывается и — главное — закрывается. Незакрывающаяся панель хуже
 * отсутствующей: она накрывает страницу, на которую человек только что перешёл.
 */
const makeStore = (user: any = null) =>
  configureStore({
    reducer: { auth: authReducer, specialist: specialistReducer },
    preloadedState: { auth: { user, loading: false, error: null, initialized: true } },
  });

const renderLayout = () =>
  render(
    <Provider store={makeStore(null)}>
      <MemoryRouter initialEntries={['/menu']}>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/menu" element={<div>Страница меню</div>} />
            <Route path="/recipes" element={<div>Страница рецептов</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </Provider>,
  );

describe('AppLayout', () => {
  it('содержимое страницы на месте', () => {
    renderLayout();
    expect(screen.getByText('Страница меню')).toBeInTheDocument();
  });

  it('кнопка меню есть', () => {
    renderLayout();
    expect(screen.getByLabelText('Открыть меню')).toBeInTheDocument();
  });

  it('затемнение появляется только при открытой панели', () => {
    renderLayout();
    expect(screen.queryByLabelText('Закрыть меню')).not.toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('Открыть меню'));

    expect(screen.getByLabelText('Закрыть меню')).toBeInTheDocument();
  });

  it('нажатие мимо меню его закрывает', () => {
    renderLayout();
    fireEvent.click(screen.getByLabelText('Открыть меню'));

    fireEvent.click(screen.getByLabelText('Закрыть меню'));

    expect(screen.queryByLabelText('Закрыть меню')).not.toBeInTheDocument();
  });

  it('переход по ссылке закрывает панель', () => {
    renderLayout();
    fireEvent.click(screen.getByLabelText('Открыть меню'));

    fireEvent.click(screen.getByText('Рецепты'));

    expect(screen.getByText('Страница рецептов')).toBeInTheDocument();
    expect(screen.queryByLabelText('Закрыть меню')).not.toBeInTheDocument();
  });

  it('кнопка меню сообщает своё состояние', () => {
    renderLayout();
    const button = screen.getByLabelText('Открыть меню');
    expect(button).toHaveAttribute('aria-expanded', 'false');

    fireEvent.click(button);

    expect(screen.getByLabelText('Открыть меню')).toHaveAttribute('aria-expanded', 'true');
  });
});
