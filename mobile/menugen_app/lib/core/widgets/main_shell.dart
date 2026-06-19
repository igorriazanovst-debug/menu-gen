import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../connectivity/connectivity_cubit.dart';
import '../premium/paywall_banner.dart';
import 'connectivity_banner.dart';
import 'sync_indicator.dart'; // MG_T08

class MainShell extends StatelessWidget {
  final Widget child;
  const MainShell({super.key, required this.child});

  static const _tabs = [
    (icon: Icons.restaurant_menu, label: 'Меню',       path: '/menu'),
    (icon: Icons.menu_book,        label: 'Рецепты',    path: '/recipes'),
    (icon: Icons.kitchen,          label: 'Холодильник',path: '/fridge'),
    (icon: Icons.shopping_cart,    label: 'Покупки',    path: '/shopping'),
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
      body: SafeArea( // MG_T09: keep indicator/banners below the status bar
        bottom: false,
        child: Column(
        children: [
          const SyncIndicator(), // MG_T08
          const ConnectivityBanner(),
          const PaywallBanner(),
          Expanded(child: child),
        ],
      )), // MG_T09: close SafeArea
      // MG_SKIN: скруглённая «плавающая» нижняя навигация в стиле Main-референса.
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surface,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.06),
              blurRadius: 16,
              offset: const Offset(0, -2),
            ),
          ],
        ),
        child: ClipRRect(
          borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
          child: BottomNavigationBar(
            currentIndex: _currentIndex(context),
            onTap: (i) => context.go(_tabs[i].path),
            elevation: 0,
            backgroundColor: Colors.transparent,
            items: _tabs.map((t) => BottomNavigationBarItem(
              icon: Icon(t.icon),
              label: t.label,
            )).toList(),
          ),
        ),
      ),
    );
  }
}
