import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/api/api_client.dart';
import '../../../core/cache/recipe_detail_prefetch.dart'; // OFFLINE: прогрев рецептов меню
import '../../../core/connectivity/connectivity_cubit.dart'; // MG_T10
import '../../../core/theme/app_theme.dart';
import '../bloc/menu_bloc.dart';
import '../widgets/generate_menu_bottom_sheet.dart';
import '../widgets/menu_matrix.dart'; // MG_SKIN: матрица меню
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

  // MG-402: id активного меню (для замены блюда в приёме).
  int? _activeMenuId;

  @override
  void initState() {
    super.initState();
    _loadMe();
    context.read<MenuBloc>().add(const MenuLoadRequested());
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

  /// Маппинг item → слот с дедупликацией по recipe.id (семейный режим).
  List<Map<String, dynamic>> _itemsForSlot({
    required List<Map<String, dynamic>> dayItems,
    required String slot,
  }) {
    List<Map<String, dynamic>> result;
    if (slot == 'snack1' || slot == 'snack2') {
      // Сначала пробуем точный meal_slot (новые меню).
      result = dayItems.where((i) => (i['meal_slot'] as String?) == slot).toList();
      if (result.isEmpty) {
        // Фоллбек по индексу для старых меню без meal_slot.
        final snacks = dayItems
            .where((i) => (i['meal_type'] as String?) == 'snack')
            .toList();
        if (slot == 'snack1' && snacks.isNotEmpty) result = [snacks.first];
        else if (slot == 'snack2' && snacks.length >= 2) result = [snacks[1]];
        else result = const [];
      }
    } else {
      result = dayItems.where((i) => (i['meal_type'] as String?) == slot).toList();
    }
    // Дедуплицируем по recipe.id — в семейном режиме один рецепт на члена семьи.
    final seen = <Object>{};
    return result.where((i) {
      final rid = (i['recipe'] as Map<String, dynamic>?)?['id'];
      if (rid == null) return true;
      return seen.add(rid);
    }).toList();
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
        toolbarHeight: 44,
        titleSpacing: 8,
        titleTextStyle: TextStyle(
          fontSize: 17,
          fontWeight: FontWeight.w700,
          color: Theme.of(context).colorScheme.onSurface,
        ),
        title: BlocBuilder<MenuBloc, MenuState>(
          buildWhen: (a, b) => true,
          builder: (context, state) {
            if (state is MenuLoaded && state.menus.length > 1) {
              final activeId = state.active?['id'];
              // Фон AppBar светлый → закрытый вид дропдауна рисуем тёмным
              // (onSurface). Открытый список на фоне primary — там пункты белые.
              final onBar = Theme.of(context).colorScheme.onSurface;
              return DropdownButtonHideUnderline(
                child: DropdownButton<int>(
                  value: activeId is int ? activeId : null,
                  isExpanded: true,
                  iconEnabledColor: onBar,
                  dropdownColor: Theme.of(context).colorScheme.primary,
                  style: TextStyle(color: onBar, fontSize: 16),
                  // Закрытый вид (выбранное меню в AppBar) — тёмным, видимым.
                  selectedItemBuilder: (context) => state.menus.map((m) {
                    return Align(
                      alignment: Alignment.centerLeft,
                      child: Text(
                        _shortRange(m),
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          color: onBar,
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    );
                  }).toList(),
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
            iconSize: 20,
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(minWidth: 38, minHeight: 38),
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
                iconSize: 20,
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(minWidth: 38, minHeight: 38),
                icon: const Icon(Icons.delete_outline, color: Colors.redAccent),
                tooltip: 'Удалить меню',
                onPressed: () => _confirmDeleteCurrent(context, activeId),
              );
            },
          ),
          IconButton(
            iconSize: 20,
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(minWidth: 38, minHeight: 38),
            icon: const Icon(Icons.refresh),
            tooltip: 'Обновить',
            onPressed: () =>
                context.read<MenuBloc>().add(const MenuLoadRequested()),
          ),
        ],
      ),
      body: BlocListener<MenuBloc, MenuState>(
        // OFFLINE: при загрузке/генерации меню фоном прогреваем кэш полными
        // рецептами всех блюд — чтобы они открывались без сети. Только онлайн.
        listenWhen: (a, b) => b is MenuLoaded || b is MenuGenerated,
        listener: (context, state) {
          Map<String, dynamic>? menu;
          if (state is MenuLoaded) {
            menu = state.active;
          } else if (state is MenuGenerated) {
            menu = state.menu;
          }
          if (menu != null &&
              context.read<ConnectivityCubit>().state ==
                  ConnectivityStatus.online) {
            RecipeDetailPrefetch.instance
                .prefetchMenu(widget.apiClient, menu);
          }
        },
        child: Stack(
        children: [
          Positioned.fill(
            child: BlocBuilder<MenuBloc, MenuState>(
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
          _activeMenuId = menu['id'] as int?; // MG-402: для замены блюда

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
              // MG_SKIN: карточка-итог за ВЫБРАННЫЙ день (донат КБЖУ).
              MenuSummaryCard(
                totals: MealNutritionTotals.fromItems(dayItems),
                start: _selectedDate!,
                end: _selectedDate!,
                periodLabel: _dayLabel(_selectedDate!),
              ),
              // MG_SKIN: матрица «приёмы × дни» с крупными фото блюд.
              Expanded(
                child: MenuMatrix(
                  days: allDays,
                  start: start,
                  mealSlots: _mealSlots,
                  labels: _mealLabels,
                  icons: _mealIcons,
                  selected: _selectedDate!,
                  cellItems: (off, slot) {
                    final di = items
                        .where((i) => (i['day_offset'] as int?) == off)
                        .toList();
                    return _itemsForSlot(dayItems: di, slot: slot);
                  },
                  onDaySelected: (d) => setState(() => _selectedDate = d),
                  onCellTap: (d, slot, its) => _openMealSheet(d, slot, its),
                ),
              ),
            ],
          );
              },
            ),
          ),
          Positioned.fill(
            child: _DraggableGenerateButton(
              onPressed: () => _showGenerateSheet(context),
            ),
          ),
        ],
        ),
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

  // MG_SKIN: подпись «выбранный день» для карточки-сводки.
  String _dayLabel(DateTime d) {
    final s = DateFormat('EEEE, d MMMM', 'ru').format(d);
    return s.isEmpty ? s : '${s[0].toUpperCase()}${s.substring(1)}';
  }

  // MG_SKIN: лист приёма пищи (тап по ячейке матрицы) — крупные карточки блюд.
  void _openMealSheet(
      DateTime date, String slot, List<Map<String, dynamic>> items) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (sheetCtx) {
        final h = MediaQuery.of(sheetCtx).size.height * 0.78;
        final cs = Theme.of(sheetCtx).colorScheme;
        return Container(
          height: h,
          decoration: BoxDecoration(
            color: cs.surface,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
          ),
          child: Column(
            children: [
              const SizedBox(height: 10),
              Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: sheetCtx.tokens.border,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 12, 8, 4),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        '${_mealLabels[slot] ?? slot} · '
                        '${DateFormat('d MMM', 'ru').format(date)}',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w800,
                          color: cs.onSurface,
                        ),
                      ),
                    ),
                    IconButton(
                      icon: const Icon(Icons.close),
                      onPressed: () => Navigator.of(sheetCtx).pop(),
                    ),
                  ],
                ),
              ),
              Expanded(
                child: MenuMealCarousel(
                  slotLabel: _mealLabels[slot] ?? slot,
                  items: items,
                  onRecipeTap: (recipeId) {
                    Navigator.of(sheetCtx).pop();
                    context.push('/recipes/$recipeId');
                  },
                  // MG-402: замена блюда в приёме.
                  menuId: _activeMenuId,
                  apiClient: widget.apiClient,
                  onSwapped: () {
                    Navigator.of(sheetCtx).pop(); // закрыть лист приёма
                    final id = _activeMenuId;
                    if (id != null) {
                      context
                          .read<MenuBloc>()
                          .add(MenuDetailRequested(id));
                    }
                  },
                ),
              ),
            ],
          ),
        );
      },
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

// MG_SKIN: перетаскиваемая кнопка «Сгенерировать» — чтобы не перекрывать
// приёмы пищи. Положение хранится локально, по умолчанию — снизу справа.
class _DraggableGenerateButton extends StatefulWidget {
  final VoidCallback onPressed;
  const _DraggableGenerateButton({required this.onPressed});

  @override
  State<_DraggableGenerateButton> createState() =>
      _DraggableGenerateButtonState();
}

class _DraggableGenerateButtonState extends State<_DraggableGenerateButton> {
  static const double _w = 168;
  static const double _h = 46;

  Offset? _pos; // top-left; null = дефолт (снизу справа)

  double _clamp(double v, double lo, double hi) =>
      v < lo ? lo : (v > hi ? hi : v);

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return LayoutBuilder(
      builder: (context, c) {
        final maxX = (c.maxWidth - _w - 8);
        final maxY = (c.maxHeight - _h - 8);
        final hiX = maxX < 8 ? 8.0 : maxX;
        final hiY = maxY < 8 ? 8.0 : maxY;
        final base = _pos ?? Offset(c.maxWidth - _w - 16, c.maxHeight - _h - 16);
        final dx = _clamp(base.dx, 8, hiX);
        final dy = _clamp(base.dy, 8, hiY);
        return Stack(
          children: [
            Positioned(
              left: dx,
              top: dy,
              child: GestureDetector(
                onPanUpdate: (d) {
                  setState(() {
                    _pos = Offset(
                      _clamp(dx + d.delta.dx, 8, hiX),
                      _clamp(dy + d.delta.dy, 8, hiY),
                    );
                  });
                },
                child: Material(
                  color: cs.primary,
                  elevation: 4,
                  borderRadius: BorderRadius.circular(_h / 2),
                  child: InkWell(
                    borderRadius: BorderRadius.circular(_h / 2),
                    onTap: widget.onPressed,
                    child: const SizedBox(
                      width: _w,
                      height: _h,
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.auto_awesome, color: Colors.white, size: 20),
                          SizedBox(width: 8),
                          Text(
                            'Сгенерировать',
                            style: TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.w600,
                              fontSize: 15,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}
