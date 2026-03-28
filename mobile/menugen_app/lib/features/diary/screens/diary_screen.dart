import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:intl/intl.dart';
import '../bloc/diary_bloc.dart';

class DiaryScreen extends StatefulWidget {
  const DiaryScreen({super.key});
  @override State<DiaryScreen> createState() => _DiaryScreenState();
}
class _DiaryScreenState extends State<DiaryScreen> {
  DateTime _selected = DateTime.now();
  @override void initState() { super.initState(); _load(); }
  void _load() => context.read<DiaryBloc>().add(DiaryLoadRequested(DateFormat('yyyy-MM-dd').format(_selected)));

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Дневник питания')),
      body: Column(children: [
        SizedBox(height: 70, child: ListView.builder(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          itemCount: 14,
          itemBuilder: (_, i) {
            final day = DateTime.now().subtract(Duration(days: 6 - i));
            final fmt = DateFormat('yyyy-MM-dd');
            final sel = fmt.format(day) == fmt.format(_selected);
            return GestureDetector(
              onTap: () { setState(() => _selected = day); _load(); },
              child: Container(width: 48, margin: const EdgeInsets.only(right: 8),
                decoration: BoxDecoration(
                  color: sel ? Theme.of(context).colorScheme.primary : Colors.grey.shade100,
                  borderRadius: BorderRadius.circular(12)),
                child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                  Text(DateFormat('EE', 'ru').format(day),
                      style: TextStyle(fontSize: 11, color: sel ? Colors.white : Colors.grey)),
                  Text('\${day.day}', style: TextStyle(fontWeight: FontWeight.bold,
                      color: sel ? Colors.white : Colors.black87)),
                ])));
          })),
        Expanded(child: BlocBuilder<DiaryBloc, DiaryState>(builder: (context, state) {
          if (state is DiaryLoading) return const Center(child: CircularProgressIndicator());
          if (state is DiaryLoaded) {
            if (state.entries.isEmpty) return const Center(child: Text('Нет записей за этот день'));
            return ListView.builder(padding: const EdgeInsets.all(12),
              itemCount: state.entries.length,
              itemBuilder: (_, i) {
                final e = state.entries[i];
                return ListTile(title: Text(e.recipeTitle ?? e.customName ?? ''), subtitle: Text(e.mealType));
              });
          }
          return const SizedBox.shrink();
        })),
      ]),
    );
  }
}
