import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:intl/intl.dart';
import 'package:table_calendar/table_calendar.dart';

import '../../../core/api/api_client.dart'; // DIARY_COPY_V3
import '../../../core/connectivity/connectivity_cubit.dart'; // MG_T10
import '../../../core/premium/premium_gate_cubit.dart';
import '../../../core/widgets/draggable_action_button.dart'; // MG_SKIN
import '../bloc/diary_bloc.dart';
import '../models/diary_entry.dart';
import '../models/diary_stats.dart';
import '../widgets/diary_stats_card.dart';

class DiaryScreen extends StatefulWidget {
  const DiaryScreen({super.key});
  @override
  State<DiaryScreen> createState() => _DiaryScreenState();
}

class _DiaryScreenState extends State<DiaryScreen> {
  DateTime _selected = DateTime.now();
  DateTime _focusedDay = DateTime.now(); // MG_SKIN: страница календаря
  int? _memberId;
  List<Map<String, dynamic>> _members = const []; // DIARY_V2
  bool _isHead = false;

  @override
  void initState() {
    super.initState();
    _load();
    _loadFamily(); // DIARY_V2
  }

  Future<void> _loadFamily() async {
    try {
      final api = context.read<DiaryBloc>().apiClient;
      final r = await api.get('/family/');
      final m = (r is Map ? r['members'] : null);
      if (m is List && mounted) {
        setState(() {
          _members = m.whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList();
          _isHead = _members.any((x) => x['role'] == 'head' || x['role'] == 'owner');
        });
      }
    } catch (_) {/* non-fatal */}
  }

  void _load() {
    context.read<DiaryBloc>().add(
          DiaryLoadRequested(
            date: DateFormat('yyyy-MM-dd').format(_selected),
            memberId: _memberId,
          ),
        );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        toolbarHeight: 44,
        titleSpacing: 12,
        titleTextStyle: TextStyle(
          fontSize: 17,
          fontWeight: FontWeight.w700,
          color: Theme.of(context).colorScheme.onSurface,
        ),
        title: const Text('Дневник питания'),
        actions: [
          if (_isHead && _members.length > 1) // DIARY_V2 member switcher
            PopupMenuButton<int?>(
              iconSize: 20,
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints(minWidth: 38, minHeight: 38),
              icon: const Icon(Icons.people_outline),
              tooltip: 'Член семьи',
              onSelected: (v) {
                setState(() => _memberId = v);
                _load();
              },
              itemBuilder: (_) => [
                const PopupMenuItem<int?>(value: null, child: Text('Я')),
                ..._members.map((m) => PopupMenuItem<int?>(
                      value: m['id'] as int?,
                      child: Text((m['name'] as String?) ?? '—'),
                    )),
              ],
            ),
          IconButton(
            iconSize: 20,
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(minWidth: 38, minHeight: 38),
            icon: const Icon(Icons.copy_all_outlined),
            tooltip: 'Копировать из дня', // DIARY_COPY_V3
            onPressed: _onCopyTap,
          ),
          IconButton(
            iconSize: 20,
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(minWidth: 38, minHeight: 38),
            icon: const Icon(Icons.download_for_offline_outlined),
            tooltip: 'Импорт из меню',
            onPressed: _onImportTap,
          ),
          const SizedBox(width: 4),
        ],
      ),
      body: Stack(
        children: [
          Positioned.fill(
            child: Column(
              children: [
                _calendarBar(),
                _WaterCard( // DIARY_V2
                  onAdd: (delta) {
                    final st = context.read<DiaryBloc>().state;
                    final cur = st is DiaryLoaded ? st.waterMl : 0;
                    context.read<DiaryBloc>().add(DiaryWaterSetRequested(
                          date: DateFormat('yyyy-MM-dd').format(_selected),
                          waterMl: (cur + delta) < 0 ? 0 : (cur + delta),
                          memberId: _memberId,
                        ));
                  },
                  onSet: (ml) {
                    context.read<DiaryBloc>().add(DiaryWaterSetRequested(
                          date: DateFormat('yyyy-MM-dd').format(_selected),
                          waterMl: ml < 0 ? 0 : ml,
                          memberId: _memberId,
                        ));
                  },
                ),
                Expanded(child: _buildBody()),
              ],
            ),
          ),
          Positioned.fill(
            child: DraggableActionButton(
              onPressed: _onAddManualTap, // DIARY_V2
              icon: Icons.add,
              label: 'Добавить',
              width: 150,
            ),
          ),
        ],
      ),
    );
  }

  // MG_SKIN: минимальный недельный выбор даты (рус. локаль) + кнопка модалки.
  Widget _calendarBar() {
    final monthLabel = _cap(DateFormat('LLLL yyyy', 'ru').format(_focusedDay));
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 4, 4, 0),
          child: Row(
            children: [
              Expanded(
                child: Text(monthLabel,
                    style: const TextStyle(
                        fontWeight: FontWeight.w700, fontSize: 14)),
              ),
              TextButton.icon(
                onPressed: _openCalendarModal,
                icon: const Icon(Icons.calendar_month, size: 18),
                label: const Text('Календарь'),
                style: TextButton.styleFrom(
                  padding: const EdgeInsets.symmetric(horizontal: 8),
                  visualDensity: VisualDensity.compact,
                ),
              ),
            ],
          ),
        ),
        TableCalendar(
          locale: 'ru',
          firstDay: DateTime(2020),
          lastDay: DateTime(2030),
          focusedDay: _focusedDay,
          currentDay: DateTime.now(),
          headerVisible: false,
          rowHeight: 40,
          daysOfWeekHeight: 18,
          availableGestures: AvailableGestures.horizontalSwipe,
          calendarFormat: CalendarFormat.week,
          selectedDayPredicate: (d) => isSameDay(d, _selected),
          onDaySelected: (sel, foc) {
            setState(() {
              _selected = sel;
              _focusedDay = foc;
            });
            _load();
          },
          onPageChanged: (foc) => setState(() => _focusedDay = foc),
          calendarStyle: const CalendarStyle(
            outsideDaysVisible: false,
            cellMargin: EdgeInsets.all(4),
          ),
          daysOfWeekStyle: const DaysOfWeekStyle(
            weekdayStyle: TextStyle(fontSize: 11),
            weekendStyle: TextStyle(fontSize: 11),
          ),
        ),
      ],
    );
  }

  // MG_SKIN: модальное окно выбора месяца/недели/даты.
  void _openCalendarModal() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Theme.of(context).colorScheme.surface,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(24))),
      builder: (sheetCtx) {
        CalendarFormat fmt = CalendarFormat.month;
        DateTime focused = _focusedDay;
        return StatefulBuilder(
          builder: (ctx, setSheet) {
            return SafeArea(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(12, 10, 12, 16),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 40,
                      height: 4,
                      decoration: BoxDecoration(
                        color: Colors.black.withOpacity(0.15),
                        borderRadius: BorderRadius.circular(2),
                      ),
                    ),
                    const SizedBox(height: 8),
                    TableCalendar(
                      locale: 'ru',
                      firstDay: DateTime(2020),
                      lastDay: DateTime(2030),
                      focusedDay: focused,
                      currentDay: DateTime.now(),
                      calendarFormat: fmt,
                      availableCalendarFormats: const {
                        CalendarFormat.month: 'Месяц',
                        CalendarFormat.twoWeeks: '2 недели',
                        CalendarFormat.week: 'Неделя',
                      },
                      selectedDayPredicate: (d) => isSameDay(d, _selected),
                      onFormatChanged: (f) => setSheet(() => fmt = f),
                      onPageChanged: (f) => setSheet(() => focused = f),
                      onDaySelected: (sel, foc) {
                        setState(() {
                          _selected = sel;
                          _focusedDay = foc;
                        });
                        _load();
                        Navigator.of(ctx).pop();
                      },
                    ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );
  }

  String _cap(String s) =>
      s.isEmpty ? s : '${s[0].toUpperCase()}${s.substring(1)}';

  Widget _buildBody() {
    return BlocBuilder<DiaryBloc, DiaryState>(
      builder: (context, state) {
        if (state is DiaryLoading || state is DiaryInitial) {
          return const Center(child: CircularProgressIndicator());
        }
        if (state is DiaryPremiumLocked) {
          return _PremiumLockView(message: state.message, isWrite: state.isWrite);
        }
        if (state is DiaryError) {
          // MG_T10: offline -> only the global banner, no error view.
          if (context.watch<ConnectivityCubit>().state ==
              ConnectivityStatus.offline) {
            return const Center(
                child: Icon(Icons.cloud_off, size: 48, color: Colors.black26));
          }
          return Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.error_outline, size: 56, color: Colors.red),
                const SizedBox(height: 12),
                Text(state.message, textAlign: TextAlign.center),
                TextButton(onPressed: _load, child: const Text('Повторить')),
              ],
            ),
          );
        }
        if (state is DiaryLoaded) {
          return _LoadedView(
            state: state,
            onMarkEaten: (entry, eaten) {
              context
                  .read<DiaryBloc>()
                  .add(DiaryMarkEatenRequested(entryId: entry.id, isEaten: eaten));
            },
            onMarkMany: (ids, eaten) {
              context
                  .read<DiaryBloc>()
                  .add(DiaryMarkManyEatenRequested(entryIds: ids, isEaten: eaten));
            },
            onDelete: (entry) {
              context.read<DiaryBloc>().add(DiaryDeleteRequested(entry.id));
            },
          );
        }
        return const SizedBox.shrink();
      },
    );
  }

  void _onImportTap() async {
    final bloc = context.read<DiaryBloc>();
    // MG_DIARYMENU: выбор меню из выпадающего списка вместо ввода сырого ID.
    final menuId = await showDialog<int?>(
      context: context,
      builder: (_) => _ImportMenuDialog(
        initialDate: _selected,
        apiClient: bloc.apiClient,
      ),
    );
    if (menuId == null) return;
    if (!mounted) return;
    bloc.add(
      DiaryImportFromMenuRequested(
        menuId: menuId,
        date: DateFormat('yyyy-MM-dd').format(_selected),
        memberId: _memberId,
      ),
    );
  }

  // DIARY_V2: manual add dialog.
  void _onAddManualTap() async {
    final result = await showDialog<_ManualEntry?>(
      context: context,
      builder: (_) => const _AddManualDialog(),
    );
    if (result == null) return;
    if (!mounted) return;
    final nutrition = <String, dynamic>{};
    if (result.calories != null) {
      nutrition['calories'] = {'value': result.calories.toString(), 'unit': 'ккал'};
    }
    if (result.proteins != null) {
      nutrition['proteins'] = {'value': result.proteins.toString(), 'unit': 'г'};
    }
    if (result.fats != null) {
      nutrition['fats'] = {'value': result.fats.toString(), 'unit': 'г'};
    }
    if (result.carbs != null) {
      nutrition['carbs'] = {'value': result.carbs.toString(), 'unit': 'г'};
    }
    context.read<DiaryBloc>().add(DiaryAddManualRequested(
          date: DateFormat('yyyy-MM-dd').format(_selected),
          mealType: result.mealType,
          customName: result.name,
          quantity: result.quantity,
          nutrition: nutrition,
        ));
  }

  // DIARY_COPY_V3: copy-from-day dialog (#4).
  void _onCopyTap() async {
    final bloc = context.read<DiaryBloc>();
    final ids = await showDialog<List<int>?>(
      context: context,
      builder: (_) => _CopyFromDayDialog(
        apiClient: bloc.apiClient,
        memberId: _memberId,
      ),
    );
    if (ids == null || ids.isEmpty) return;
    if (!mounted) return;
    bloc.add(DiaryCopyRequested(
      entryIds: ids,
      targetDate: DateFormat('yyyy-MM-dd').format(_selected),
      memberId: _memberId,
    ));
  }

}

class _LoadedView extends StatefulWidget {
  final DiaryLoaded state;
  final void Function(DiaryEntry, bool) onMarkEaten;
  final void Function(List<int>, bool) onMarkMany; // MG_SKIN: branch / all
  final void Function(DiaryEntry) onDelete;
  const _LoadedView({
    required this.state,
    required this.onMarkEaten,
    required this.onMarkMany,
    required this.onDelete,
  });

  @override
  State<_LoadedView> createState() => _LoadedViewState();
}

class _LoadedViewState extends State<_LoadedView> {
  // Свёрнутые ветки приёмов (по умолчанию все развёрнуты).
  final Set<MealType> _collapsed = <MealType>{};

  static const List<MealType> _mealOrder = [
    MealType.breakfast,
    MealType.lunch,
    MealType.dinner,
    MealType.snack,
  ];

  @override
  Widget build(BuildContext context) {
    final planned = widget.state.plannedEntries;
    final manual = widget.state.manualEntries;
    return Column(
      children: [
        // MG_SKIN: «прилеплённая» сводка КБЖУ — не уезжает при скролле.
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 6, 12, 2),
          child: DiaryStatsCard(stats: widget.state.stats),
        ),
        Expanded(
          child: ListView(
            // MG_SKIN: сохраняем позицию скролла при check/uncheck.
            key: const PageStorageKey('diary-entries'),
            padding: const EdgeInsets.fromLTRB(12, 6, 12, 8),
            children: [
              if (planned.isEmpty && manual.isEmpty)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 32),
                  child: Center(child: Text('Нет записей')),
                ),
              if (planned.isNotEmpty) ..._buildPlanTree(planned),
              if (manual.isNotEmpty) ...[
                const SizedBox(height: 12),
                _SectionHeader(
                  icon: Icons.restaurant,
                  title: 'Факт (${manual.length})',
                ),
                ...manual.map((e) => _EntryTile(
                      entry: e,
                      onToggleEaten: null, // manual entries are always actual
                      onDelete: () => widget.onDelete(e),
                    )),
              ],
              const SizedBox(height: 96),
            ],
          ),
        ),
      ],
    );
  }

  // MG_SKIN: «дерево» плана — мастер-чекбокс + ветки приёмов + листья.
  List<Widget> _buildPlanTree(List<DiaryEntry> planned) {
    final total = planned.length;
    final eaten = planned.where((e) => e.isEaten).length;
    final allEaten = total > 0 && eaten == total;
    final noneEaten = eaten == 0;
    final allIds = planned.map((e) => e.id).toList();

    final out = <Widget>[];

    // Мастер-строка: чекнуть/снять весь план.
    out.add(Row(
      children: [
        Checkbox(
          tristate: true,
          value: allEaten ? true : (noneEaten ? false : null),
          onChanged: (_) => widget.onMarkMany(allIds, !allEaten),
        ),
        const Icon(Icons.event_note, size: 18),
        const SizedBox(width: 6),
        const Expanded(
          child: Text('План',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
        ),
        Text('$eaten/$total',
            style: TextStyle(color: Colors.grey.shade600, fontSize: 13)),
        const SizedBox(width: 8),
      ],
    ));

    for (final mt in _mealOrder) {
      final items = planned.where((e) => e.mealType == mt).toList();
      if (items.isEmpty) continue;
      final mEaten = items.where((e) => e.isEaten).length;
      final mAll = mEaten == items.length;
      final mNone = mEaten == 0;
      final mIds = items.map((e) => e.id).toList();
      final collapsed = _collapsed.contains(mt);

      // Заголовок ветки: чекбокс всей ветки + сворачивание.
      out.add(InkWell(
        onTap: () => setState(() {
          if (!_collapsed.remove(mt)) _collapsed.add(mt);
        }),
        child: Padding(
          padding: const EdgeInsets.only(left: 8, top: 2),
          child: Row(
            children: [
              Checkbox(
                tristate: true,
                value: mAll ? true : (mNone ? false : null),
                onChanged: (_) => widget.onMarkMany(mIds, !mAll),
              ),
              Expanded(
                child: Text('${mt.label} ($mEaten/${items.length})',
                    style: const TextStyle(fontWeight: FontWeight.w600)),
              ),
              AnimatedRotation(
                turns: collapsed ? -0.25 : 0.0,
                duration: const Duration(milliseconds: 180),
                child: const Icon(Icons.keyboard_arrow_down, size: 22),
              ),
              const SizedBox(width: 4),
            ],
          ),
        ),
      ));

      if (!collapsed) {
        for (final e in items) {
          out.add(Padding(
            padding: const EdgeInsets.only(left: 16),
            child: _EntryTile(
              entry: e,
              onToggleEaten: (v) => widget.onMarkEaten(e, v),
              onDelete: () => widget.onDelete(e),
            ),
          ));
        }
      }
    }
    return out;
  }
}

class _SectionHeader extends StatelessWidget {
  final IconData icon;
  final String title;
  const _SectionHeader({required this.icon, required this.title});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 8),
      child: Row(children: [
        Icon(icon, size: 18, color: Colors.grey.shade600),
        const SizedBox(width: 6),
        Text(title, style: const TextStyle(fontWeight: FontWeight.bold)),
      ]),
    );
  }
}

class _EntryTile extends StatelessWidget {
  final DiaryEntry entry;
  final void Function(bool)? onToggleEaten;
  final VoidCallback onDelete;

  const _EntryTile({
    required this.entry,
    required this.onToggleEaten,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    return Dismissible(
      key: ValueKey('diary-${entry.id}'),
      direction: DismissDirection.endToStart,
      background: Container(
        color: Colors.red,
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: const Icon(Icons.delete, color: Colors.white),
      ),
      onDismissed: (_) => onDelete(),
      child: Card(
        margin: const EdgeInsets.symmetric(vertical: 4),
        child: ListTile(
          leading: onToggleEaten != null
              ? Checkbox(
                  value: entry.isEaten,
                  onChanged: (v) => onToggleEaten!(v ?? false),
                )
              : const Icon(Icons.check_circle, color: Colors.green),
          title: Text(
            entry.displayTitle.isNotEmpty ? entry.displayTitle : '—',
          ),
          subtitle: Text(entry.mealType.label),
          trailing: Text('×${entry.quantity.toStringAsFixed(entry.quantity == entry.quantity.roundToDouble() ? 0 : 1)}'),
        ),
      ),
    );
  }
}

class _PremiumLockView extends StatelessWidget {
  final String message;
  final bool isWrite;
  const _PremiumLockView({required this.message, required this.isWrite});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.lock_outline, size: 72, color: Colors.grey.shade600),
          const SizedBox(height: 16),
          Text(
            isWrite ? 'Дневник в режиме чтения' : 'Дневник доступен по Premium',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 8),
          Text(message, textAlign: TextAlign.center),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: () {
              // Navigate via go_router push — paywall is at /paywall.
              // Read PremiumGateCubit so it has context if needed.
              context.read<PremiumGateCubit>();
              Navigator.of(context).pushNamed('/paywall');
            },
            child: const Text('Подключить Premium'),
          ),
        ],
      ),
    );
  }
}

// MG_DIARYMENU: выпадающий список меню вместо ручного ввода ID (ID — внутреннее
// обозначение, пользователю не известно). Грузим /menu/ как в shopping_create_sheet.
class _ImportMenuDialog extends StatefulWidget {
  final DateTime initialDate;
  final ApiClient apiClient;
  const _ImportMenuDialog({required this.initialDate, required this.apiClient});
  @override
  State<_ImportMenuDialog> createState() => _ImportMenuDialogState();
}

class _ImportMenuDialogState extends State<_ImportMenuDialog> {
  List<Map<String, dynamic>> _menus = const [];
  int? _menuId;
  bool _loading = true;
  String? _err;

  @override
  void initState() {
    super.initState();
    _loadMenus();
  }

  // Человекочитаемый лейбл меню (автор + диапазон дат), как в списках покупок.
  String _menuLabel(Map<String, dynamic> m) {
    String dm(Object? iso) {
      final s = iso?.toString() ?? '';
      if (s.length < 10) return '';
      return '${s.substring(8, 10)}.${s.substring(5, 7)}';
    }

    final name = (m['creator_name'] as String?)?.trim() ?? '';
    final a = dm(m['start_date']);
    final b = dm(m['end_date']);
    final dates = (a.isNotEmpty && b.isNotEmpty) ? '$a–$b' : '';
    final parts = [name, dates].where((e) => e.isNotEmpty).toList();
    return parts.isEmpty ? 'Меню #${m['id']}' : parts.join(' ');
  }

  Future<void> _loadMenus() async {
    try {
      final r = await widget.apiClient.get('/menu/');
      final list = (r is Map ? r['results'] : r);
      if (!mounted) return;
      if (list is List) {
        final menus = list
            .whereType<Map>()
            .map((e) => Map<String, dynamic>.from(e))
            .toList();
        setState(() {
          _menus = menus;
          _menuId = menus.isNotEmpty ? menus.first['id'] as int? : null;
          _loading = false;
        });
      } else {
        setState(() => _loading = false);
      }
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _err = 'Не удалось загрузить меню';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Импорт из меню'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'На дату: ${DateFormat('d MMMM yyyy', 'ru').format(widget.initialDate)}',
            style: const TextStyle(fontSize: 13, color: Colors.grey),
          ),
          const SizedBox(height: 12),
          if (_loading)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 16),
              child: Center(child: CircularProgressIndicator()),
            )
          else if (_menus.isEmpty)
            Text(
              _err ?? 'Нет доступных меню. Сначала сгенерируйте меню.',
              style: const TextStyle(fontSize: 13, color: Colors.grey),
            )
          else
            DropdownButtonFormField<int>(
              value: _menuId,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'Меню'),
              items: _menus
                  .map((m) => DropdownMenuItem<int>(
                        value: m['id'] as int?,
                        child: Text(
                          _menuLabel(m),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ))
                  .toList(),
              onChanged: (v) => setState(() => _menuId = v),
            ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context, null),
          child: const Text('Отмена'),
        ),
        FilledButton(
          onPressed: (_loading || _menuId == null)
              ? null
              : () => Navigator.pop(context, _menuId),
          child: const Text('Импортировать'),
        ),
      ],
    );
  }
}


// DIARY_V2: water tracker card under calendar.
class _WaterCard extends StatefulWidget {
  final void Function(int delta) onAdd;
  final void Function(int ml) onSet;
  const _WaterCard({required this.onAdd, required this.onSet});
  @override
  State<_WaterCard> createState() => _WaterCardState();
}

class _WaterCardState extends State<_WaterCard> {
  static const int _goal = 2000;
  final _ctrl = TextEditingController();
  bool _expanded = false; // MG_SKIN: по умолчанию свёрнуто в строчку

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final st = context.watch<DiaryBloc>().state;
    final ml = st is DiaryLoaded ? st.waterMl : 0;
    final pct = (_goal == 0) ? 0.0 : (ml / _goal).clamp(0.0, 1.0);
    return Card(
      margin: const EdgeInsets.fromLTRB(12, 6, 12, 2),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Свёрнутая строка-сводка (тап — развернуть управление).
          InkWell(
            onTap: () => setState(() => _expanded = !_expanded),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              child: Row(
                children: [
                  const Text('💧', style: TextStyle(fontSize: 16)),
                  const SizedBox(width: 8),
                  const Text('Вода',
                      style: TextStyle(fontWeight: FontWeight.bold)),
                  const SizedBox(width: 10),
                  Expanded(
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(4),
                      child: LinearProgressIndicator(value: pct, minHeight: 6),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Text('$ml/$_goal мл',
                      style:
                          TextStyle(fontSize: 12, color: Colors.grey.shade600)),
                  const SizedBox(width: 2),
                  AnimatedRotation(
                    turns: _expanded ? 0.0 : -0.25,
                    duration: const Duration(milliseconds: 180),
                    child: const Icon(Icons.keyboard_arrow_down, size: 20),
                  ),
                ],
              ),
            ),
          ),
          if (_expanded)
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
              child: Wrap(
                spacing: 8,
                runSpacing: 4,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  OutlinedButton(
                      onPressed: () => widget.onAdd(250),
                      child: const Text('+250 мл')),
                  OutlinedButton(
                      onPressed: () => widget.onAdd(500),
                      child: const Text('+500 мл')),
                  OutlinedButton(
                    onPressed: ml <= 0 ? null : () => widget.onAdd(-250),
                    child: const Text('−250 мл'),
                  ),
                  SizedBox(
                    width: 90,
                    child: TextField(
                      controller: _ctrl,
                      keyboardType: TextInputType.number,
                      decoration:
                          const InputDecoration(hintText: 'мл', isDense: true),
                    ),
                  ),
                  TextButton(
                    onPressed: () {
                      final v = int.tryParse(_ctrl.text.trim());
                      if (v != null) {
                        widget.onSet(v);
                        _ctrl.clear();
                        FocusScope.of(context).unfocus();
                      }
                    },
                    child: const Text('Задать'),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

// DIARY_V2: result of manual-add dialog.
class _ManualEntry {
  final MealType mealType;
  final String name;
  final double quantity;
  final num? calories;
  final num? proteins;
  final num? fats;
  final num? carbs;
  const _ManualEntry({
    required this.mealType,
    required this.name,
    required this.quantity,
    this.calories,
    this.proteins,
    this.fats,
    this.carbs,
  });
}

class _AddManualDialog extends StatefulWidget {
  const _AddManualDialog();
  @override
  State<_AddManualDialog> createState() => _AddManualDialogState();
}

class _AddManualDialogState extends State<_AddManualDialog> {
  MealType _meal = MealType.breakfast;
  final _name = TextEditingController();
  final _qty = TextEditingController(text: '1');
  final _cal = TextEditingController();
  final _prot = TextEditingController();
  final _fat = TextEditingController();
  final _carb = TextEditingController();
  String? _error;

  @override
  void dispose() {
    _name.dispose();
    _qty.dispose();
    _cal.dispose();
    _prot.dispose();
    _fat.dispose();
    _carb.dispose();
    super.dispose();
  }

  num? _n(TextEditingController c) {
    final v = double.tryParse(c.text.trim().replaceAll(',', '.'));
    return v;
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Добавить вручную'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // DIARY_COPY_V3: spaced fields — fixes overlapping labels (#3).
            DropdownButtonFormField<MealType>(
              value: _meal,
              isExpanded: true,
              decoration: const InputDecoration(
                labelText: 'Приём пищи',
                isDense: true,
                border: OutlineInputBorder(),
                contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 12),
              ),
              items: MealType.values
                  .map((m) => DropdownMenuItem(value: m, child: Text(m.label)))
                  .toList(),
              onChanged: (v) => setState(() => _meal = v ?? MealType.breakfast),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _name,
              decoration: const InputDecoration(
                labelText: 'Название',
                isDense: true,
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _qty,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration: const InputDecoration(
                labelText: 'Количество (порций)',
                isDense: true,
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _cal,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration: const InputDecoration(
                labelText: 'Калории (ккал)',
                isDense: true,
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _prot,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration: const InputDecoration(
                labelText: 'Белки (г)',
                isDense: true,
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _fat,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration: const InputDecoration(
                labelText: 'Жиры (г)',
                isDense: true,
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _carb,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration: const InputDecoration(
                labelText: 'Углеводы (г)',
                isDense: true,
                border: OutlineInputBorder(),
              ),
            ),
            if (_error != null) ...[
              const SizedBox(height: 8),
              Text(_error!, style: const TextStyle(color: Colors.red, fontSize: 13)),
            ],
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context, null), child: const Text('Отмена')),
        FilledButton(
          onPressed: () {
            if (_name.text.trim().isEmpty) {
              setState(() => _error = 'Укажите название блюда');
              return;
            }
            Navigator.pop(
              context,
              _ManualEntry(
                mealType: _meal,
                name: _name.text.trim(),
                quantity: _n(_qty)?.toDouble() ?? 1.0,
                calories: _n(_cal),
                proteins: _n(_prot),
                fats: _n(_fat),
                carbs: _n(_carb),
              ),
            );
          },
          child: const Text('Добавить'),
        ),
      ],
    );
  }
}


// DIARY_COPY_V3: pick a source day, check entries, return selected ids.
class _CopyFromDayDialog extends StatefulWidget {
  final ApiClient apiClient;
  final int? memberId;
  const _CopyFromDayDialog({required this.apiClient, required this.memberId});
  @override
  State<_CopyFromDayDialog> createState() => _CopyFromDayDialogState();
}

class _CopyFromDayDialogState extends State<_CopyFromDayDialog> {
  DateTime _sourceDay = DateTime.now();
  bool _loading = false;
  String? _error;
  List<DiaryEntry> _entries = const [];
  final Set<int> _selected = <int>{};

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
      _selected.clear();
    });
    try {
      final params = <String, dynamic>{
        'date': DateFormat('yyyy-MM-dd').format(_sourceDay),
      };
      if (widget.memberId != null) params['member_id'] = widget.memberId;
      final resp = await widget.apiClient.get('/diary/', params: params);
      final root = resp is Map ? resp : <String, dynamic>{};
      final list = (root['results'] ?? const []) as List;
      final parsed = list
          .whereType<Map>()
          .map((e) => DiaryEntry.fromJson(Map<String, dynamic>.from(e)))
          .toList();
      if (!mounted) return;
      setState(() {
        _entries = parsed;
        _loading = false;
      });
    } catch (err) {
      if (!mounted) return;
      setState(() {
        _error = err.toString();
        _loading = false;
      });
    }
  }

  Future<void> _pickDay() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _sourceDay,
      firstDate: DateTime(2020),
      lastDate: DateTime.now(),
    );
    if (picked != null) {
      setState(() => _sourceDay = picked);
      _load();
    }
  }

  @override
  Widget build(BuildContext context) {
    final allChecked = _entries.isNotEmpty && _selected.length == _entries.length;
    return AlertDialog(
      title: const Text('Копировать из дня'),
      content: SizedBox(
        width: double.maxFinite,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            OutlinedButton.icon(
              onPressed: _pickDay,
              icon: const Icon(Icons.calendar_today, size: 18),
              label: Text('Источник: ${DateFormat('d MMMM yyyy', 'ru').format(_sourceDay)}'),
            ),
            const SizedBox(height: 8),
            if (_loading)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 24),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (_error != null)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 16),
                child: Text(_error!, style: const TextStyle(color: Colors.red, fontSize: 13)),
              )
            else if (_entries.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 24),
                child: Center(child: Text('Нет записей за этот день')),
              )
            else ...[
              CheckboxListTile(
                dense: true,
                contentPadding: EdgeInsets.zero,
                title: Text('Выбрать все (${_entries.length})'),
                value: allChecked,
                onChanged: (v) => setState(() {
                  _selected.clear();
                  if (v == true) {
                    _selected.addAll(_entries.map((e) => e.id));
                  }
                }),
              ),
              const Divider(height: 1),
              Flexible(
                child: ListView.builder(
                  shrinkWrap: true,
                  itemCount: _entries.length,
                  itemBuilder: (_, i) {
                    final e = _entries[i];
                    final title = e.displayTitle.isNotEmpty ? e.displayTitle : '—';
                    return CheckboxListTile(
                      dense: true,
                      contentPadding: EdgeInsets.zero,
                      value: _selected.contains(e.id),
                      onChanged: (v) => setState(() {
                        if (v == true) {
                          _selected.add(e.id);
                        } else {
                          _selected.remove(e.id);
                        }
                      }),
                      title: Text(title),
                      subtitle: Text(e.mealType.label),
                    );
                  },
                ),
              ),
            ],
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context, null),
          child: const Text('Отмена'),
        ),
        FilledButton(
          onPressed: _selected.isEmpty
              ? null
              : () => Navigator.pop(context, _selected.toList()),
          child: Text('Копировать (${_selected.length})'),
        ),
      ],
    );
  }
}
