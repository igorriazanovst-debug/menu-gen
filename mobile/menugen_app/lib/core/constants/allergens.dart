// MG_ALLERGEN14 — обязательные к маркировке аллергены (ТР ТС 022/2011,
// EU 1169/2011). Зеркалит backend apps/common/allergens.py (ключи совпадают).
class AllergenDef {
  final String key;
  final String label;
  final String group;
  final String full;
  const AllergenDef(this.key, this.label, this.group, this.full);
}

const List<AllergenDef> kAllergens = [
  AllergenDef('gluten', 'Глютен (злаки)', 'Злаки',
      'Злаки, содержащие глютен: пшеница (в т.ч. полба, камут), рожь, ячмень, овёс'),
  AllergenDef('crustaceans', 'Ракообразные', 'Морепродукты',
      'Ракообразные и продукты их переработки (крабы, креветки, омары и др.)'),
  AllergenDef('eggs', 'Яйца', 'Яйца', 'Яйца и продукты их переработки'),
  AllergenDef('fish', 'Рыба', 'Рыба', 'Рыба и продукты её переработки'),
  AllergenDef('peanuts', 'Арахис', 'Орехи/бобовые', 'Арахис и продукты его переработки'),
  AllergenDef('soy', 'Соя', 'Бобовые', 'Соя и продукты её переработки'),
  AllergenDef('milk', 'Молоко', 'Молочные продукты',
      'Молоко и продукты его переработки (включая лактозу)'),
  AllergenDef('nuts', 'Орехи', 'Орехи',
      'Орехи: миндаль, фундук, грецкий, кешью, пекан, бразильский, фисташки, макадамия'),
  AllergenDef('celery', 'Сельдерей', 'Овощи', 'Сельдерей и продукты его переработки'),
  AllergenDef('mustard', 'Горчица', 'Приправы', 'Горчица и продукты её переработки'),
  AllergenDef('sesame', 'Кунжут', 'Семена', 'Кунжут и продукты его переработки'),
  AllergenDef('sulphites', 'Диоксид серы и сульфиты', 'Добавки',
      'Диоксид серы и сульфиты в концентрации более 10 мг/кг (мг/л)'),
  AllergenDef('lupin', 'Люпин', 'Бобовые', 'Люпин и продукты его переработки'),
  AllergenDef('molluscs', 'Моллюски', 'Морепродукты',
      'Моллюски и продукты их переработки (устрицы, мидии, кальмары и др.)'),
];

final Map<String, AllergenDef> _byKey = {for (final a in kAllergens) a.key: a};

final List<String> kAllergenKeys = [for (final a in kAllergens) a.key];

/// Человекочитаемая метка по ключу; для кастомных/неизвестных — само значение.
String allergenLabel(String key) => _byKey[key]?.label ?? key;

/// true, если значение — один из 14 стандартных ключей.
bool isKnownAllergen(String key) => _byKey.containsKey(key);
