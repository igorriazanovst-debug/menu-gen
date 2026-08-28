// MG_LEGAL: общий каркас юридических страниц (реквизиты / оферта).
import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { legalApi } from '../../api/legal';
import type { LegalInfo } from '../../types';

export function useLegal() {
  const [data, setData] = useState<LegalInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  useEffect(() => {
    legalApi
      .get()
      .then((r) => setData(r.data))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);
  return { data, loading, error };
}

export const LegalShell: React.FC<{
  title: string;
  logoUrl?: string | null;
  children: React.ReactNode;
}> = ({ title, logoUrl, children }) => (
  <div className="min-h-screen bg-bg text-text flex flex-col items-center py-10 px-4">
    <div className="w-full max-w-2xl">
      <div className="flex flex-col items-center mb-8">
        {/* Логотип: заглушка-помидор, пока не загружен реальный */}
        {logoUrl ? (
          <img src={logoUrl} alt="Логотип" className="h-20 object-contain mb-3" />
        ) : (
          <div className="h-20 w-20 rounded-2xl bg-rice flex items-center justify-center text-5xl mb-3">🍅</div>
        )}
        <h1 className="text-2xl font-bold text-chocolate text-center">{title}</h1>
      </div>

      {children}

      <div className="mt-10 pt-6 border-t border-border text-center text-sm text-gray-400 flex flex-wrap gap-4 justify-center">
        <Link to="/requisites" className="hover:text-tomato">Реквизиты</Link>
        <Link to="/offer" className="hover:text-tomato">Оферта</Link>
        {/* MG_PRIVACY */}
        <Link to="/privacy" className="hover:text-tomato">Политика обработки ПД</Link>
        {/* MG_ACCDEL: адрес должен быть находимым без входа — по нему ходит и
            модерация Google Play, и человек, потерявший доступ к аккаунту. */}
        <Link to="/delete-account" className="hover:text-tomato">Удаление аккаунта</Link>
        <Link to="/" className="hover:text-tomato">На главную</Link>
      </div>
    </div>
  </div>
);
