// MG-profile-premium: badge widget shown on ProfileScreen.
//
// Reads `subscription_status` map from /users/me/ payload and renders:
//   - active/non-trial premium → green "Premium до DD.MM.YYYY"
//   - active trial             → blue  "Триал до DD.MM.YYYY"
//   - has_ever && expired      → orange "Подписка истекла — продлить" (taps to /paywall)
//   - never paid / null        → nothing
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class PremiumBadge extends StatelessWidget {
  final Map<String, dynamic>? subscriptionStatus;
  const PremiumBadge({super.key, required this.subscriptionStatus});

  @override
  Widget build(BuildContext context) {
    final s = subscriptionStatus;
    if (s == null) return const SizedBox.shrink();

    final isActive = s['is_active_premium'] == true;
    final hasEver = s['has_ever_premium'] == true;
    final status = s['status'] as String?;
    final expiresAtRaw = s['expires_at'] as String?;
    final expiresAt = expiresAtRaw == null
        ? null
        : DateTime.tryParse(expiresAtRaw)?.toLocal();

    // Decide variant.
    final _BadgeData? data = _decide(
      isActive: isActive,
      hasEver: hasEver,
      status: status,
      expiresAt: expiresAt,
    );
    if (data == null) return const SizedBox.shrink();

    final tile = Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: data.bg,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(children: [
        Icon(data.icon, size: 18, color: data.fg),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            data.text,
            style: TextStyle(color: data.fg, fontSize: 13, fontWeight: FontWeight.w500),
          ),
        ),
        if (data.tappable)
          Icon(Icons.chevron_right, size: 18, color: data.fg),
      ]),
    );

    if (!data.tappable) return tile;
    return InkWell(
      onTap: () => context.push('/paywall'),
      borderRadius: BorderRadius.circular(8),
      child: tile,
    );
  }

  _BadgeData? _decide({
    required bool isActive,
    required bool hasEver,
    required String? status,
    required DateTime? expiresAt,
  }) {
    final dateStr = expiresAt == null
        ? ''
        : ' до ${_fmt(expiresAt)}';
    if (isActive && status == 'trial') {
      return _BadgeData(
        text: 'Триал$dateStr',
        bg: const Color(0xFFE3F2FD),
        fg: const Color(0xFF0D47A1),
        icon: Icons.timer_outlined,
        tappable: false,
      );
    }
    if (isActive) {
      return _BadgeData(
        text: 'Premium$dateStr',
        bg: const Color(0xFFE8F5E9),
        fg: const Color(0xFF1B5E20),
        icon: Icons.workspace_premium_outlined,
        tappable: false,
      );
    }
    if (hasEver) {
      return _BadgeData(
        text: 'Подписка истекла — продлить',
        bg: const Color(0xFFFFF3E0),
        fg: const Color(0xFFE65100),
        icon: Icons.lock_clock_outlined,
        tappable: true,
      );
    }
    return null;
  }

  String _fmt(DateTime d) =>
      '${d.day.toString().padLeft(2, '0')}.${d.month.toString().padLeft(2, '0')}.${d.year}';
}

class _BadgeData {
  final String text;
  final Color bg;
  final Color fg;
  final IconData icon;
  final bool tappable;
  _BadgeData({
    required this.text,
    required this.bg,
    required this.fg,
    required this.icon,
    required this.tappable,
  });
}
