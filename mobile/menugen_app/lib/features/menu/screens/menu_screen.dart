import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:intl/intl.dart';
import '../bloc/menu_bloc.dart';
import '../widgets/generate_menu_bottom_sheet.dart';

class MenuScreen extends StatefulWidget {
  const MenuScreen({super.key});
  @override
  State<MenuScreen> createState() => _MenuScreenState();
}

class _MenuScreenState extends State<MenuScreen> {
  @override
  void initState() {
    super.initState();
    context.read<MenuBloc>().add(MenuLoadRequested());
  }

  static const _mealLabels = {
    'breakfast': 'Завтрак',
    'lunch': 'Обед',
    'dinner': 'Ужин',
    'snack': 'Перекус',
  };

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Меню'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => context.read<MenuBloc>().add(MenuLoadRequested()),
          ),
        ],
      ),
      body: BlocBuilder<MenuBloc, MenuState>(
        builder: (context, state) {
          if (state is MenuLoading || state is MenuGenerating) {
            return const Center(child: CircularProgressIndicator());
          }
          if (state is MenuError) {
            return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
              const Icon(Icons.error_outline, size: 56, color: Colors.red),
              const SizedBox(height: 12),
              Text(state.message, textAlign: TextAlign.center),
              TextButton(
                onPressed: () => context.read<MenuBloc>().add(MenuLoadRequested()),
                child: const Text('Повторить'),
              ),
            ]));
          }

          Map<String, dynamic>? menu;
          if (state is MenuLoaded && state.menus.isNotEmpty) {
            menu = state.menus.first;
          } else if (state is MenuGenerated) {
            menu = state.menu;
          }

          if (menu == null) {
            return Center(child: Padding(
              padding: const EdgeInsets.all(32),
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                Icon(Icons.restaurant_menu, size: 80, color: Colors.grey.shade300),
                const SizedBox(height: 16),
                Text('Меню пока нет', style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 8),
                Text('Нажмите «Сгенерировать» чтобы составить меню на неделю',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: Colors.grey.shade600)),
              ]),
            ));
          }

          final items = (menu['items'] as List<dynamic>?) ?? [];
          final startDateStr = menu['start_date'] as String? ?? '';
          final periodDays = (menu['period_days'] as int?) ?? 7;

          DateTime? startDate;
          try { if (startDateStr.isNotEmpty) startDate = DateTime.parse(startDateStr); } catch (_) {}

          return RefreshIndicator(
            onRefresh: () async => context.read<MenuBloc>().add(MenuLoadRequested()),
            child: ListView.builder(
              padding: const EdgeInsets.all(12),
              itemCount: periodDays,
              itemBuilder: (context, day) {
                final dayItems = items
                    .where((i) => (i as Map<String, dynamic>)['day_offset'] == day)
                    .map((i) => i as Map<String, dynamic>)
                    .toList();
                final date = startDate?.add(Duration(days: day));
                final dateLabel = date != null
                    ? DateFormat('EEEE, d MMMM', 'ru').format(date)
                    : 'День ${day + 1}';

                return Card(
                  margin: const EdgeInsets.only(bottom: 10),
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(dateLabel,
                          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                      const SizedBox(height: 8),
                      if (dayItems.isEmpty)
                        const Text('Нет блюд', style: TextStyle(color: Colors.grey))
                      else
                        ...dayItems.map((item) {
                          final recipe = item['recipe'] as Map<String, dynamic>?;
                          final title = recipe?['title'] as String? ?? '';
                          final mealType = item['meal_type'] as String? ?? '';
                          final mealLabel = _mealLabels[mealType] ?? mealType;
                          final imageUrl = recipe?['image_url'] as String?;
                          return Padding(
                            padding: const EdgeInsets.symmetric(vertical: 4),
                            child: Row(children: [
                              if (imageUrl != null)
                                ClipRRect(
                                  borderRadius: BorderRadius.circular(6),
                                  child: Image.network(imageUrl,
                                      width: 48, height: 48, fit: BoxFit.cover,
                                      errorBuilder: (_, __, ___) =>
                                          const Icon(Icons.restaurant, size: 48)),
                                )
                              else
                                const Icon(Icons.restaurant, size: 48, color: Colors.grey),
                              const SizedBox(width: 10),
                              Expanded(child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(title, maxLines: 2,
                                      overflow: TextOverflow.ellipsis,
                                      style: const TextStyle(fontSize: 14)),
                                  Text(mealLabel,
                                      style: TextStyle(fontSize: 12, color: Colors.grey.shade600)),
                                ],
                              )),
                            ]),
                          );
                        }),
                    ]),
                  ),
                );
              },
            ),
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