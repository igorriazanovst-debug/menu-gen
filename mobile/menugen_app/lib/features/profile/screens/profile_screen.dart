// MG_204m_V_profile = 1
// MG_205UI_V_profile = 1
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../features/auth/bloc/auth_bloc.dart';
import '../../../core/api/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/macro_pill.dart';
import '../../../core/widgets/target_field.dart';

class ProfileScreen extends StatefulWidget {
  final ApiClient apiClient;
  const ProfileScreen({super.key, required this.apiClient});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  Map<String, dynamic>? _me;
  bool _loading = true;
  bool _saving = false;
  String? _error;
  String _mealPlanType = '3';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final r = await widget.apiClient.get('/users/me/');
      final data = r is Map<String, dynamic>
          ? r
          : Map<String, dynamic>.from(r as Map);
      final profile = data['profile'] as Map<String, dynamic>?;
      setState(() {
        _me = data;
        _mealPlanType = (profile?['meal_plan_type'] as String?) ?? '3';
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  Future<void> _saveMealPlan(String value) async {
    final prev = _mealPlanType;
    setState(() {
      _mealPlanType = value;
      _saving = true;
      _error = null;
    });
    try {
      await widget.apiClient.patch(
        '/users/me/',
        data: {
          'profile': {'meal_plan_type': value}
        },
      );
      await _load();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Профиль обновлён')),
      );
    } catch (e) {
      setState(() {
        _mealPlanType = prev;
        _error = e.toString();
      });
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Профиль')),
      body: BlocBuilder<AuthBloc, AuthState>(
        builder: (context, state) {
          if (state is! AuthAuthenticated) return const SizedBox.shrink();
          if (_loading) {
            return const Center(child: CircularProgressIndicator());
          }
          final user = (_me ?? (state.user as Map<String, dynamic>));
          final profile = user['profile'] as Map<String, dynamic>?;
          final targets = extractTargets(profile);
          final profileFilled = profile != null
              && profile['birth_year'] != null
              && profile['height_cm'] != null
              && profile['weight_kg'] != null;

          return RefreshIndicator(
            onRefresh: _load,
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Center(
                  child: CircleAvatar(
                    radius: 44,
                    backgroundColor: AppColors.primary.withOpacity(0.15),
                    child: Text(
                      ((user['name'] as String?) ?? 'U')[0].toUpperCase(),
                      style: const TextStyle(
                          fontSize: 32, color: AppColors.primary),
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                Center(
                  child: Text(
                    user['name'] ?? '',
                    style: Theme.of(context)
                        .textTheme
                        .titleLarge
                        ?.copyWith(fontWeight: FontWeight.bold),
                  ),
                ),
                Center(
                  child: Text(
                    user['email'] ?? user['phone'] ?? '',
                    style: TextStyle(color: Colors.grey.shade600),
                  ),
                ),
                const SizedBox(height: 24),

                // ── Целевые КБЖУ ────────────────────────────────────
                Card(
                  margin: EdgeInsets.zero,
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Целевые КБЖУ',
                          style: TextStyle(
                              fontSize: 16, fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 4),
                        const Text(
                          'Рассчитываются автоматически по формуле Mifflin-St Jeor',
                          style: TextStyle(fontSize: 12, color: Colors.grey),
                        ),
                        const SizedBox(height: 12),
                        if (!profileFilled)
                          Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: const Color(0xFFFEF6E0),
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(color: const Color(0xFFF1D08A)),
                            ),
                            child: const Text(
                              'Заполните рост, вес и год рождения — после этого появятся целевые КБЖУ.',
                              style: TextStyle(
                                  fontSize: 13, color: Color(0xFF8B6A12)),
                            ),
                          )
                        else if (targets != null)
                          TargetFieldsRow(
                            targets: targets,
                            meta: extractTargetsMeta(profile),
                            loader: MeTargetLoader(
                              apiClient: widget.apiClient,
                              onChanged: _load,
                            ),
                          )
                        else
                          const Text(
                            'Не удалось рассчитать цели — проверьте параметры профиля.',
                            style: TextStyle(fontSize: 13, color: Colors.grey),
                          ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 12),

                // ── План приёмов пищи ───────────────────────────────
                Card(
                  margin: EdgeInsets.zero,
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'План приёмов пищи',
                          style: TextStyle(
                              fontSize: 16, fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 12),
                        SegmentedButton<String>(
                          segments: const [
                            ButtonSegment(
                                value: '3', label: Text('3 приёма')),
                            ButtonSegment(
                                value: '5', label: Text('5 приёмов')),
                          ],
                          selected: {_mealPlanType},
                          onSelectionChanged: _saving
                              ? null
                              : (v) => _saveMealPlan(v.first),
                        ),
                        if (_saving)
                          const Padding(
                            padding: EdgeInsets.only(top: 8),
                            child: LinearProgressIndicator(),
                          ),
                        if (_error != null)
                          Padding(
                            padding: const EdgeInsets.only(top: 8),
                            child: Text(
                              _error!,
                              style: const TextStyle(
                                  color: Colors.red, fontSize: 12),
                            ),
                          ),
                      ],
                    ),
                  ),
                ),

                const SizedBox(height: 24),
                const Divider(),
                ListTile(
                  leading: const Icon(Icons.people_outline,
                      color: AppColors.secondary),
                  title: const Text('Семья'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => context.push('/family'),
                ),
                ListTile(
                  leading: const Icon(Icons.notifications_outlined),
                  title: const Text('Уведомления'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () {},
                ),
                const Divider(),
                ListTile(
                  leading: const Icon(Icons.logout, color: Colors.red),
                  title: const Text('Выйти',
                      style: TextStyle(color: Colors.red)),
                  onTap: () =>
                      context.read<AuthBloc>().add(const AuthLogoutRequested()),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}
