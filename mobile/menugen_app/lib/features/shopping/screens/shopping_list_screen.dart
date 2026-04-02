import 'package:flutter/material.dart';
import '../../../core/api/api_client.dart';

class ShoppingListScreen extends StatefulWidget {
  final ApiClient apiClient;
  final int menuId;
  const ShoppingListScreen({super.key, required this.apiClient, required this.menuId});
  @override
  State<ShoppingListScreen> createState() => _ShoppingListScreenState();
}

class _ShoppingListScreenState extends State<ShoppingListScreen> {
  List<dynamic> _items = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final data = await widget.apiClient.get('/menu/${widget.menuId}/shopping-list/');
      setState(() {
        _items = (data is Map ? data['items'] : data) as List<dynamic>? ?? [];
        _loading = false;
      });
    } catch (e) {
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Список покупок')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text(_error!))
              : ListView.builder(
                  itemCount: _items.length,
                  itemBuilder: (_, i) {
                    final item = _items[i] as Map<String, dynamic>;
                    return CheckboxListTile(
                      value: false,
                      onChanged: (_) {},
                      title: Text(item['name'] as String? ?? ''),
                      subtitle: Text('${item['quantity'] ?? ''} ${item['unit'] ?? ''}'),
                    );
                  },
                ),
    );
  }
}