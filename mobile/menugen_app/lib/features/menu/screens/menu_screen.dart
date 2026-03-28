import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:intl/intl.dart';
import '../bloc/menu_bloc.dart';
import '../widgets/menu_day_card.dart';
import '../widgets/generate_menu_bottom_sheet.dart';

class MenuScreen extends StatelessWidget {
  const MenuScreen({super.key});

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

          final menus = state is MenuLoaded ? state.menus
              : state is MenuGenerated ? [state.menu] : <dynamic>[];

          if (menus.isEmpty) {
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
                const SizedBox(height: 24),
                ElevatedButton.icon(
                  onPressed: () => _showGenerateSheet(context),
                  icon: const Icon(Icons.auto_awesome),
                  label: const Text('Сгенерировать меню'),
                ),
              ]),
            ));
          }

          final menu = menus.first;
          return RefreshIndicator(
            onRefresh: () async => context.read<MenuBloc>().add(MenuLoadRequested()),
            child: ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: menu.periodDays,
              itemBuilder: (context, day) {
                final dayItems = menu.items.where((i) => i.dayOffset == day).toList();
                final date = DateTime.parse(menu.startDate).add(Duration(days: day));
                return MenuDayCard(date: date, items: dayItems, menuId: menu.id);
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
