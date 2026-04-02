import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:intl/intl.dart';
import '../bloc/menu_bloc.dart';

class GenerateMenuBottomSheet extends StatefulWidget {
  const GenerateMenuBottomSheet({super.key});
  @override
  State<GenerateMenuBottomSheet> createState() => _State();
}

class _State extends State<GenerateMenuBottomSheet> {
  int _days = 7;
  DateTime _start = DateTime.now();
  String _country = '';
  int? _maxCookTime;
  final _countryCtrl = TextEditingController();
  final _cookTimeCtrl = TextEditingController();

  static const _countries = ['', 'Россия', 'Италия', 'Франция', 'Япония', 'Китай', 'Мексика', 'Индия', 'Греция'];
  static const _cookTimes = [null, 15, 30, 45, 60, 90, 120];

  @override
  void dispose() {
    _countryCtrl.dispose();
    _cookTimeCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.fromLTRB(24, 24, 24, MediaQuery.of(context).viewInsets.bottom + 24),
      child: SingleChildScrollView(
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Генерация меню', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
          const SizedBox(height: 20),

          // Дата начала
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.calendar_today),
            title: Text('Дата начала: ${DateFormat('dd.MM.yyyy').format(_start)}'),
            onTap: () async {
              final d = await showDatePicker(
                context: context,
                initialDate: _start,
                firstDate: DateTime.now(),
                lastDate: DateTime.now().add(const Duration(days: 30)),
              );
              if (d != null) setState(() => _start = d);
            },
          ),
          const Divider(),

          // Количество дней
          Row(children: [
            const Icon(Icons.date_range, color: Colors.grey),
            const SizedBox(width: 12),
            const Text('Дней:'),
            Expanded(child: Slider(
              value: _days.toDouble(), min: 1, max: 14, divisions: 13, label: '$_days',
              onChanged: (v) => setState(() => _days = v.round()),
            )),
            Text('$_days', style: const TextStyle(fontWeight: FontWeight.bold)),
          ]),
          const Divider(),

          // Страна кухни
          const Text('Кухня', style: TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          Wrap(spacing: 8, children: _countries.map((c) {
            final label = c.isEmpty ? 'Любая' : c;
            return ChoiceChip(
              label: Text(label),
              selected: _country == c,
              onSelected: (_) => setState(() => _country = c),
            );
          }).toList()),
          const SizedBox(height: 16),

          // Макс время готовки
          const Text('Макс. время готовки', style: TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          Wrap(spacing: 8, children: _cookTimes.map((t) {
            final label = t == null ? 'Любое' : '$t мин';
            return ChoiceChip(
              label: Text(label),
              selected: _maxCookTime == t,
              onSelected: (_) => setState(() => _maxCookTime = t),
            );
          }).toList()),
          const SizedBox(height: 24),

          // Кнопка
          SizedBox(width: double.infinity,
            child: ElevatedButton.icon(
              icon: const Icon(Icons.auto_awesome),
              label: const Text('Сгенерировать'),
              style: ElevatedButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 14)),
              onPressed: () {
                final data = <String, dynamic>{
                  'start_date': DateFormat('yyyy-MM-dd').format(_start),
                  'period_days': _days,
                };
                if (_country.isNotEmpty) data['country'] = _country;
                if (_maxCookTime != null) data['max_cook_time'] = _maxCookTime;
                context.read<MenuBloc>().add(MenuGenerateRequested(
                  startDate: DateFormat('yyyy-MM-dd').format(_start),
                  periodDays: _days,
                  country: _country.isEmpty ? null : _country,
                  maxCookTime: _maxCookTime,
                ));
                Navigator.pop(context);
              },
            ),
          ),
        ]),
      ),
    );
  }
}