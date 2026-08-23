import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../connectivity/connectivity_cubit.dart';
import '../premium/paywall_banner.dart';
import '../premium/premium_gate_cubit.dart';
import '../update/self_update_watcher.dart'; // MG_SELFUPDATE
import 'connectivity_banner.dart';
import 'sync_indicator.dart'; // MG_T08

typedef _Tab = ({IconData icon, String label, int branch});

class MainShell extends StatelessWidget {
  // MG_TABSTATE: navigationShell = IndexedStack всех вкладок (состояние сохраняется).
  final StatefulNavigationShell navigationShell;
  const MainShell({super.key, required this.navigationShell});

  // branch = индекс ветки в StatefulShellRoute (см. app_router).
  static const _allTabs = <_Tab>[
    (icon: Icons.restaurant_menu, label: 'Меню',        branch: 0),
    (icon: Icons.menu_book,       label: 'Рецепты',     branch: 1),
    (icon: Icons.kitchen,         label: 'Холодильник', branch: 2),
    (icon: Icons.shopping_cart,   label: 'Покупки',     branch: 3),
    (icon: Icons.book,            label: 'Дневник',     branch: 4),
    (icon: Icons.person,          label: 'Профиль',     branch: 5),
  ];

  // freemium: дневник открыт free-юзерам (как в вебе). Холодильник остаётся premium.
  static const _premiumOnlyBranches = {2}; // fridge

  List<_Tab> _visibleTabs(PremiumStatus status) {
    if (status == PremiumStatus.lockedForRead) {
      return _allTabs.where((t) => !_premiumOnlyBranches.contains(t.branch)).toList();
    }
    return _allTabs;
  }

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<PremiumGateCubit, PremiumGateState>(
      builder: (context, premiumState) {
        final tabs = _visibleTabs(premiumState.status);
        int currentIdx = tabs.indexWhere((t) => t.branch == navigationShell.currentIndex);
        if (currentIdx < 0) currentIdx = 0;
        return Scaffold(
          body: SafeArea( // MG_T09: keep indicator/banners below the status bar
            bottom: false,
            child: Column(
            children: [
              const SelfUpdateWatcher(), // MG_SELFUPDATE: ничего не рисует
              const SyncIndicator(), // MG_T08
              const ConnectivityBanner(),
              const PaywallBanner(),
              Expanded(child: navigationShell),
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
                currentIndex: currentIdx,
                onTap: (i) => navigationShell.goBranch(
                  tabs[i].branch,
                  initialLocation: tabs[i].branch == navigationShell.currentIndex,
                ),
                elevation: 0,
                backgroundColor: Colors.transparent,
                items: tabs.map((t) => BottomNavigationBarItem(
                  icon: Icon(t.icon),
                  label: t.label,
                )).toList(),
              ),
            ),
          ),
        );
      },
    );
  }
}
