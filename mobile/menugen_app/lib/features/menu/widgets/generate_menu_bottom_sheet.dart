import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:intl/intl.dart';
import '../bloc/menu_bloc.dart';
import '../../../core/theme/app_theme.dart';

class GenerateMenuBottomSheet extends StatefulWidget {
  const GenerateMenuBottomSheet({super.key});
  @override State<GenerateMenuBottomSheet> createState() => _GenerateMenuBottomSheetState();
}
class _GenerateMenuBottomSheetState extends State<GenerateMenuBottomSheet> {
  int _days = 7;
  String? _country;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
          left: 24, right: 24, top: 24,
          bottom: MediaQuery.of(context).viewInsets.bottom + 24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Center(child: Container(width: 40, height: 4,
              decoration: BoxDecoration(color: Colors.grey.shade300,
                  borderRadius: BorderRadius.circular(2)))),
          const SizedBox(height: 20),
          Text('Новое меню', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
          const SizedBox(height: 24),
          Row(children: [
            const Text('Дней:'),
            Expanded(child: Slider(value: _days.toDouble(), min: 1, max: 14, divisions: 13,
              label: '$_days', onChanged: (v) => setState(() => _days = v.round()))),
            Text('$_days', style: const TextStyle(fontWeight: FontWeight.w600)),
          ]),
          const SizedBox(height: 12),
          TextFormField(
            decoration: const InputDecoration(labelText: 'Страна (необязательно)',
                prefixIcon: Icon(Icons.flag_outlined), hintText: 'Например: Россия'),
            onChanged: (v) => _country = v.isEmpty ? null : v,
          ),
          const SizedBox(height: 24),
          BlocConsumer<MenuBloc, MenuState>(
            listener: (context, state) {
              if (state is MenuGenerated) Navigator.pop(context);
              if (state is MenuError) ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text(state.message), backgroundColor: AppColors.error));
            },
            builder: (context, state) {
              final loading = state is MenuGenerating;
              return ElevatedButton(
                onPressed: loading ? null : () => context.read<MenuBloc>().add(MenuGenerateRequested(
                  periodDays: _days,
                  startDate: DateFormat('yyyy-MM-dd').format(DateTime.now()),
                  country: _country,
                )),
                child: loading
                    ? const SizedBox(height: 22, width: 22,
                        child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                    : const Text('Сгенерировать'),
              );
            },
          ),
        ],
      ),
    );
  }
}
