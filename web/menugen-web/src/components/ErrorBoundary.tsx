import React from 'react';

interface Props { children: React.ReactNode }
interface State { hasError: boolean }

/**
 * Ловит ошибки рендера страницы, чтобы падение одной страницы не сносило всё
 * приложение в «тёмный экран». Сайдбар/навигация остаются живыми.
 */
export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: unknown, info: unknown): void {
    // eslint-disable-next-line no-console
    console.error('ErrorBoundary:', error, info);
  }

  private reset = () => {
    this.setState({ hasError: false });
    window.location.assign('/');
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 text-center">
          <p className="text-lg font-semibold text-text mb-1">Что-то пошло не так</p>
          <p className="text-sm text-muted mb-4">Страница не загрузилась. Попробуйте обновить или вернуться на главную.</p>
          <button
            onClick={this.reset}
            className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-fg transition hover:opacity-90"
          >
            На главную
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
