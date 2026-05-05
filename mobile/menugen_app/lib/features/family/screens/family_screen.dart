import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../bloc/family_bloc.dart';
import '../../../core/widgets/macro_pill.dart';
import '../../../core/widgets/target_field.dart';
// MG_204m_V_family = 1
// MG_205UI_V_family = 1

class FamilyScreen extends StatelessWidget {
  const FamilyScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Семья')),
      body: BlocConsumer<FamilyBloc, FamilyState>(
        listener: (context, state) {
          if (state is FamilyError) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text(state.message)),
            );
          }
        },
        builder: (context, state) {
          if (state is FamilyLoading) {
            return const Center(child: CircularProgressIndicator());
          }

          final Map<String, dynamic>? family;
          final bool isActionInProgress;

          if (state is FamilyLoaded) {
            family = state.family;
            isActionInProgress = false;
          } else if (state is FamilyActionInProgress) {
            family = state.family;
            isActionInProgress = true;
          } else if (state is FamilyError && state.family != null) {
            family = state.family;
            isActionInProgress = false;
          } else {
            return const Center(child: Text('Нет данных'));
          }

          final members = (family!['members'] as List<dynamic>?) ?? [];

          return Stack(
            children: [
              ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  Text(
                    family['name'] as String? ?? '',
                    style: const TextStyle(
                        fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      Text(
                        'Участники (${members.length})',
                        style:
                            const TextStyle(fontWeight: FontWeight.w600),
                      ),
                      const Spacer(),
                      TextButton.icon(
                        onPressed: isActionInProgress
                            ? null
                            : () => _showAddMemberSheet(context),
                        icon: const Icon(Icons.person_add_outlined,
                            size: 18),
                        label: const Text('Добавить'),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  ...members.map((m) {
                    final member = m as Map<String, dynamic>;
                    final isHead = member['role'] == 'head';
                    return Card(
                      margin: const EdgeInsets.only(bottom: 8),
                      child: ListTile(
                        leading: CircleAvatar(
                          backgroundColor:
                              Theme.of(context).colorScheme.primaryContainer,
                          child: Text(
                            ((member['name'] as String?) ?? 'U')
                                .substring(0, 1)
                                .toUpperCase(),
                          ),
                        ),
                        title: Text(member['name'] as String? ?? ''),
                        subtitle: Text(
                          isHead ? 'Глава семьи' : 'Участник',
                          style: TextStyle(
                            color: isHead
                                ? Theme.of(context).colorScheme.primary
                                : null,
                          ),
                        ),
                        trailing: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            IconButton(
                              icon: const Icon(Icons.edit_outlined,
                                  size: 20),
                              tooltip: 'Редактировать',
                              onPressed: isActionInProgress
                                  ? null
                                  : () => _showEditMemberSheet(
                                      context, member),
                            ),
                            if (!isHead)
                              IconButton(
                                icon: const Icon(
                                    Icons.person_remove_outlined,
                                    size: 20,
                                    color: Colors.red),
                                tooltip: 'Удалить',
                                onPressed: isActionInProgress
                                    ? null
                                    : () => _confirmRemove(
                                        context, member),
                              ),
                          ],
                        ),
                      ),
                    );
                  }),
                ],
              ),
              if (isActionInProgress)
                const Positioned.fill(
                  child: ColoredBox(
                    color: Color(0x44000000),
                    child: Center(child: CircularProgressIndicator()),
                  ),
                ),
            ],
          );
        },
      ),
    );
  }

  void _showAddMemberSheet(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (_) => BlocProvider.value(
        value: context.read<FamilyBloc>(),
        child: const _AddMemberSheet(),
      ),
    );
  }

  void _showEditMemberSheet(
      BuildContext context, Map<String, dynamic> member) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (_) => BlocProvider.value(
        value: context.read<FamilyBloc>(),
        child: _EditMemberSheet(member: member),
      ),
    );
  }

  void _confirmRemove(BuildContext context, Map<String, dynamic> member) {
    final bloc = context.read<FamilyBloc>();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Удалить участника?'),
        content:
            Text('${member['name']} будет удалён из семьи.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('Отмена'),
          ),
          TextButton(
            onPressed: () {
              Navigator.of(ctx).pop();
              bloc.add(FamilyRemoveMemberRequested(
                  member['id'] as int));
            },
            style:
                TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('Удалить'),
          ),
        ],
      ),
    );
  }
}

// ── Add Member Sheet ──────────────────────────────────────────────────────────

class _AddMemberSheet extends StatefulWidget {
  const _AddMemberSheet();

  @override
  State<_AddMemberSheet> createState() => _AddMemberSheetState();
}

class _AddMemberSheetState extends State<_AddMemberSheet> {
  final _emailCtrl = TextEditingController();
  final _phoneCtrl = TextEditingController();
  bool _byEmail = true;

  @override
  void dispose() {
    _emailCtrl.dispose();
    _phoneCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.of(context).viewInsets.bottom;
    return Padding(
      padding: EdgeInsets.fromLTRB(16, 16, 16, 16 + bottom),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text('Добавить участника',
              style:
                  TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 16),
          SegmentedButton<bool>(
            segments: const [
              ButtonSegment(value: true, label: Text('По email')),
              ButtonSegment(value: false, label: Text('По телефону')),
            ],
            selected: {_byEmail},
            onSelectionChanged: (v) =>
                setState(() => _byEmail = v.first),
          ),
          const SizedBox(height: 12),
          if (_byEmail)
            TextField(
              controller: _emailCtrl,
              keyboardType: TextInputType.emailAddress,
              decoration:
                  const InputDecoration(labelText: 'Email участника'),
            )
          else
            TextField(
              controller: _phoneCtrl,
              keyboardType: TextInputType.phone,
              decoration: const InputDecoration(
                  labelText: 'Телефон участника'),
            ),
          const SizedBox(height: 16),
          ElevatedButton(
            onPressed: () {
              final email =
                  _byEmail ? _emailCtrl.text.trim() : null;
              final phone =
                  !_byEmail ? _phoneCtrl.text.trim() : null;
              if ((email ?? '').isEmpty && (phone ?? '').isEmpty) {
                return;
              }
              context.read<FamilyBloc>().add(
                    FamilyInviteMemberRequested(
                        email: email, phone: phone),
                  );
              Navigator.of(context).pop();
            },
            child: const Text('Добавить'),
          ),
        ],
      ),
    );
  }
}

// ── Edit Member Sheet ─────────────────────────────────────────────────────────

class _EditMemberSheet extends StatefulWidget {
  final Map<String, dynamic> member;
  const _EditMemberSheet({required this.member});

  @override
  State<_EditMemberSheet> createState() => _EditMemberSheetState();
}

class _EditMemberSheetState extends State<_EditMemberSheet> {
  late final TextEditingController _nameCtrl;
  late final TextEditingController _allergiesCtrl;
  late final TextEditingController _dislikedCtrl;
  late final TextEditingController _birthYearCtrl;
  late final TextEditingController _heightCtrl;
  late final TextEditingController _weightCtrl;
  late final TextEditingController _calorieCtrl;

  String? _gender;
  String? _activityLevel;
  String? _goal;
  String _mealPlanType = '3';

  static const _genders = [
    ('male', 'Мужской'),
    ('female', 'Женский'),
    ('other', 'Другой'),
  ];

  static const _activities = [
    ('sedentary', 'Малоподвижный'),
    ('light', 'Лёгкая активность'),
    ('moderate', 'Умеренная активность'),
    ('active', 'Высокая активность'),
    ('very_active', 'Очень высокая'),
  ];

  static const _goals = [
    ('lose_weight', 'Похудение'),
    ('maintain', 'Поддержание веса'),
    ('gain_weight', 'Набор массы'),
    ('healthy', 'Здоровое питание'),
  ];

  @override
  void initState() {
    super.initState();
    final m = widget.member;
    final profile = m['profile'] as Map<String, dynamic>? ?? {};

    _nameCtrl =
        TextEditingController(text: m['name'] as String? ?? '');
    _allergiesCtrl = TextEditingController(
      text: ((m['allergies'] as List<dynamic>?) ?? []).join(', '),
    );
    _dislikedCtrl = TextEditingController(
      text:
          ((m['disliked_products'] as List<dynamic>?) ?? []).join(', '),
    );
    _birthYearCtrl = TextEditingController(
      text: profile['birth_year']?.toString() ?? '',
    );
    _heightCtrl = TextEditingController(
      text: profile['height_cm']?.toString() ?? '',
    );
    _weightCtrl = TextEditingController(
      text: profile['weight_kg']?.toString() ?? '',
    );
    _calorieCtrl = TextEditingController(
      text: profile['calorie_target']?.toString() ?? '',
    );
    _gender = profile['gender'] as String?;
    _activityLevel = profile['activity_level'] as String?;
    _goal = profile['goal'] as String?;
    _mealPlanType = (profile['meal_plan_type'] as String?) ?? '3';
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _allergiesCtrl.dispose();
    _dislikedCtrl.dispose();
    _birthYearCtrl.dispose();
    _heightCtrl.dispose();
    _weightCtrl.dispose();
    _calorieCtrl.dispose();
    super.dispose();
  }

  List<String> _parseList(String text) => text
      .split(',')
      .map((s) => s.trim())
      .where((s) => s.isNotEmpty)
      .toList();

  void _save() {
    final profile = <String, dynamic>{};
    if (_birthYearCtrl.text.isNotEmpty) {
      profile['birth_year'] = int.tryParse(_birthYearCtrl.text);
    }
    if (_heightCtrl.text.isNotEmpty) {
      profile['height_cm'] = int.tryParse(_heightCtrl.text);
    }
    if (_weightCtrl.text.isNotEmpty) {
      profile['weight_kg'] = double.tryParse(_weightCtrl.text);
    }
    if (_calorieCtrl.text.isNotEmpty) {
      profile['calorie_target'] = int.tryParse(_calorieCtrl.text);
    }
    if (_gender != null) profile['gender'] = _gender;
    if (_activityLevel != null) {
      profile['activity_level'] = _activityLevel;
    }
    if (_goal != null) profile['goal'] = _goal;
      profile['meal_plan_type'] = _mealPlanType;
    final data = <String, dynamic>{
      'name': _nameCtrl.text.trim(),
      'allergies': _parseList(_allergiesCtrl.text),
      'disliked_products': _parseList(_dislikedCtrl.text),
      if (profile.isNotEmpty) 'profile': profile,
    };

    context.read<FamilyBloc>().add(
          FamilyUpdateMemberRequested(
            memberId: widget.member['id'] as int,
            data: data,
          ),
        );
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.of(context).viewInsets.bottom;
    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.85,
      maxChildSize: 0.95,
      builder: (_, scroll) => Padding(
        padding: EdgeInsets.fromLTRB(16, 16, 16, 16 + bottom),
        child: Column(
          children: [
            Row(
              children: [
                const Text('Редактировать участника',
                    style: TextStyle(
                        fontSize: 18, fontWeight: FontWeight.bold)),
                const Spacer(),
                IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () => Navigator.of(context).pop(),
                ),
              ],
            ),
            const Divider(),
            Expanded(
              child: ListView(
                controller: scroll,
                children: [
                  _section('Основное'),
                  _field(_nameCtrl, 'Имя'),
                  const SizedBox(height: 12),
                  _field(_allergiesCtrl, 'Аллергии (через запятую)'),
                  const SizedBox(height: 12),
                  _field(_dislikedCtrl,
                      'Нелюбимые продукты (через запятую)'),
                  const SizedBox(height: 20),
                  _section('Физиология'),
                  _field(_birthYearCtrl, 'Год рождения',
                      type: TextInputType.number),
                  const SizedBox(height: 12),
                  _dropdown(
                    'Пол',
                    _gender,
                    _genders,
                    (v) => setState(() => _gender = v),
                  ),
                  const SizedBox(height: 12),
                  _field(_heightCtrl, 'Рост (см)',
                      type: TextInputType.number),
                  const SizedBox(height: 12),
                  _field(_weightCtrl, 'Вес (кг)',
                      type: const TextInputType.numberWithOptions(
                          decimal: true)),
                  const SizedBox(height: 20),
                  _section('Цели и активность'),
                  _dropdown(
                    'Уровень активности',
                    _activityLevel,
                    _activities,
                    (v) => setState(() => _activityLevel = v),
                  ),
                  const SizedBox(height: 12),
                  _dropdown(
                    'Цель',
                    _goal,
                    _goals,
                    (v) => setState(() => _goal = v),
                  ),
                  const SizedBox(height: 12),
                  _field(_calorieCtrl, 'Целевые калории',
                      type: TextInputType.number),
                  const SizedBox(height: 16),
                  // MG_204m_V_family targets pills
                  Builder(builder: (_) {
                    final profile = (widget.member['profile'] as Map<String, dynamic>?) ?? {};
                    final targets = extractTargets(profile);
                    if (targets == null) return const SizedBox.shrink();
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Padding(
                          padding: EdgeInsets.only(bottom: 6),
                          child: Text(
                            'Целевые КБЖУ (рассчитано автоматически)',
                            style: TextStyle(
                              fontSize: 12,
                              color: Colors.grey,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ),
                        TargetFieldsRow(
                          targets: targets,
                          meta: extractTargetsMeta(profile),
                          loader: FamilyMemberTargetLoader(
                            apiClient: context.read<FamilyBloc>().apiClient,
                            memberId: widget.member['id'] as int,
                            onChanged: () => context
                                .read<FamilyBloc>()
                                .add(const FamilyLoadRequested()),
                          ),
                        ),
                        const SizedBox(height: 16),
                      ],
                    );
                  }),
                  // MG_204m_V_family meal_plan toggle
                  const Padding(
                    padding: EdgeInsets.only(bottom: 6),
                    child: Text(
                      'План приёмов пищи',
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.grey,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                  SegmentedButton<String>(
                    segments: const [
                      ButtonSegment(value: '3', label: Text('3 приёма')),
                      ButtonSegment(value: '5', label: Text('5 приёмов')),
                    ],
                    selected: {_mealPlanType},
                    onSelectionChanged: (v) =>
                        setState(() => _mealPlanType = v.first),
                  ),
                  const SizedBox(height: 24),
                  ElevatedButton(
                    onPressed: _save,
                    child: const Text('Сохранить'),
                  ),
                  const SizedBox(height: 8),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _section(String title) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Text(title,
            style: const TextStyle(
                fontWeight: FontWeight.w600, fontSize: 14,
                color: Colors.grey)),
      );

  Widget _field(TextEditingController ctrl, String label,
          {TextInputType type = TextInputType.text}) =>
      TextField(
        controller: ctrl,
        keyboardType: type,
        decoration: InputDecoration(labelText: label),
      );

  Widget _dropdown(
    String label,
    String? value,
    List<(String, String)> items,
    ValueChanged<String?> onChanged,
  ) =>
      DropdownButtonFormField<String>(
        value: value,
        decoration: InputDecoration(labelText: label),
        items: items
            .map((e) => DropdownMenuItem(
                value: e.$1, child: Text(e.$2)))
            .toList(),
        onChanged: onChanged,
      );
}
