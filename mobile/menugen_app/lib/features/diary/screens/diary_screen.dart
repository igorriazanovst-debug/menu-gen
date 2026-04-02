import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:table_calendar/table_calendar.dart';
import 'package:intl/intl.dart';
import '../bloc/diary_bloc.dart';

class DiaryScreen extends StatefulWidget {
  const DiaryScreen({super.key});
  @override
  State<DiaryScreen> createState() => _DiaryScreenState();
}

class _DiaryScreenState extends State<DiaryScreen> {
  DateTime _selected = DateTime.now();

  @override
  void initState() {
    super.initState();
    _load(_selected);
  }

  void _load(DateTime d) {
    context.read<DiaryBloc>().add(DiaryLoadRequested(DateFormat('yyyy-MM-dd').format(d)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Дневник питания')),
      body: Column(children: [
        TableCalendar(
          firstDay: DateTime(2020),
          lastDay: DateTime(2030),
          focusedDay: _selected,
          selectedDayPredicate: (d) => isSameDay(d, _selected),
          onDaySelected: (sel, _) { setState(() => _selected = sel); _load(sel); },
          calendarFormat: CalendarFormat.week,
        ),
        Expanded(child: BlocBuilder<DiaryBloc, DiaryState>(
          builder: (context, state) {
            if (state is DiaryLoading) return const Center(child: CircularProgressIndicator());
            if (state is DiaryError) return Center(child: Text(state.message));
            final entries = state is DiaryLoaded ? state.entries : <Map<String, dynamic>>[];
            if (entries.isEmpty) return const Center(child: Text('Нет записей'));
            return ListView.builder(
              itemCount: entries.length,
              itemBuilder: (_, i) {
                final e = entries[i] as Map<String, dynamic>;
                return ListTile(
                  title: Text(e['recipe_title'] as String? ?? e['custom_name'] as String? ?? ''),
                  subtitle: Text(e['meal_type'] as String? ?? ''),
                );
              },
            );
          },
        )),
      ]),
    );
  }
}