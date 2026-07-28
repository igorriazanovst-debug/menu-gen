// MG_PHOTOZOOM: полноэкранный просмотр изображения (по клику/тапу).
import React, { useEffect } from 'react';

export const ImageLightbox: React.FC<{ src: string; alt?: string; onClose: () => void }> = ({
  src,
  alt,
  onClose,
}) => {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-[80] bg-black/90 flex items-center justify-center p-4" onClick={onClose}>
      <img
        src={src}
        alt={alt || ''}
        className="max-w-full max-h-full object-contain"
        onClick={(e) => e.stopPropagation()}
      />
      <button
        onClick={onClose}
        className="absolute top-3 right-5 text-white/80 hover:text-white text-4xl leading-none"
        aria-label="Закрыть"
      >
        ×
      </button>
    </div>
  );
};
