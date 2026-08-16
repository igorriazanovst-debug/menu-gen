// MG_PAY: экран подписки — тарифы, выбор периода и оплата через ЮKassa.
//
// Оплата открывается во внешнем браузере: платёжная страница внутри WebView —
// плохая идея и для банков, и для доверия. По возвращении приложение само
// спрашивает бэкенд об исходе платежа (MG_PAYRELIABLE) — ждать уведомления
// ЮKassa нельзя, оно может опоздать, а человек уже смотрит на экран.
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/api/api_client.dart';
import '../pay_offers.dart';
import '../pending_payment.dart';

class SubscriptionScreen extends StatefulWidget {
  final ApiClient apiClient;
  const SubscriptionScreen({super.key, required this.apiClient});

  @override
  State<SubscriptionScreen> createState() => _SubscriptionScreenState();
}

class _SubscriptionScreenState extends State<SubscriptionScreen> with WidgetsBindingObserver {
  bool _loading = true;
  String? _error;
  List<Map<String, dynamic>> _plans = const [];
  List<Map<String, dynamic>> _offers = const [];
  final Map<String, String> _chosen = {}; // plan_code -> offer_code
  Map<String, dynamic>? _current;
  String? _subscribing; // plan_code в процессе
  (String, bool)? _payResult; // (текст, успех)

  // Возврат ведёт на страницу сайта: ЮKassa принимает только http(s). Оттуда
  // человек возвращается в приложение — либо кнопкой, либо просто переключившись.
  static const _returnUrl = 'https://menugen.ru/pay/return';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _load();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // Вернулись из браузера — самое время узнать, чем всё кончилось.
    if (state == AppLifecycleState.resumed) _checkPendingPayment();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      _plans = await _list('/subscriptions/plans/');
      _offers = await _list('/subscriptions/offers/');
      for (final o in _offers) {
        final plan = o['plan_code']?.toString();
        final code = o['code']?.toString();
        if (plan != null && code != null) _chosen.putIfAbsent(plan, () => code);
      }
      try {
        final cur = await widget.apiClient.get('/subscriptions/current/');
        _current = cur is Map ? Map<String, dynamic>.from(cur) : null;
      } catch (_) {
        _current = null; // нет активной подписки — норм
      }
    } catch (e) {
      _error = 'Не удалось загрузить тарифы.';
    } finally {
      if (mounted) setState(() => _loading = false);
    }
    await _checkPendingPayment();
  }

  Future<List<Map<String, dynamic>>> _list(String path) async {
    final resp = await widget.apiClient.get(path);
    final raw = resp is Map ? resp['results'] : resp;
    return ((raw as List?) ?? const [])
        .whereType<Map>()
        .map((e) => Map<String, dynamic>.from(e))
        .toList();
  }

  Future<void> _checkPendingPayment() async {
    final paymentId = await takePendingPayment();
    if (paymentId == null) return;
    try {
      final resp = await widget.apiClient.get('/payments/$paymentId/status/');
      final data = resp is Map ? Map<String, dynamic>.from(resp) : <String, dynamic>{};
      final result = paymentResultText(data);
      if (result == null) {
        // Ещё в работе: идентификатор возвращаем, проверим при следующем заходе.
        await rememberPayment(paymentId);
        if (mounted) {
          setState(() => _payResult = ('Платёж обрабатывается — обновите через минуту.', false));
        }
        return;
      }
      if (!mounted) return;
      setState(() => _payResult = result);
      if (result.$2) await _reloadCurrent();
    } catch (_) {
      await rememberPayment(paymentId); // не потеряем: спросим в следующий раз
    }
  }

  Future<void> _reloadCurrent() async {
    try {
      final cur = await widget.apiClient.get('/subscriptions/current/');
      if (mounted) {
        setState(() => _current = cur is Map ? Map<String, dynamic>.from(cur) : null);
      }
    } catch (_) {/* ignore */}
  }

  Future<void> _subscribe(Map<String, dynamic> plan, Map<String, dynamic> offer) async {
    final planCode = plan['code']?.toString() ?? '';
    setState(() {
      _subscribing = planCode;
      _payResult = null;
    });
    try {
      final resp = await widget.apiClient.post(
        '/subscriptions/subscribe/',
        data: {'offer_code': offer['code'], 'return_url': _returnUrl},
      );
      final data = resp is Map ? Map<String, dynamic>.from(resp) : <String, dynamic>{};
      final url = data['payment_url'] as String?;
      final paymentId = data['payment_id'] as String?;
      if (url == null || url.isEmpty) {
        throw Exception('Нет ссылки на оплату');
      }
      // Запоминаем ДО ухода: приложение могут выгрузить, пока человек платит.
      if (paymentId != null && paymentId.isNotEmpty) await rememberPayment(paymentId);

      final uri = Uri.parse(url);
      if (!await launchUrl(uri, mode: LaunchMode.externalApplication)) {
        throw Exception('Не удалось открыть страницу оплаты');
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Ошибка оплаты: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _subscribing = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Подписка'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _loading ? null : _load),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text(_error!))
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      if (_payResult != null) _resultBanner(_payResult!),
                      if (_current != null) _currentCard(_current!),
                      ..._plans.map(_planCard),
                      const SizedBox(height: 12),
                      const Text(
                        'Оплата откроется в браузере. Вернитесь в приложение — '
                        'подписка обновится сама.',
                        style: TextStyle(fontSize: 12, color: Colors.grey),
                      ),
                    ],
                  ),
                ),
    );
  }

  Widget _resultBanner((String, bool) result) {
    final ok = result.$2;
    return Card(
      color: ok ? Colors.green.shade50 : Colors.orange.shade50,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(children: [
          Icon(ok ? Icons.check_circle_outline : Icons.info_outline,
              color: ok ? Colors.green.shade700 : Colors.orange.shade800),
          const SizedBox(width: 8),
          Expanded(child: Text(result.$1)),
        ]),
      ),
    );
  }

  Widget _currentCard(Map<String, dynamic> sub) {
    final plan = sub['plan'] is Map ? Map<String, dynamic>.from(sub['plan'] as Map) : null;
    final expires = sub['expires_at']?.toString();
    return Card(
      color: Colors.green.shade50,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Активный тариф', style: TextStyle(fontSize: 12, color: Colors.grey)),
            const SizedBox(height: 2),
            Text(plan?['name']?.toString() ?? '—',
                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            if (expires != null && expires.length >= 10)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text('Действует до ${expires.substring(0, 10)}',
                    style: const TextStyle(fontSize: 12, color: Colors.grey)),
              ),
          ],
        ),
      ),
    );
  }

  Widget _planCard(Map<String, dynamic> plan) {
    final planCode = plan['code']?.toString();
    final price = plan['price']?.toString() ?? '0';
    final isFree = price == '0.00' || price == '0';
    final isCurrent = _current != null &&
        (_current!['plan'] is Map) &&
        (Map<String, dynamic>.from(_current!['plan'] as Map)['code'] == planCode);
    final busy = _subscribing == planCode;

    final planOffers = offersForPlan(_offers, planCode);
    final offer = selectedOffer(planOffers, _chosen[planCode]);
    final note = offer != null ? offerPriceNote(offer) : null;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(plan['name']?.toString() ?? '',
                style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
            const SizedBox(height: 4),
            Text(
              isFree ? 'Бесплатно' : (offer != null ? offerPrice(offer) : '$price ₽'),
              style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700),
            ),
            if (note != null)
              Padding(
                padding: const EdgeInsets.only(top: 2),
                child: Text(note, style: const TextStyle(fontSize: 12, color: Colors.grey)),
              ),
            if (planOffers.length > 1) ...[
              const SizedBox(height: 12),
              _periodPicker(planCode!, planOffers, offer),
            ],
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: isFree
                  ? const OutlinedButton(onPressed: null, child: Text('Бесплатный тариф'))
                  : offer == null
                      ? const OutlinedButton(onPressed: null, child: Text('Оплата недоступна'))
                      : ElevatedButton(
                          // Текущий тариф тоже можно оплатить: это продление, и
                          // срок прибавляется к остатку, а не начинается заново.
                          onPressed: busy ? null : () => _subscribe(plan, offer),
                          child: busy
                              ? const SizedBox(
                                  height: 20,
                                  width: 20,
                                  child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                              : Text(isCurrent ? 'Продлить' : 'Подключить'),
                        ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _periodPicker(
    String planCode,
    List<Map<String, dynamic>> planOffers,
    Map<String, dynamic>? selected,
  ) {
    return Wrap(
      spacing: 8,
      children: planOffers.map((o) {
        final discount = offerDiscount(o);
        final label = discount > 0 ? '${o['title']} · −$discount%' : '${o['title']}';
        return ChoiceChip(
          label: Text(label),
          selected: o['code'] == selected?['code'],
          onSelected: (_) => setState(() => _chosen[planCode] = o['code'].toString()),
        );
      }).toList(),
    );
  }
}
