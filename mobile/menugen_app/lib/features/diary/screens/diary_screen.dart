import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:intl/intl.dart';
import 'package:table_calendar/table_calendar.dart';

import '../../../core/premium/premium_gate_cubit.dart';
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
  int? _memberId;

  @override
  void initState() {
    super.initState();
    _load();
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
        title: const Text('Дневник питания'),
        actions: [
          IconButton(
            icon: const Icon(Icons.download_for_offline_outlined),
            tooltip: 'Импорт из меню',
            onPressed: _onImportTap,
          ),
        ],
      ),
      body: Column(
        children: [
          TableCalendar(
            firstDay: DateTime(2020),
            lastDay: DateTime(2030),
            focusedDay: _selected,
            selectedDayPredicate: (d) => isSameDay(d, _selected),
            onDaySelected: (sel, _) {
              setState(() => _selected = sel);
              _load();
            },
            calendarFormat: CalendarFormat.week,
          ),
          Expanded(child: _buildBody()),
        ],
      ),
    );
  }

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
    final menuIdText = await showDialog<String?>(
      context: context,
      builder: (_) => _ImportMenuDialog(initialDate: _selected),
    );
    if (menuIdText == null) return;
    final menuId = int.tryParse(menuIdText);
    if (menuId == null) return;
    if (!mounted) return;
    context.read<DiaryBloc>().add(
          DiaryImportFromMenuRequested(
            menuId: menuId,
            date: DateFormat('yyyy-MM-dd').format(_selected),
            memberId: _memberId,
          ),
        );
  }
}

class _LoadedView extends StatelessWidget {
  final DiaryLoaded state;
  final void Function(DiaryEntry, bool) onMarkEaten;
  final void Function(DiaryEntry) onDelete;
  const _LoadedView({
    required this.state,
    required this.onMarkEaten,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final planned = state.plannedEntries;
    final manual = state.manualEntries;
    return ListView(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      children: [
        DiaryStatsCard(stats: state.stats),
        const SizedBox(height: 12),
        if (planned.isEmpty && manual.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 32),
            child: Center(child: Text('Нет записей')),
          ),
        if (planned.isNotEmpty) ...[
          _SectionHeader(
            icon: Icons.event_note,
            title: 'План (${planned.length})',
          ),
          ...planned.map((e) => _EntryTile(
                entry: e,
                onToggleEaten: (v) => onMarkEaten(e, v),
                onDelete: () => onDelete(e),
              )),
        ],
        if (manual.isNotEmpty) ...[
          const SizedBox(height: 12),
          _SectionHeader(
            icon: Icons.restaurant,
            title: 'Факт (${manual.length})',
          ),
          ...manual.map((e) => _EntryTile(
                entry: e,
                onToggleEaten: null, // manual entries are always actual
                onDelete: () => onDelete(e),
              )),
        ],
        const SizedBox(height: 80),
      ],
    );
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

class _ImportMenuDialog extends StatefulWidget {
  final DateTime initialDate;
  const _ImportMenuDialog({required this.initialDate});
  @override
  State<_ImportMenuDialog> createState() => _ImportMenuDialogState();
}

class _ImportMenuDialogState extends State<_ImportMenuDialog> {
  final _ctrl = TextEditingController();

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
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
          TextField(
            controller: _ctrl,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(
              labelText: 'ID меню',
              hintText: 'Например, 42',
            ),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context, null),
          child: const Text('Отмена'),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(context, _ctrl.text.trim()),
          child: const Text('Импортировать'),
        ),
      ],
    );
  }
}
