import 'package:flutter/material.dart';

import '../models/recipe_filters.dart';

/// Bottom sheet that lets the user toggle and configure recipe filters.
/// All filter blocks are independent; any combination is allowed.
class FilterSheet extends StatefulWidget {
  final RecipeFilters initial;
  final List<String> availableCountries;
  final bool hasFridge;

  const FilterSheet({
    super.key,
    required this.initial,
    this.availableCountries = const [],
    this.hasFridge = false,
  });

  static Future<RecipeFilters?> show(
    BuildContext context, {
    required RecipeFilters initial,
    List<String> countries = const [],
    bool hasFridge = false,
  }) {
    return showModalBottomSheet<RecipeFilters>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) => FilterSheet(
        initial: initial,
        availableCountries: countries,
        hasFridge: hasFridge,
      ),
    );
  }

  @override
  State<FilterSheet> createState() => _FilterSheetState();
}

class _FilterSheetState extends State<FilterSheet> {
  late RecipeFilters _f;

  // local controllers
  final _ingCtrl = TextEditingController();

  // labels
  static const _mealTypes = <String, String>{
    'breakfast': 'Завтрак',
    'lunch': 'Обед',
    'dinner': 'Ужин',
    'snack': 'Перекус',
  };
  static const _dishTypes = <String>[
    'Суп', 'Салат', 'Выпечка', 'Десерт', 'Напиток', 'Закуска', 'Соус', 'Гарнир',
  ];
  static const _foodGroups = <String, String>{
    'grain': 'Зерновые',
    'protein': 'Белки',
    'vegetable': 'Овощи',
    'fruit': 'Фрукты',
    'dairy': 'Молочные',
    'oil': 'Масла/жиры',
    'other': 'Прочее',
  };

  @override
  void initState() {
    super.initState();
    _f = widget.initial;
  }

  @override
  void dispose() {
    _ingCtrl.dispose();
    super.dispose();
  }

  void _addIngredient() {
    final t = _ingCtrl.text.trim();
    if (t.isEmpty) return;
    final next = List<String>.from(_f.manualIngredients);
    if (!next.any((s) => s.toLowerCase() == t.toLowerCase())) {
      next.add(t);
    }
    setState(() {
      _f = _f.copyWith(manualIngredients: next);
      _ingCtrl.clear();
    });
  }

  void _removeIngredient(String name) {
    final next = List<String>.from(_f.manualIngredients)..remove(name);
    setState(() => _f = _f.copyWith(manualIngredients: next));
  }

  @override
  Widget build(BuildContext context) {
    final viewInsets = MediaQuery.of(context).viewInsets.bottom;
    return Padding(
      padding: EdgeInsets.only(bottom: viewInsets),
      child: SafeArea(
        top: false,
        child: ConstrainedBox(
          constraints: BoxConstraints(
            maxHeight: MediaQuery.of(context).size.height * 0.92,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              _handle(),
              _topBar(context),
              const Divider(height: 1),
              Expanded(
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
                  children: [
                    _section(
                      title: '1. Приём пищи',
                      child: Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: _mealTypes.entries.map((e) {
                          final selected = _f.mealType == e.key;
                          return ChoiceChip(
                            label: Text(e.value),
                            selected: selected,
                            onSelected: (_) => setState(
                              () => _f = _f.copyWith(mealType: selected ? null : e.key),
                            ),
                          );
                        }).toList(),
                      ),
                    ),
                    _section(
                      title: '2. Вид блюда',
                      child: Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: _dishTypes.map((d) {
                          final selected = _f.dishType == d;
                          return ChoiceChip(
                            label: Text(d),
                            selected: selected,
                            onSelected: (_) => setState(
                              () => _f = _f.copyWith(dishType: selected ? null : d),
                            ),
                          );
                        }).toList(),
                      ),
                    ),
                    _section(
                      title: '3. Основной продукт',
                      child: Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: _foodGroups.entries.map((e) {
                          final selected = _f.foodGroup == e.key;
                          return ChoiceChip(
                            label: Text(e.value),
                            selected: selected,
                            onSelected: (_) => setState(
                              () => _f = _f.copyWith(foodGroup: selected ? null : e.key),
                            ),
                          );
                        }).toList(),
                      ),
                    ),
                    _section(
                      title: '4. Набор ингредиентов',
                      subtitle:
                          'Введите ингредиенты, которые должны быть в рецепте.',
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Expanded(
                                child: TextField(
                                  controller: _ingCtrl,
                                  textInputAction: TextInputAction.done,
                                  onSubmitted: (_) => _addIngredient(),
                                  decoration: const InputDecoration(
                                    hintText: 'Например, курица',
                                    isDense: true,
                                    border: OutlineInputBorder(),
                                  ),
                                ),
                              ),
                              const SizedBox(width: 8),
                              IconButton.filled(
                                onPressed: _addIngredient,
                                icon: const Icon(Icons.add),
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),
                          if (_f.manualIngredients.isNotEmpty)
                            Wrap(
                              spacing: 6,
                              runSpacing: 6,
                              children: _f.manualIngredients
                                  .map(
                                    (n) => InputChip(
                                      label: Text(n),
                                      onDeleted: () => _removeIngredient(n),
                                    ),
                                  )
                                  .toList(),
                            ),
                          const SizedBox(height: 8),
                          Row(
                            children: [
                              const Text('Совпадение: '),
                              const SizedBox(width: 8),
                              SegmentedButton<bool>(
                                segments: const [
                                  ButtonSegment(value: true, label: Text('Все')),
                                  ButtonSegment(value: false, label: Text('Любой')),
                                ],
                                selected: {_f.manualIngredientsAll},
                                onSelectionChanged: (s) => setState(
                                  () => _f = _f.copyWith(manualIngredientsAll: s.first),
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                    _section(
                      title: '5. Из холодильника',
                      subtitle: widget.hasFridge
                          ? 'Сортировать рецепты по числу совпадений с содержимым холодильника.'
                          : 'Холодильник пуст или недоступен.',
                      child: SwitchListTile(
                        contentPadding: EdgeInsets.zero,
                        title: const Text('Использовать содержимое холодильника'),
                        value: _f.useFridge,
                        onChanged: widget.hasFridge
                            ? (v) => setState(() => _f = _f.copyWith(useFridge: v))
                            : null,
                      ),
                    ),
                    _section(
                      title: '6. Любимое / Нелюбимое',
                      child: SegmentedButton<int>(
                        segments: const [
                          ButtonSegment(value: 0, label: Text('Все')),
                          ButtonSegment(value: 1, label: Text('Любимые')),
                          ButtonSegment(value: 2, label: Text('Нелюбимые')),
                        ],
                        selected: {
                          _f.favorite == null ? 0 : (_f.favorite! ? 1 : 2),
                        },
                        onSelectionChanged: (s) {
                          final v = s.first;
                          setState(() {
                            _f = _f.copyWith(
                              favorite: v == 0 ? null : (v == 1 ? true : false),
                            );
                          });
                        },
                      ),
                    ),
                    _section(
                      title: '7. Страна',
                      child: widget.availableCountries.isEmpty
                          ? TextField(
                              controller: TextEditingController(text: _f.country ?? ''),
                              decoration: const InputDecoration(
                                hintText: 'Например, Италия',
                                isDense: true,
                                border: OutlineInputBorder(),
                              ),
                              onChanged: (v) => _f = _f.copyWith(country: v),
                            )
                          : Wrap(
                              spacing: 8,
                              runSpacing: 8,
                              children: widget.availableCountries.map((c) {
                                final selected = _f.country == c;
                                return ChoiceChip(
                                  label: Text(c),
                                  selected: selected,
                                  onSelected: (_) => setState(
                                    () => _f = _f.copyWith(country: selected ? null : c),
                                  ),
                                );
                              }).toList(),
                            ),
                    ),
                    _section(
                      title: '8. Аллергены',
                      child: SwitchListTile(
                        contentPadding: EdgeInsets.zero,
                        title: const Text('Исключить мои аллергены'),
                        value: _f.excludeAllergens,
                        onChanged: (v) => setState(
                          () => _f = _f.copyWith(excludeAllergens: v),
                        ),
                      ),
                    ),
                    const SizedBox(height: 8),
                  ],
                ),
              ),
              const Divider(height: 1),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
                child: Row(
                  children: [
                    Expanded(
                      child: OutlinedButton(
                        onPressed: () =>
                            setState(() => _f = const RecipeFilters()),
                        child: const Text('Сбросить'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: FilledButton(
                        onPressed: () => Navigator.of(context).pop(_f),
                        child: Text(
                          _f.isEmpty
                              ? 'Применить'
                              : 'Применить (${_f.activeCount})',
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _handle() => Container(
        width: 40,
        height: 4,
        margin: const EdgeInsets.only(top: 10, bottom: 10),
        decoration: BoxDecoration(
          color: Colors.grey.shade300,
          borderRadius: BorderRadius.circular(2),
        ),
      );

  Widget _topBar(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 0, 8, 8),
        child: Row(
          children: [
            const Text(
              'Фильтры',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
            ),
            const Spacer(),
            IconButton(
              icon: const Icon(Icons.close),
              onPressed: () => Navigator.of(context).pop(),
            ),
          ],
        ),
      );

  Widget _section({required String title, String? subtitle, required Widget child}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
          ),
          if (subtitle != null) ...[
            const SizedBox(height: 4),
            Text(
              subtitle,
              style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
            ),
          ],
          const SizedBox(height: 8),
          child,
        ],
      ),
    );
  }
}
