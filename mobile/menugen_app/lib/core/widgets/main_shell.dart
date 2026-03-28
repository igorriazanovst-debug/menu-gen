import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../connectivity/connectivity_cubit.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'connectivity_banner.dart';

class MainShell extends StatelessWidget {
  final Widget child;
  const MainShell({super.key, required this.child});

  static const _tabs = [
    (icon: Icons.restaurant_menu, label: 'Меню',       path: '/menu'),
    (icon: Icons.menu_book,        label: 'Рецепты',    path: '/recipes'),
    (icon: Icons.kitchen,          label: 'Холодильник',path: '/fridge'),
    (icon: Icons.book,             label: 'Дневник',    path: '/diary'),
    (icon: Icons.person,           label: 'Профиль',    path: '/profile'),
  ];

  int _currentIndex(BuildContext context) {
    final location = GoRouterState.of(context).matchedLocation;
    final idx = _tabs.indexWhere((t) => location.startsWith(t.path));
    return idx >= 0 ? idx : 0;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(
        children: [
          const ConnectivityBanner(),
          Expanded(child: child),
        ],
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex(context),
        onTap: (i) => context.go(_tabs[i].path),
        items: _tabs.map((t) => BottomNavigationBarItem(
          icon: Icon(t.icon),
          label: t.label,
        )).toList(),
      ),
    );
  }
}
