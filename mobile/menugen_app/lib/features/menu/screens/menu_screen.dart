import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/api/api_client.dart';
import '../../../core/connectivity/connectivity_cubit.dart'; // MG_T10
import '../../../core/theme/app_theme.dart';
import '../bloc/menu_bloc.dart';
import '../widgets/generate_menu_bottom_sheet.dart';
import '../widgets/menu_day_strip.dart';
import '../widgets/menu_meal_carousel.dart';
import '../widgets/menu_summary_card.dart'; // MG_SKIN
import 'quarantine_screen.dart';

/// Главный экран "Меню" (MG_608_V_mobile_screen — добавлен Dropdown выбора меню).
class MenuScreen extends StatefulWidget {
  final ApiClient apiClient;
  const MenuScreen({super.key, required this.apiClient});

  @override
  State<MenuScreen> createState() => _MenuScreenState();
}

class _MenuScreenState extends State<MenuScreen> {
  // --- /users/me/ snapshot
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
        _mealPlanType = (profile['meal_plan_type'] as String?) ?? '3';
        _meLoaded = true;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _meLoaded = true);
    }
  }

  List<String> get _mealSlots => _mealPlanType == '5'
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

  DateTime? _parseDate(dynamic v) {
    if (v is! String || v.isEmpty) return null;
    try {
      final d = DateTime.parse(v);
      return DateTime(d.year, d.month, d.day);
    } catch (_) {
      return null;
    }
  }

  /// Маппинг item.meal_type → слот:
  /// для 5-приёмов: первый snack за день → snack1, второй → snack2.
  List<Map<String, dynamic>> _itemsForSlot({
    required List<Map<String, dynamic>> dayItems,
    required String slot,
  }) {
    if (slot == 'snack1' || slot == 'snack2') {
      final snacks =
          dayItems.where((i) => (i['meal_type'] as String?) == 'snack').toList();
      if (snacks.isEmpty) return const [];
      if (slot == 'snack1') return [snacks.first];
      if (snacks.length >= 2) return [snacks[1]];
      return const [];
    }
    return dayItems.where((i) => (i['meal_type'] as String?) == slot).toList();
  }

  String _shortRange(Map<String, dynamic> m) {
    final s = _parseDate(m['start_date']);
    final e = _parseDate(m['end_date']);
    if (s == null || e == null) return 'Меню #${m['id']}';
    final fmt = DateFormat('d MMM', 'ru');
    return '${fmt.format(s)} – ${fmt.format(e)}';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: BlocBuilder<MenuBloc, MenuState>(
          buildWhen: (a, b) => true,
          builder: (context, state) {
            if (state is MenuLoaded && state.menus.length > 1) {
              final activeId = state.active?['id'];
              return DropdownButtonHideUnderline(
                child: DropdownButton<int>(
                  value: activeId is int ? activeId : null,
                  isExpanded: true,
                  iconEnabledColor: Colors.white,
                  dropdownColor: Theme.of(context).colorScheme.primary,
                  style: const TextStyle(color: Colors.white, fontSize: 16),
                  items: state.menus.map((m) {
                    return DropdownMenuItem<int>(
                      value: m['id'] as int,
                      child: Text(
                        _shortRange(m),
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(color: Colors.white),
                      ),
                    );
                  }).toList(),
                  onChanged: (id) {
                    if (id != null && id != activeId) {
                      context.read<MenuBloc>().add(MenuDetailRequested(id));
                    }
                  },
                ),
              );
            }
            return const Text('Меню');
          },
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.inventory_2_outlined),
            tooltip: 'Карантин',
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (_) => BlocProvider.value(
                    value: context.read<MenuBloc>(),
                    child: QuarantineScreen(apiClient: widget.apiClient),
                  ),
                ),
              );
            },
          ),
          // MG_608_1_V_mobile_delete: удалить текущее меню (мягко, в карантин)
          BlocBuilder<MenuBloc, MenuState>(
            buildWhen: (a, b) => true,
            builder: (context, state) {
              if (state is! MenuLoaded) return const SizedBox.shrink();
              final dynamic rawId = state.active?['id'];
              if (rawId is! int) return const SizedBox.shrink();
              final int activeId = rawId;
              return IconButton(
                icon: const Icon(Icons.delete_outline, color: Colors.redAccent),
                tooltip: 'Удалить меню',
                onPressed: () => _confirmDeleteCurrent(context, activeId),
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Обновить',
            onPressed: () =>
                context.read<MenuBloc>().add(const MenuLoadRequested()),
          ),
        ],
      ),
      body: BlocBuilder<MenuBloc, MenuState>(
        builder: (context, state) {
          if (state is MenuLoading || state is MenuGenerating || !_meLoaded) {
            return const Center(child: CircularProgressIndicator());
          }
          if (state is MenuError) {
            // MG_T10: offline -> only the global banner, no error view.
            if (context.watch<ConnectivityCubit>().state ==
                ConnectivityStatus.offline) {
              return const Center(
                  child: Icon(Icons.cloud_off, size: 48, color: Colors.black26));
            }
            return _ErrorView(
              message: state.message,
              onRetry: () =>
                  context.read<MenuBloc>().add(const MenuLoadRequested()),
            );
          }
          if (state is MenuPremiumLocked) {
            return _PremiumLockedView(message: state.message);
          }

          Map<String, dynamic>? menu;
          if (state is MenuLoaded) {
            menu = state.active;
          } else if (state is MenuGenerated) {
            menu = state.menu;
          }

          if (menu == null) {
            return _EmptyView(onGenerate: () => _showGenerateSheet(context));
          }

          final start = _parseDate(menu['start_date']);
          final periodDays = (menu['period_days'] as int?) ?? 7;
          if (start == null) {
            return _ErrorView(
              message: 'Не удалось разобрать дату меню',
              onRetry: () =>
                  context.read<MenuBloc>().add(const MenuLoadRequested()),
            );
          }
          final allDays =
              List<DateTime>.generate(periodDays, (i) => start.add(Duration(days: i)));

          // выбранная дата: today если в окне, иначе start
          // MG_608_V_mobile_screen: сброс _selectedDate если она вне окна нового меню
          if (_selectedDate == null ||
              _selectedDate!.isBefore(allDays.first) ||
              _selectedDate!.isAfter(allDays.last)) {
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
              // MG_SKIN: карточка-итог дня (донат КБЖУ) в стиле Main-референса.
              MenuSummaryCard(
                totals: MealNutritionTotals.fromItems(dayItems),
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

  Future<void> _confirmDeleteCurrent(BuildContext context, int menuId) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Удалить меню?'),
        content: const Text(
          'Меню переместится в карантин. Его можно будет восстановить в течение 24 часов.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Отмена'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('Удалить'),
          ),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await widget.apiClient.delete('/menu/$menuId/delete/');
      if (!mounted) return;
      try {
        final p = await SharedPreferences.getInstance();
        if (p.getInt('menugen.lastMenuId') == menuId) {
          await p.remove('menugen.lastMenuId');
        }
      } catch (_) {}
      // Сброс выбранной даты — для нового меню окно будет своё
      setState(() {
        _selectedDate = null;
      });
      // ignore: use_build_context_synchronously
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Меню перемещено в карантин')),
      );
      // ignore: use_build_context_synchronously
      context.read<MenuBloc>().add(const MenuLoadRequested());
    } catch (e) {
      if (!mounted) return;
      // ignore: use_build_context_synchronously
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Ошибка удаления: $e')),
      );
    }
  }

  void _showGenerateSheet(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(24))),
      builder: (_) => BlocProvider.value(
        value: context.read<MenuBloc>(),
        child: GenerateMenuBottomSheet(apiClient: widget.apiClient),
      ),
    );
  }
}

class _MealTabs extends StatefulWidget {
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
  State<_MealTabs> createState() => _MealTabsState();
}

class _MealTabsState extends State<_MealTabs> {
  // KBJU_DISPLAY: авто-скролл ленты к активному табу при свайпе PageView.
  final ScrollController _ctrl = ScrollController();
  static const double _chipExtent = 132.0; // оценка ширины чипа + separator

  @override
  void didUpdateWidget(covariant _MealTabs old) {
    super.didUpdateWidget(old);
    if (old.selected != widget.selected) _scrollToSelected();
  }

  void _scrollToSelected() {
    if (!_ctrl.hasClients) return;
    final target =
        (widget.selected * _chipExtent) - 40; // лёгкий отступ слева
    final max = _ctrl.position.maxScrollExtent;
    final offset = target.clamp(0.0, max);
    _ctrl.animateTo(offset,
        duration: const Duration(milliseconds: 250), curve: Curves.easeOut);
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final slots = widget.slots;
    final labels = widget.labels;
    final icons = widget.icons;
    final onSelected = widget.onSelected;
    return SizedBox(
      height: 64,
      child: ListView.separated(
        controller: _ctrl,
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        itemCount: slots.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (context, i) {
          final slot = slots[i];
          final active = i == widget.selected;
          final cs = context.cs;
          return ChoiceChip(
            label: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(icons[slot] ?? Icons.restaurant,
                    size: 18,
                    color: active ? Colors.white : cs.onSurface),
                const SizedBox(width: 6),
                Text(
                  labels[slot] ?? slot,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: active ? Colors.white : cs.onSurface,
                  ),
                ),
              ],
            ),
            selected: active,
            selectedColor: cs.primary,
            backgroundColor: cs.surface,
            showCheckmark: false,
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(20),
              side: BorderSide(
                color: active ? cs.primary : context.tokens.border,
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
            Icon(Icons.lock_outline, size: 56, color: context.cs.primary),
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
