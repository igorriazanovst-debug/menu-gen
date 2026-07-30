// Фабрика мока: реальный api/legal не загружается, поэтому Jest не тянет
// ESM-сборку axios (через api/client).
jest.mock('../../api/legal', () => ({
  legalApi: { get: jest.fn() },
}));

import '@testing-library/jest-dom';

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PrivacyPage } from './PrivacyPage';
import { legalApi } from '../../api/legal';

const mockLegalApi = legalApi as jest.Mocked<typeof legalApi>;

const renderPage = () =>
  render(
    <MemoryRouter>
      <PrivacyPage />
    </MemoryRouter>,
  );

describe('PrivacyPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('показывает текст политики с бэкенда', async () => {
    mockLegalApi.get.mockResolvedValueOnce({
      data: { privacy_text: '1. ОБЩИЕ ПОЛОЖЕНИЯ — текст политики', logo_url: null },
    } as any);
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/ОБЩИЕ ПОЛОЖЕНИЯ/)).toBeInTheDocument(),
    );
    expect(screen.getByText('Политика обработки персональных данных')).toBeInTheDocument();
  });

  it('сообщает об ошибке загрузки', async () => {
    mockLegalApi.get.mockRejectedValueOnce(new Error('network'));
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/Не удалось загрузить политику/)).toBeInTheDocument(),
    );
  });
});
