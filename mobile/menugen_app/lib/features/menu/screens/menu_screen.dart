import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../core/api/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../bloc/menu_bloc.dart';
import '../widgets/generate_menu_bottom_sheet.dart';
import '../widgets/menu_day_strip.dart';
import '../widgets/menu_meal_carousel.dart';

/// Главный экран "Меню":
///  1. Заголовок:  Меню для %name% на %start–end%
///  2. Календарь дат (горизонтальный, tappable)
///  3. Табы приёмов пищи (по profile.meal_plan_type)
///  4. PageView крупных карточек блюд выбранного приёма
///  5. tap по карточке → /recipes/:id
class MenuScreen extends StatefulWidget {
  final ApiClient apiClient;
  const MenuScreen({super.key, required this.apiClient});

  @override
  State<MenuScreen> createState() => _MenuScreenState();
}

class _MenuScreenState extends State<MenuScreen> {
  // --- /users/me/ snapshot
  String? _userName;
  String _mealPlanType = '3';
  bool _meLoaded = false;

  // --- выбранная дата
  DateTime? _selectedDate;

  // --- порядок meal-таб для PageView
  late final PageController _mealPageCtrl;
  int _mealIndex = 0;

  @override
  void initState() {
    super.initState();
    _mealPageCtrl = PageController();
    _loadMe();
    context.read<MenuBloc>().add(const MenuLoadRequested());
  }

  @override
  void dispose() {
    _mealPageCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadMe() async {
    try {
      final r = await widget.apiClient.get('/users/me/');
      final data = r is Map ? Map<String, dynamic>.from(r) : <String, dynamic>{};
      final profile = data['profile'] is Map
          ? Map<String, dynamic>.from(data['profile'] as Map)
          : <String, dynamic>{};
      if (!mounted) return;
      setState(() {
        _userName = data['name'] as String?;
        _mealPlanType = (profile['meal_plan_type'] as String?) ?? '3';
        _meLoaded = true;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _meLoaded = true);
    }
  }

  List<String> get _mealSlots =>
      _mealPlanType == '5'
          ? const ['breakfast', 'snack1', 'lunch', 'snack2', 'dinner']
          : const ['breakfast', 'lunch', 'dinner'];

  static const _mealLabels = {
    'breakfast': 'Завтрак',
    'snack1': 'Перекус 1',
    'lunch': 'Обед',
    'snack2': 'Перекус 2',
    'dinner': 'Ужин',
    'snack': 'Перекус',
  };

  static const _mealIcons = {
    'breakfast': Icons.wb_sunny_outlined,
    'snack1': Icons.local_cafe_outlined,
    'lunch': Icons.lunch_dining_outlined,
    'snack2': Icons.cookie_outlined,
    'dinner': Icons.nights_stay_outlined,
    'snack': Icons.apple,
  };

  /// Меню с today внутри (start_date <= today <= end_date), иначе ближайшее.
  Map<String, dynamic>? _pickMenu(List<Map<String, dynamic>> menus) {
    if (menus.isEmpty) return null;
    final today = DateTime.now();
    final todayDate = DateTime(today.year, today.month, today.day);
    for (final m in menus) {
      final s = _parseDate(m['start_date']);
      final e = _parseDate(m['end_date']);
      if (s != null && e != null && !todayDate.isBefore(s) && !todayDate.isAfter(e)) {
        return m;
      }
    }
    return menus.first;
  }

  DateTime? _parseDate(dynamic v) {
    if (v is! String || v.isEmpty) return null;
    try {
      final d = DateTime.parse(v);
      return DateTime(d.year, d.month, d.day);
    } catch (_) {
      return null;
    }
  }

  /// Маппинг item.meal_type на наш слот:
  /// для 3-приёмов "snack" → не показываем (или сливаем в один tab "snack")
  /// для 5-приёмов "snack" чередуем: первый встретившийся snack/день → snack1, второй → snack2
  List<Map<String, dynamic>> _itemsForSlot({
    required List<Map<String, dynamic>> dayItems,
    required String slot,
  }) {
    if (slot == 'snack1' || slot == 'snack2') {
      final snacks = dayItems.where((i) => (i['meal_type'] as String?) == 'snack').toList();
      if (snacks.isEmpty) return const [];
      if (slot == 'snack1') return [snacks.first];
      if (snacks.length >= 2) return [snacks[1]];
      return const [];
    }
    return dayItems.where((i) => (i['meal_type'] as String?) == slot).toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Меню'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Обновить',
            onPressed: () => context.read<MenuBloc>().add(const MenuLoadRequested()),
          ),
        ],
      ),
      body: BlocBuilder<MenuBloc, MenuState>(
        builder: (context, state) {
          if (state is MenuLoading || state is MenuGenerating || !_meLoaded) {
            return const Center(child: CircularProgressIndicator());
          }
          if (state is MenuError) {
            return _ErrorView(
              message: state.message,
              onRetry: () => context.read<MenuBloc>().add(const MenuLoadRequested()),
            );
          }
          if (state is MenuPremiumLocked) {
            return _PremiumLockedView(message: state.message);
          }

          final menus = <Map<String, dynamic>>[];
          if (state is MenuLoaded) {
            menus.addAll(state.menus);
          } else if (state is MenuGenerated) {
            menus.add(state.menu);
          }

          final menu = _pickMenu(menus);
          if (menu == null) {
            return _EmptyView(onGenerate: () => _showGenerateSheet(context));
          }

          final start = _parseDate(menu['start_date']);
          final periodDays = (menu['period_days'] as int?) ?? 7;
          if (start == null) {
            return _ErrorView(
              message: 'Не удалось разобрать дату меню',
              onRetry: () => context.read<MenuBloc>().add(const MenuLoadRequested()),
            );
          }
          final allDays = List<DateTime>.generate(periodDays, (i) => start.add(Duration(days: i)));

          // выбранная дата: today если в окне, иначе start
          if (_selectedDate == null) {
            final today = DateTime.now();
            final todayDate = DateTime(today.year, today.month, today.day);
            _selectedDate = allDays.firstWhere(
              (d) => d.isAtSameMomentAs(todayDate),
              orElse: () => start,
            );
          }

          final items = (menu['items'] as List?)
                  ?.whereType<Map>()
                  .map((m) => Map<String, dynamic>.from(m))
                  .toList() ??
              const <Map<String, dynamic>>[];

          final selectedOffset =
              _selectedDate!.difference(start).inDays.clamp(0, periodDays - 1);
          final dayItems =
              items.where((i) => (i['day_offset'] as int?) == selectedOffset).toList();

          return Column(
            children: [
              _HeaderTitle(
                userName: _userName,
                start: start,
                end: start.add(Duration(days: periodDays - 1)),
              ),
              MenuDayStrip(
                days: allDays,
                selected: _selectedDate!,
                onSelected: (d) => setState(() => _selectedDate = d),
              ),
              _MealTabs(
                slots: _mealSlots,
                labels: _mealLabels,
                icons: _mealIcons,
                selected: _mealIndex,
                onSelected: (i) {
                  setState(() => _mealIndex = i);
                  _mealPageCtrl.animateToPage(
                    i,
                    duration: const Duration(milliseconds: 250),
                    curve: Curves.easeOut,
                  );
                },
              ),
              const SizedBox(height: 4),
              Expanded(
                child: PageView.builder(
                  controller: _mealPageCtrl,
                  itemCount: _mealSlots.length,
                  onPageChanged: (i) => setState(() => _mealIndex = i),
                  itemBuilder: (context, i) {
                    final slot = _mealSlots[i];
                    final slotItems = _itemsForSlot(dayItems: dayItems, slot: slot);
                    return MenuMealCarousel(
                      slotLabel: _mealLabels[slot] ?? slot,
                      items: slotItems,
                      onRecipeTap: (recipeId) => context.push('/recipes/$recipeId'),
                    );
                  },
                ),
              ),
            ],
          );
        },
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _showGenerateSheet(context),
        icon: const Icon(Icons.auto_awesome),
        label: const Text('Сгенерировать'),
      ),
    );
  }

  void _showGenerateSheet(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(24))),
      builder: (_) => BlocProvider.value(
        value: context.read<MenuBloc>(),
        child: const GenerateMenuBottomSheet(),
      ),
    );
  }
}

class _HeaderTitle extends StatelessWidget {
  final String? userName;
  final DateTime start;
  final DateTime end;
  const _HeaderTitle({required this.userName, required this.start, required this.end});

  @override
  Widget build(BuildContext context) {
    final fmt = DateFormat('d MMM', 'ru');
    final period = '${fmt.format(start)} – ${fmt.format(end)}';
    final name = (userName == null || userName!.isEmpty) ? '—' : userName!;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Меню для $name',
            style: const TextStyle(
                fontSize: 18, fontWeight: FontWeight.w700, color: AppColors.textPrimary),
          ),
          const SizedBox(height: 2),
          Text(
            'на $period',
            style: TextStyle(fontSize: 13, color: Colors.grey.shade600),
          ),
        ],
      ),
    );
  }
}

class _MealTabs extends StatelessWidget {
  final List<String> slots;
  final Map<String, String> labels;
  final Map<String, IconData> icons;
  final int selected;
  final ValueChanged<int> onSelected;

  const _MealTabs({
    required this.slots,
    required this.labels,
    required this.icons,
    required this.selected,
    required this.onSelected,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 64,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        itemCount: slots.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (context, i) {
          final slot = slots[i];
          final active = i == selected;
          return ChoiceChip(
            label: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(icons[slot] ?? Icons.restaurant,
                    size: 18,
                    color: active ? Colors.white : AppColors.textPrimary),
                const SizedBox(width: 6),
                Text(
                  labels[slot] ?? slot,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: active ? Colors.white : AppColors.textPrimary,
                  ),
                ),
              ],
            ),
            selected: active,
            selectedColor: AppColors.primary,
            backgroundColor: AppColors.surface,
            showCheckmark: false,
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(20),
              side: BorderSide(
                color: active ? AppColors.primary : Colors.grey.shade300,
              ),
            ),
            onSelected: (_) => onSelected(i),
          );
        },
      ),
    );
  }
}

class _EmptyView extends StatelessWidget {
  final VoidCallback onGenerate;
  const _EmptyView({required this.onGenerate});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.restaurant_menu, size: 80, color: Colors.grey.shade300),
            const SizedBox(height: 16),
            Text('Меню пока нет', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 8),
            Text(
              'Нажмите «Сгенерировать», чтобы составить меню',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.grey.shade600),
            ),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              icon: const Icon(Icons.auto_awesome),
              label: const Text('Сгенерировать'),
              onPressed: onGenerate,
            ),
          ],
        ),
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const _ErrorView({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, size: 56, color: Colors.red),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 8),
            TextButton(onPressed: onRetry, child: const Text('Повторить')),
          ],
        ),
      ),
    );
  }
}

class _PremiumLockedView extends StatelessWidget {
  final String message;
  const _PremiumLockedView({required this.message});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.lock_outline, size: 56, color: AppColors.primary),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: () => context.push('/paywall'),
              child: const Text('Подписка'),
            ),
          ],
        ),
      ),
    );
  }
}
