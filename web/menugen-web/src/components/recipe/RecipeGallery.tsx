// MG_GALLERY: галерея фото рецепта с листанием кликом по краям изображения.
//
// Раскладка кликов: левая треть — предыдущее фото, правая треть — следующее,
// середина — открыть во весь экран. Стрелки показываем всегда (не только на
// hover): на сенсорных экранах hover не существует, а подсказка нужна.
//
// При одном изображении зоны листания не создаются — клик по всей площади
// открывает просмотр, как было до галереи.
import React, { useEffect, useState } from 'react';
import type { GalleryImage } from '../../utils/recipeImages';

interface Props {
  images: GalleryImage[];
  alt: string;
  /** Открыть полноэкранный просмотр текущего фото. */
  onZoom?: (image: GalleryImage) => void;
  className?: string;
}

export const RecipeGallery: React.FC<Props> = ({ images, alt, onZoom, className }) => {
  const [index, setIndex] = useState(0);

  // Рецепт в модальном окне может смениться без размонтирования — иначе
  // остались бы на слайде №3 у рецепта с одним фото.
  useEffect(() => setIndex(0), [images]);

  if (images.length === 0) return null;

  const safeIndex = Math.min(index, images.length - 1);
  const current = images[safeIndex];
  const many = images.length > 1;

  const step = (delta: number) => (e: React.MouseEvent) => {
    e.stopPropagation();
    setIndex((i) => (i + delta + images.length) % images.length);
  };

  return (
    <div className={`relative bg-gray-50 ${className ?? ''}`}>
      <img
        src={current.url}
        alt={current.caption ? `${alt} — ${current.caption}` : alt}
        onClick={() => onZoom?.(current)}
        className="w-full object-contain cursor-zoom-in select-none"
      />

      {many && (
        <>
          <button
            type="button"
            onClick={step(-1)}
            aria-label="Предыдущее фото"
            className="absolute left-0 top-0 h-full w-1/3 flex items-center justify-start pl-2
                       text-white/0 hover:text-white/90 transition cursor-pointer"
          >
            <span className="text-3xl drop-shadow-lg bg-black/30 rounded-full w-9 h-9 flex items-center justify-center">
              ‹
            </span>
          </button>
          <button
            type="button"
            onClick={step(1)}
            aria-label="Следующее фото"
            className="absolute right-0 top-0 h-full w-1/3 flex items-center justify-end pr-2
                       text-white/0 hover:text-white/90 transition cursor-pointer"
          >
            <span className="text-3xl drop-shadow-lg bg-black/30 rounded-full w-9 h-9 flex items-center justify-center">
              ›
            </span>
          </button>

          <div className="absolute top-2 right-2 px-2 py-0.5 rounded-full bg-black/50 text-white text-xs">
            {safeIndex + 1} / {images.length}
          </div>

          {/* Точки поднимаем над подписью, иначе они бы её перекрывали. */}
          <div className={`absolute left-0 right-0 flex justify-center gap-1.5 ${current.caption ? 'bottom-9' : 'bottom-2'}`}>
            {images.map((img, i) => (
              <button
                key={img.url}
                type="button"
                aria-label={`Фото ${i + 1}`}
                aria-current={i === safeIndex}
                onClick={(e) => {
                  e.stopPropagation();
                  setIndex(i);
                }}
                className={`w-2 h-2 rounded-full transition ${
                  i === safeIndex ? 'bg-white' : 'bg-white/50 hover:bg-white/80'
                }`}
              />
            ))}
          </div>
        </>
      )}

      {current.caption && (
        <div className="absolute bottom-0 left-0 right-0 px-3 py-1.5 bg-black/45 text-white text-xs text-center">
          {current.caption}
        </div>
      )}
    </div>
  );
};
