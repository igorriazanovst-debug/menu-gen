// MG_204m_V_profile = 1
// MG_205UI_V_profile = 1
// MG_207_V_profile_btn = 1
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../features/auth/bloc/auth_bloc.dart';
import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/theme/skin_selector.dart'; // MG_SKIN
import '../../../core/widgets/macro_pill.dart';
import '../../../core/widgets/target_field.dart';
import '../../../core/premium/premium_badge.dart';
import '../../../core/premium/premium_gate_cubit.dart'; // MG_PROMO
import '../widgets/allergen_editor.dart'; // MG_ALLERGEN

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
  List<String> _allergies = const []; // MG_ALLERGEN
  bool _allergenSaving = false;
  // MG_PROMO: активация промокода.
  final _promoCtrl = TextEditingController();
  bool _promoBusy = false;
  bool _promoOk = false;
  String? _promoMsg;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _promoCtrl.dispose();
    super.dispose();
  }

  // MG_PROMO: активировать промокод → выдаётся/продлевается премиум семье.
  Future<void> _redeemPromo() async {
    final code = _promoCtrl.text.trim().toUpperCase();
    if (code.isEmpty) return;
    setState(() {
      _promoBusy = true;
      _promoMsg = null;
    });
    try {
      final r = await widget.apiClient
          .post('/subscriptions/promo/redeem/', data: {'code': code});
      final data = r is Map ? Map<String, dynamic>.from(r) : <String, dynamic>{};
      _promoCtrl.clear();
      if (mounted) context.read<PremiumGateCubit>().reset();
      await _load();
      if (!mounted) return;
      final until = data['expires_at'] != null
          ? DateTime.tryParse(data['expires_at'].toString())
          : null;
      setState(() {
        _promoOk = true;
        _promoMsg = until != null
            ? 'Промокод активирован. Премиум до ${until.day.toString().padLeft(2, '0')}.'
                '${until.month.toString().padLeft(2, '0')}.${until.year}.'
            : 'Промокод активирован. Премиум подключён.';
      });
    } catch (e) {
      setState(() {
        _promoOk = false;
        _promoMsg = e is ApiException ? e.message : 'Не удалось активировать промокод.';
      });
    } finally {
      if (mounted) setState(() => _promoBusy = false);
    }
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
        _allergies = ((data['allergies'] as List?) ?? const [])
            .map((e) => e.toString())
            .toList();
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

  // MG_ALLERGEN: сохранить список аллергенов (оптимистично, PATCH /users/me/).
  Future<void> _saveAllergies(List<String> next) async {
    final prev = _allergies;
    setState(() {
      _allergies = next;
      _allergenSaving = true;
      _error = null;
    });
    try {
      await widget.apiClient.patch('/users/me/', data: {'allergies': next});
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Аллергены сохранены')),
      );
    } catch (e) {
      setState(() {
        _allergies = prev;
        _error = e.toString();
      });
    } finally {
      if (mounted) setState(() => _allergenSaving = false);
    }
  }

  // MG_207_V_profile_btn: открыть калькулятор КБЖУ, по возврату — перезагрузить профиль.
  Future<void> _openCalculator(Map<String, dynamic>? profile) async {
    await context.push('/profile/kbju-calculator', extra: profile);
    if (mounted) _load();
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
                    backgroundColor: context.cs.primary.withOpacity(0.15),
                    child: Text(
                      ((user['name'] as String?) ?? 'U')[0].toUpperCase(),
                      style: TextStyle(
                          fontSize: 32, color: context.cs.primary),
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                // MG-profile-premium: subscription badge.
                PremiumBadge(
                  subscriptionStatus: user['subscription_status'] as Map<String, dynamic>?,
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

                // ── Промокод (MG_PROMO) ─────────────────────────────
                Card(
                  margin: EdgeInsets.zero,
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Промокод',
                          style: TextStyle(
                              fontSize: 16, fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 4),
                        const Text(
                          'Введите промокод, чтобы подключить премиум.',
                          style: TextStyle(fontSize: 12, color: Colors.grey),
                        ),
                        const SizedBox(height: 12),
                        Row(
                          children: [
                            Expanded(
                              child: TextField(
                                controller: _promoCtrl,
                                textCapitalization:
                                    TextCapitalization.characters,
                                decoration: const InputDecoration(
                                  hintText: 'ABCD-EFGH-JKLM',
                                  border: OutlineInputBorder(),
                                  isDense: true,
                                ),
                                onSubmitted:
                                    _promoBusy ? null : (_) => _redeemPromo(),
                              ),
                            ),
                            const SizedBox(width: 8),
                            FilledButton(
                              onPressed: _promoBusy ? null : _redeemPromo,
                              child: _promoBusy
                                  ? const SizedBox(
                                      width: 16,
                                      height: 16,
                                      child: CircularProgressIndicator(
                                          strokeWidth: 2),
                                    )
                                  : const Text('Активировать'),
                            ),
                          ],
                        ),
                        if (_promoMsg != null)
                          Padding(
                            padding: const EdgeInsets.only(top: 8),
                            child: Text(
                              _promoMsg!,
                              style: TextStyle(
                                fontSize: 12,
                                color: _promoOk
                                    ? Colors.green.shade700
                                    : Colors.red,
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 12),

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
                        // MG_207_V_profile_btn: вход в калькулятор КБЖУ.
                        const SizedBox(height: 12),
                        SizedBox(
                          width: double.infinity,
                          child: OutlinedButton.icon(
                            onPressed: () => _openCalculator(profile),
                            icon: const Icon(Icons.calculate_outlined, size: 18),
                            label: const Text('Открыть калькулятор КБЖУ'),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 12),

                // ── Оформление (скин) ───────────────────────────────
                const SkinSelectorCard(), // MG_SKIN
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

                const SizedBox(height: 12),

                // ── Аллергены ───────────────────────────────────────
                Card(
                  margin: EdgeInsets.zero,
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            const Expanded(
                              child: Text(
                                'Аллергены',
                                style: TextStyle(
                                    fontSize: 16, fontWeight: FontWeight.bold),
                              ),
                            ),
                            if (_allergenSaving)
                              const SizedBox(
                                width: 16,
                                height: 16,
                                child:
                                    CircularProgressIndicator(strokeWidth: 2),
                              ),
                          ],
                        ),
                        const SizedBox(height: 4),
                        const Text(
                          'Отметьте аллергены из обязательного перечня (ТР ТС 022/2011) — '
                          'блюда с ними исключаются из генерации меню. Можно добавить '
                          'и свой аллерген вне списка.',
                          style: TextStyle(fontSize: 12, color: Colors.grey),
                        ),
                        const SizedBox(height: 12),
                        AllergenEditor(
                          apiClient: widget.apiClient,
                          value: _allergies,
                          onChanged: _saveAllergies,
                        ),
                      ],
                    ),
                  ),
                ),

                const SizedBox(height: 24),
                const Divider(),
                ListTile(
                  leading: Icon(Icons.workspace_premium_outlined,
                      color: context.cs.secondary),
                  title: const Text('Подписка'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => context.push('/subscription'), // MG_PAY
                ),
                ListTile(
                  leading: Icon(Icons.people_outline,
                      color: context.cs.secondary),
                  title: const Text('Семья'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => context.push('/family'),
                ),
                ListTile(
                  leading: const Icon(Icons.notifications_outlined),
                  title: const Text('Уведомления'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => context.push('/notifications'), // MG_WEIGHREMIND
                ),
                // MG_LEGAL: оферта, политика обработки ПД, реквизиты.
                ListTile(
                  leading: const Icon(Icons.gavel_outlined),
                  title: const Text('Документы'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => context.push('/legal'),
                ),
                const Divider(),
                ListTile(
                  leading: const Icon(Icons.logout, color: Colors.red),
                  title: const Text('Выйти',
                      style: TextStyle(color: Colors.red)),
                  onTap: () =>
                      context.read<AuthBloc>().add(const AuthLogoutRequested()),
                ),
                // MG_ACCDEL: ниже выхода и без выделения цветом — путь должен
                // существовать (этого требует Google Play), но не соседствовать
                // с обычными настройками так, чтобы в него попадали промахом.
                ListTile(
                  leading: const Icon(Icons.delete_forever_outlined,
                      color: Colors.grey),
                  title: const Text('Удалить аккаунт',
                      style: TextStyle(color: Colors.grey)),
                  trailing: const Icon(Icons.chevron_right, color: Colors.grey),
                  onTap: () => context.push('/delete-account'),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}
