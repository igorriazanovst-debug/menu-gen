// MG_BODYSIZE: обхваты тела — ввод, последние значения и контур.
//
// Стоит рядом с весом и по той же причине, по которой вес когда-то уехал из
// профиля в дневник: профиль хранит текущее состояние, а вопрос «что
// происходит» требует прошлых точек. С обхватами это заметнее, чем с весом: вес
// на диете неделями стоит, а талия в это время уходит — и человек, глядя на
// одно число, решает, что старается зря.
//
// Карточка свёрнута по умолчанию: обхваты меряют раз в неделю-две, и держать
// пять полей раскрытыми каждый день незачем.
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/api/api_client.dart';
import 'body_outline.dart';

/// Поля сверху вниз по телу: ключ на сервере и подпись. Один список на весь
/// экран — иначе подписи и значения однажды разъедутся.
const _fields = <(String, String)>[
  ('neck_cm', 'Шея'),
  ('chest_cm', 'Грудь'),
  ('under_bust_cm', 'Под грудью'),
  ('waist_cm', 'Талия'),
  ('hips_cm', 'Бёдра'),
];

class MeasurementsCard extends StatefulWidget {
  final ApiClient api;
  final String date;
  final int? memberId;

  /// Пол из профиля — только для силуэта. Не указан — нейтральный контур.
  final String? gender;
  const MeasurementsCard({
    super.key,
    required this.api,
    required this.date,
    this.memberId,
    this.gender,
  });

  @override
  State<MeasurementsCard> createState() => _MeasurementsCardState();
}

class _MeasurementsCardState extends State<MeasurementsCard> {
  static const _prefKey = 'menugen.showChart.body';

  final _ctrls = {for (final f in _fields) f.$1: TextEditingController()};
  List<Map<String, dynamic>> _rows = const [];
  bool _expanded = false;
  bool _showChart = false;
  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _restoreChartFlag();
    _load();
  }

  @override
  void didUpdateWidget(covariant MeasurementsCard old) {
    super.didUpdateWidget(old);
    if (old.date != widget.date || old.memberId != widget.memberId) _load();
  }

  @override
  void dispose() {
    for (final c in _ctrls.values) {
      c.dispose();
    }
    super.dispose();
  }

  /// Показывать диаграмму или нет — выбор человека, и он помнится: одному
  /// нужна картина каждый день, другому не нужна вовсе.
  Future<void> _restoreChartFlag() async {
    try {
      final p = await SharedPreferences.getInstance();
      if (mounted) setState(() => _showChart = p.getBool(_prefKey) ?? false);
    } catch (_) {/* не критично: просто останется выключенной */}
  }

  Future<void> _saveChartFlag(bool value) async {
    setState(() => _showChart = value);
    try {
      final p = await SharedPreferences.getInstance();
      await p.setBool(_prefKey, value);
    } catch (_) {/* не критично */}
  }

  Future<void> _load() async {
    try {
      final params = <String, String>{'days': '365'};
      if (widget.memberId != null) params['member_id'] = '${widget.memberId}';
      final r = await widget.api.get('/diary/measurements/', params: params);
      if (!mounted) return;
      final rows = (r is List ? r : const [])
          .whereType<Map>()
          .map((e) => Map<String, dynamic>.from(e))
          .toList();
      setState(() {
        _rows = rows;
        final today = _forDate(widget.date);
        for (final f in _fields) {
          _ctrls[f.$1]!.text = '${today?[f.$1] ?? ''}';
        }
      });
    } catch (_) {
      // Пустая история — не ошибка: карточка просто без данных.
      if (mounted) setState(() => _rows = const []);
    }
  }

  Map<String, dynamic>? _forDate(String date) {
    for (final r in _rows) {
      if (r['date'] == date) return r;
    }
    return null;
  }

  Map<String, dynamic>? get _latest => _rows.isEmpty ? null : _rows.last;
  Map<String, dynamic>? get _previous => _rows.length < 2 ? null : _rows[_rows.length - 2];

  double? _num(Object? v) => v == null ? null : double.tryParse('$v');

  BodySizes _sizes(Map<String, dynamic>? row) => BodySizes(
        neck: _num(row?['neck_cm']),
        chest: _num(row?['chest_cm']),
        underBust: _num(row?['under_bust_cm']),
        waist: _num(row?['waist_cm']),
        hips: _num(row?['hips_cm']),
      );

  Future<void> _save() async {
    final data = <String, dynamic>{'date': widget.date};
    var any = false;
    for (final f in _fields) {
      final raw = _ctrls[f.$1]!.text.trim().replaceAll(',', '.');
      if (raw.isEmpty) {
        // Пустое поле уходит как null: так стирают ошибочный замер.
        data[f.$1] = null;
        continue;
      }
      final v = double.tryParse(raw);
      if (v == null || v <= 0 || v > 300) {
        setState(() => _error = '${f.$2}: нужно число от 0 до 300 см.');
        return;
      }
      data[f.$1] = raw;
      any = true;
    }
    if (!any) {
      setState(() => _error = 'Укажите хотя бы один обхват.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      // ApiClient.post не принимает query-параметры, поэтому участник уходит
      // прямо в путь — так же, как в карточке веса.
      final path = widget.memberId == null
          ? '/diary/measurements/'
          : '/diary/measurements/?member_id=${widget.memberId}';
      await widget.api.post(path, data: data);
      await _load();
      if (mounted) FocusScope.of(context).unfocus();
    } catch (_) {
      if (mounted) setState(() => _error = 'Не удалось сохранить замеры.');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  String get _summary {
    final row = _latest;
    if (row == null) return 'не записаны';
    final parts = <String>[];
    for (final f in _fields) {
      final v = row[f.$1];
      if (v != null) parts.add('${f.$2} $v');
    }
    return parts.isEmpty ? 'не записаны' : parts.join(' · ');
  }

  @override
  Widget build(BuildContext context) {
    final accent = Theme.of(context).colorScheme.primary;
    final addedBy = _latest?['added_by_name'] as String?;
    return Card(
      margin: const EdgeInsets.fromLTRB(12, 2, 12, 2),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          InkWell(
            onTap: () => setState(() => _expanded = !_expanded),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              child: Row(
                children: [
                  const Text('📏', style: TextStyle(fontSize: 16)),
                  const SizedBox(width: 8),
                  const Text('Обхваты', style: TextStyle(fontWeight: FontWeight.bold)),
                  // MG_HEADKEEPS: замер внёс не сам человек.
                  if (addedBy != null) ...[
                    const SizedBox(width: 4),
                    const Text('👑', style: TextStyle(fontSize: 13)),
                  ],
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      _summary,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontSize: 12,
                        color: _latest == null ? Colors.grey.shade600 : null,
                      ),
                    ),
                  ),
                  AnimatedRotation(
                    turns: _expanded ? 0.0 : -0.25,
                    duration: const Duration(milliseconds: 180),
                    child: const Icon(Icons.keyboard_arrow_down, size: 20),
                  ),
                ],
              ),
            ),
          ),
          if (_expanded)
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  for (final f in _fields)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 2),
                      child: Row(
                        children: [
                          SizedBox(
                            width: 110,
                            child: Text(f.$2, style: const TextStyle(fontSize: 13)),
                          ),
                          SizedBox(
                            width: 90,
                            child: TextField(
                              controller: _ctrls[f.$1],
                              keyboardType: const TextInputType.numberWithOptions(decimal: true),
                              decoration: const InputDecoration(hintText: 'см', isDense: true),
                            ),
                          ),
                        ],
                      ),
                    ),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      TextButton(
                        onPressed: _busy ? null : _save,
                        child: const Text('Записать'),
                      ),
                      const SizedBox(width: 4),
                      Expanded(
                        child: Text(
                          'за ${widget.date}',
                          style: TextStyle(fontSize: 11, color: Colors.grey.shade500),
                        ),
                      ),
                      // Всегда, а не только при готовых замерах: иначе о
                      // диаграмме не узнать, пока не запишешь первый обхват, —
                      // а записывать незачем, пока не знаешь, что она есть.
                      TextButton(
                        onPressed: () => _saveChartFlag(!_showChart),
                        child: Text(_showChart ? 'скрыть диаграмму' : 'показать диаграмму'),
                      ),
                    ],
                  ),
                  if (_error != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Text(_error!, style: const TextStyle(color: Colors.red, fontSize: 12)),
                    ),
                  if (addedBy != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Text(
                        'Последний замер внёс(ла) $addedBy',
                        style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
                      ),
                    ),
                  if (_showChart)
                    BodyOutline(
                      sizes: _sizes(_latest),
                      previous: _previous == null ? null : _sizes(_previous),
                      shape: bodyShapeFromGender(widget.gender),
                      accent: accent,
                    ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}
