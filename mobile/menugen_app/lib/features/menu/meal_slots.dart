// MG_MEALCOUNT_UI: сколько приёмов показывать — свойство меню, а не профиля.
//
// Экран брал число приёмов из профиля (`/users/me/` → `meal_plan_type`), а
// генерация спрашивает его отдельно, в шторке. Выбрал в шторке три приёма при
// пятиразовом профиле — меню приходило на три, а сетка всё равно рисовала пять,
// и два перекуса стояли пустыми.
//
// Правильный источник — само меню: `filters_used.meal_plan_type`, с которым его
// сгенерировали. Веб так и делает (MenuPage.tsx, `hasTwoSnacks`).

const mealSlots3 = <String>['breakfast', 'lunch', 'dinner'];
const mealSlots5 = <String>['breakfast', 'snack1', 'lunch', 'snack2', 'dinner'];

/// Позиция — перекус (в новых меню есть `meal_slot`, в старых только `meal_type`).
bool isSnackItem(Map<String, dynamic> item) {
  final slot = item['meal_slot'];
  if (slot is String && slot.startsWith('snack')) return true;
  return item['meal_type'] == 'snack';
}

/// Слоты для меню: сперва по фильтрам генерации, иначе по самим позициям.
///
/// Фоллбек нужен старым меню, сгенерированным до появления `meal_plan_type` в
/// `filters_used`. Он смотрит на всё меню, а не на выбранный день: перекуса
/// может не быть в конкретном дне, и это не повод прятать слот целиком.
List<String> mealSlotsForMenu(Map<String, dynamic>? menu) {
  if (menu == null) return mealSlots3;

  final filters = menu['filters_used'];
  final planType = filters is Map ? filters['meal_plan_type'] : null;
  if (planType == '5') return mealSlots5;
  if (planType == '3') return mealSlots3;

  final items = menu['items'];
  if (items is! List) return mealSlots3;
  final hasSnack = items
      .whereType<Map>()
      .any((i) => isSnackItem(Map<String, dynamic>.from(i)));
  return hasSnack ? mealSlots5 : mealSlots3;
}

/// Позиции дня для слота, с дедупликацией по recipe.id (семейный режим — один
/// рецепт на нескольких членов семьи показываем один раз).
List<Map<String, dynamic>> itemsForSlot({
  required List<Map<String, dynamic>> dayItems,
  required String slot,
}) {
  List<Map<String, dynamic>> result;
  if (slot == 'snack1' || slot == 'snack2') {
    // Сначала пробуем точный meal_slot (новые меню).
    result = dayItems.where((i) => (i['meal_slot'] as String?) == slot).toList();
    if (result.isEmpty) {
      // Фоллбек по индексу для старых меню без meal_slot.
      final snacks =
          dayItems.where((i) => (i['meal_type'] as String?) == 'snack').toList();
      if (slot == 'snack1' && snacks.isNotEmpty) {
        result = [snacks.first];
      } else if (slot == 'snack2' && snacks.length >= 2) {
        result = [snacks[1]];
      } else {
        result = const [];
      }
    }
  } else {
    result = dayItems.where((i) => (i['meal_type'] as String?) == slot).toList();
  }

  final seen = <Object>{};
  return result.where((i) {
    final rid = (i['recipe'] as Map<String, dynamic>?)?['id'];
    if (rid == null) return true;
    return seen.add(rid);
  }).toList();
}
