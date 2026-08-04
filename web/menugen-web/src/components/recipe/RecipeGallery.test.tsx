// MG_GALLERY: сбор фото рецепта и листание кликом по краям.
import React from 'react';
// В проекте jest-dom не подключён глобально (setupTests.js только про
// TextEncoder), поэтому матчеры вроде toBeInTheDocument импортируем здесь.
import '@testing-library/jest-dom';
import { render, screen, fireEvent } from '@testing-library/react';
import { RecipeGallery } from './RecipeGallery';
import { collectRecipeImages } from '../../utils/recipeImages';

const images = [
  { url: '/media/cover.png' },
  { url: '/media/side.png', caption: 'Вид сбоку' },
  { url: '/media/cut.png' },
];

describe('collectRecipeImages', () => {
  it('ставит обложку первой, затем фото галереи по порядку', () => {
    const result = collectRecipeImages({
      image_url: '/media/cover.png',
      gallery: [
        { id: 1, url: '/media/a.png', caption: 'A' },
        { id: 2, url: '/media/b.png' },
      ],
    } as any);

    expect(result.map((i) => i.url)).toEqual(['/media/cover.png', '/media/a.png', '/media/b.png']);
    expect(result[1].caption).toBe('A');
  });

  it('отбрасывает дубль обложки в галерее', () => {
    const result = collectRecipeImages({
      image_url: '/media/cover.png',
      gallery: [{ id: 1, url: '/media/cover.png' }],
    } as any);

    expect(result).toHaveLength(1);
  });

  it('пропускает пустые адреса', () => {
    const result = collectRecipeImages({
      image_url: '   ',
      gallery: [{ id: 1, url: '' }, { id: 2, url: '/media/ok.png' }],
    } as any);

    expect(result.map((i) => i.url)).toEqual(['/media/ok.png']);
  });

  it('рецепт без фото даёт пустой список', () => {
    expect(collectRecipeImages({ image_url: undefined } as any)).toEqual([]);
    expect(collectRecipeImages(null)).toEqual([]);
  });
});

describe('RecipeGallery', () => {
  it('без фото ничего не рисует', () => {
    const { container } = render(<RecipeGallery images={[]} alt="Блюдо" />);
    expect(container).toBeEmptyDOMElement();
  });

  it('при одном фото стрелок нет', () => {
    render(<RecipeGallery images={[images[0]]} alt="Блюдо" />);

    expect(screen.queryByLabelText('Следующее фото')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Предыдущее фото')).not.toBeInTheDocument();
  });

  it('клик справа листает вперёд, слева — назад', () => {
    render(<RecipeGallery images={images} alt="Блюдо" />);
    const img = () => screen.getByRole('img') as HTMLImageElement;

    expect(img().src).toContain('cover.png');

    fireEvent.click(screen.getByLabelText('Следующее фото'));
    expect(img().src).toContain('side.png');

    fireEvent.click(screen.getByLabelText('Предыдущее фото'));
    expect(img().src).toContain('cover.png');
  });

  it('листание закольцовано в обе стороны', () => {
    render(<RecipeGallery images={images} alt="Блюдо" />);
    const img = () => screen.getByRole('img') as HTMLImageElement;

    // назад с первого фото → последнее
    fireEvent.click(screen.getByLabelText('Предыдущее фото'));
    expect(img().src).toContain('cut.png');

    // вперёд с последнего → снова первое
    fireEvent.click(screen.getByLabelText('Следующее фото'));
    expect(img().src).toContain('cover.png');
  });

  it('показывает счётчик и подпись текущего фото', () => {
    render(<RecipeGallery images={images} alt="Блюдо" />);

    expect(screen.getByText('1 / 3')).toBeInTheDocument();
    expect(screen.queryByText('Вид сбоку')).not.toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('Следующее фото'));

    expect(screen.getByText('2 / 3')).toBeInTheDocument();
    expect(screen.getByText('Вид сбоку')).toBeInTheDocument();
  });

  it('точка переключает на нужное фото', () => {
    render(<RecipeGallery images={images} alt="Блюдо" />);

    fireEvent.click(screen.getByLabelText('Фото 3'));

    expect((screen.getByRole('img') as HTMLImageElement).src).toContain('cut.png');
  });

  it('клик по центру открывает текущее фото во весь экран', () => {
    const onZoom = jest.fn();
    render(<RecipeGallery images={images} alt="Блюдо" onZoom={onZoom} />);

    fireEvent.click(screen.getByLabelText('Следующее фото'));
    fireEvent.click(screen.getByRole('img'));

    expect(onZoom).toHaveBeenCalledWith(images[1]);
  });

  it('смена рецепта сбрасывает галерею на первое фото', () => {
    const { rerender } = render(<RecipeGallery images={images} alt="Блюдо" />);
    fireEvent.click(screen.getByLabelText('Следующее фото'));
    expect((screen.getByRole('img') as HTMLImageElement).src).toContain('side.png');

    rerender(<RecipeGallery images={[{ url: '/media/other.png' }]} alt="Другое" />);

    expect((screen.getByRole('img') as HTMLImageElement).src).toContain('other.png');
  });
});
