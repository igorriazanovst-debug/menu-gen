// MG_PAY: экран подписки — список тарифов + оплата через YooKassa.
// Оплата открывается во внешнем браузере; смена тарифа происходит автоматически
// по webhook'у платёжной системы (backend). После возврата — «Обновить».
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/api/api_client.dart';

class SubscriptionScreen extends StatefulWidget {
  final ApiClient apiClient;
  const SubscriptionScreen({super.key, required this.apiClient});

  @override
  State<SubscriptionScreen> createState() => _SubscriptionScreenState();
}

class _SubscriptionScreenState extends State<SubscriptionScreen> {
  bool _loading = true;
  String? _error;
  List<Map<String, dynamic>> _plans = const [];
  Map<String, dynamic>? _current;
  String? _subscribing; // plan_code в процессе

  static const _returnUrl = 'https://menugen.ru/subscriptions?status=success';

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
      final plansResp = await widget.apiClient.get('/subscriptions/plans/');
      final raw = plansResp is Map ? plansResp['results'] : plansResp;
      _plans = ((raw as List?) ?? const [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
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
  }

  Future<void> _subscribe(Map<String, dynamic> plan) async {
    final code = plan['code'] as String;
    setState(() => _subscribing = code);
    try {
      final resp = await widget.apiClient.post('/subscriptions/subscribe/',
          data: {'plan_code': code, 'return_url': _returnUrl});
      final data = resp is Map ? Map<String, dynamic>.from(resp) : <String, dynamic>{};
      final url = data['payment_url'] as String?;
      if (url == null || url.isEmpty) {
        throw Exception('Нет ссылки на оплату');
      }
      final uri = Uri.parse(url);
      if (await canLaunchUrl(uri)) {
        await launchUrl(uri, mode: LaunchMode.externalApplication);
      } else {
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
                      if (_current != null) _currentCard(_current!),
                      ..._plans.map(_planCard),
                      const SizedBox(height: 12),
                      const Text(
                        'Оплата откроется в браузере. Тариф сменится автоматически '
                        'после подтверждения оплаты — вернитесь и нажмите «Обновить».',
                        style: TextStyle(fontSize: 12, color: Colors.grey),
                      ),
                    ],
                  ),
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
    final price = plan['price']?.toString() ?? '0';
    final isFree = price == '0.00' || price == '0';
    final period = plan['period'] == 'year' ? 'год' : 'мес';
    final isCurrent = _current != null &&
        (_current!['plan'] is Map) &&
        (Map<String, dynamic>.from(_current!['plan'] as Map)['code'] == plan['code']);
    final busy = _subscribing == plan['code'];

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(plan['name']?.toString() ?? '',
                style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
            const SizedBox(height: 4),
            Text(isFree ? 'Бесплатно' : '${price.split('.').first} ₽ / $period',
                style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: isCurrent
                  ? OutlinedButton(onPressed: null, child: const Text('Текущий тариф'))
                  : isFree
                      ? OutlinedButton(onPressed: null, child: const Text('Бесплатный тариф'))
                      : ElevatedButton(
                          onPressed: busy ? null : () => _subscribe(plan),
                          child: busy
                              ? const SizedBox(
                                  height: 20,
                                  width: 20,
                                  child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                              : const Text('Подключить'),
                        ),
            ),
          ],
        ),
      ),
    );
  }
}
