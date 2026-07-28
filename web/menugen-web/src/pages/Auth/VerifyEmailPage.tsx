// MG_EMAILVERIFY: страница перехода по ссылке из письма — подтверждает e-mail
// и логинит. /verify-email?token=...
import React, { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAppDispatch } from '../../hooks/useAppDispatch';
import { verifyEmail } from '../../store/slices/authSlice';

export const VerifyEmailPage: React.FC = () => {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [state, setState] = useState<'checking' | 'ok' | 'error'>('checking');
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return; // StrictMode: не дёргаем дважды
    ran.current = true;
    const token = params.get('token') || '';
    if (!token) { setState('error'); return; }
    dispatch(verifyEmail(token))
      .unwrap()
      .then(() => {
        setState('ok');
        setTimeout(() => navigate('/'), 1200);
      })
      .catch(() => setState('error'));
  }, [dispatch, navigate, params]);

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-4">
      <div className="w-full max-w-sm text-center">
        <div className="text-6xl mb-3">🍅</div>
        <div className="bg-surface rounded-2xl shadow-sm border border-border p-8">
          {state === 'checking' && (
            <>
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-tomato mx-auto mb-3" />
              <p className="text-muted text-sm">Подтверждаем e-mail…</p>
            </>
          )}
          {state === 'ok' && (
            <>
              <div className="text-5xl mb-3">✅</div>
              <h2 className="text-xl font-semibold text-text mb-1">E-mail подтверждён</h2>
              <p className="text-muted text-sm">Входим в аккаунт…</p>
            </>
          )}
          {state === 'error' && (
            <>
              <div className="text-5xl mb-3">⚠️</div>
              <h2 className="text-xl font-semibold text-text mb-1">Ссылка недействительна</h2>
              <p className="text-muted text-sm">
                Возможно, срок действия истёк. Войдите и запросите письмо заново.
              </p>
              <p className="text-sm text-muted mt-5">
                <Link to="/login" className="text-tomato font-medium hover:underline">Перейти ко входу</Link>
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
