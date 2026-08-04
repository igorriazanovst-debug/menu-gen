// MG_GALLERY: сбор всех изображений рецепта в один список для галереи.
//
// Основное фото (image_url) — обложка и первый слайд. Остальные ракурсы лежат
// в gallery: их загружает администратор в карточке рецепта, порядок задаётся там же.
//
// Фото «я приготовил» (made_photos) сюда не входят: они личные, у каждого
// пользователя свои, и живут в отдельном блоке с кнопкой загрузки.
import type { Recipe, RecipeGalleryPhoto } from '../types';

export interface GalleryImage {
  url: string;
  /** Необязательная подпись под фото (задаётся в админке). */
  caption?: string;
}

type RecipeLike = Pick<Recipe, 'image_url'> & { gallery?: RecipeGalleryPhoto[] | null };

export function collectRecipeImages(recipe: RecipeLike | null | undefined): GalleryImage[] {
  if (!recipe) return [];

  const images: GalleryImage[] = [];
  const seen = new Set<string>();

  const add = (raw: unknown, caption?: string) => {
    const url = typeof raw === 'string' ? raw.trim() : '';
    // Дубли отбрасываем: обложку иногда дублируют и в галерее.
    if (!url || seen.has(url)) return;
    seen.add(url);
    images.push(caption ? { url, caption } : { url });
  };

  add(recipe.image_url);
  (recipe.gallery ?? []).forEach((photo) => add(photo?.url, photo?.caption));

  return images;
}
