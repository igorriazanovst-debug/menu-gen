// MG_SWAPFREE: русские подписи пищевых групп (Recipe.food_group).
//
// Те же значения лежат в web/menugen-web/src/constants/categories.ts — при
// изменении списка групп на бэкенде правятся обе стороны.
const Map<String, String> kFoodGroupRu = {
  'grain': 'Зерновые',
  'protein': 'Белки',
  'vegetable': 'Овощи',
  'fruit': 'Фрукты',
  'dairy': 'Молочные',
  'oil': 'Масла/жиры',
  'other': 'Прочее',
};

/// Подпись группы; незнакомый код возвращается как есть, а не прячется.
String foodGroupLabel(String? code) {
  final key = (code ?? '').trim().toLowerCase();
  if (key.isEmpty) return '';
  return kFoodGroupRu[key] ?? key;
}
