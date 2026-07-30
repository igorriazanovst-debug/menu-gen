// MG_CATRU — русские подписи для англ. токенов категорий рецепта
// (Recipe.categories: DishType / FoodGroup / meal_type и пр.).
// Зеркалит словарь мобилки (_kCategoryRu в recipe_detail_screen.dart) и
// backend-choices Recipe.DishType. Незнакомые токены выводим как есть.
export const CATEGORY_RU: Record<string, string> = {
  // DishType (backend apps/recipes/models.py)
  soup: 'Первое (суп)',
  main: 'Второе/горячее',
  salad: 'Салат',
  side: 'Гарнир',
  dessert: 'Десерт',
  drink: 'Напиток',
  bakery: 'Выпечка',
  sauce: 'Соус',
  snack: 'Перекус',
  breakfast_dish: 'Завтрак',
  // meal_type
  breakfast: 'Завтрак',
  lunch: 'Обед',
  dinner: 'Ужин',
  // FoodGroup / прочие токены
  grain: 'Зерновые',
  protein: 'Белки',
  vegetable: 'Овощи',
  fruit: 'Фрукты',
  dairy: 'Молочные',
  oil: 'Масла/жиры',
  other: 'Прочее',
};

/** Русская подпись категории; незнакомый токен возвращается без изменений. */
export const categoryLabel = (c: string): string =>
  CATEGORY_RU[c.trim().toLowerCase()] ?? c;
