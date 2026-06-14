// MG_CACHE: lightweight offline cache for shopping lists + details.
//
// Stores the raw decoded API JSON (write-through) in SharedPreferences. A
// successful online GET overwrites (invalidates) the prior entry; reads are
// TTL-bounded so stale data is not served indefinitely. Mobile-only.
import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

class ShoppingCache {
  final SharedPreferences prefs;
  ShoppingCache(this.prefs);

  static const Duration _ttl = Duration(days: 7);
  static const String _vListsActive = 'mg_cache_lists_active_v1';
  static const String _vListsArchived = 'mg_cache_lists_archived_v1';
  static String _detailKey(int id) => 'mg_cache_detail_${id}_v1';

  String _listsKey(bool archived) =>
      archived ? _vListsArchived : _vListsActive;

  Future<void> _write(String key, Object data) async {
    final env = {'ts': DateTime.now().millisecondsSinceEpoch, 'data': data};
    await prefs.setString(key, jsonEncode(env));
  }

  dynamic _read(String key) {
    final s = prefs.getString(key);
    if (s == null) return null;
    try {
      final env = jsonDecode(s);
      if (env is! Map) return null;
      final ts = env['ts'];
      if (ts is! int) return null;
      final age = DateTime.now().millisecondsSinceEpoch - ts;
      if (age > _ttl.inMilliseconds) return null; // expired
      return env['data'];
    } catch (_) {
      return null;
    }
  }

  Future<void> saveLists(bool archived, List<dynamic> raw) =>
      _write(_listsKey(archived), raw);

  /// Cached raw list (List of Maps) or null on miss/expired.
  List<Map<String, dynamic>>? readLists(bool archived) {
    final d = _read(_listsKey(archived));
    if (d is! List) return null;
    return d
        .whereType<Map>()
        .map((e) => Map<String, dynamic>.from(e))
        .toList();
  }

  Future<void> saveDetail(int id, Map<String, dynamic> raw) =>
      _write(_detailKey(id), raw);

  /// Cached raw detail map or null on miss/expired.
  Map<String, dynamic>? readDetail(int id) {
    final d = _read(_detailKey(id));
    if (d is! Map) return null;
    return Map<String, dynamic>.from(d);
  }

  /// Reflect an offline toggle in the cached detail so re-opening the list
  /// offline shows the toggled state. No-op if the detail isn't cached.
  Future<void> patchDetailItemPurchased(
      int listId, int itemId, bool isPurchased) async {
    final d = readDetail(listId);
    if (d == null) return;
    final items = d['items'];
    if (items is List) {
      for (final it in items) {
        if (it is Map && it['id'] == itemId) {
          it['is_purchased'] = isPurchased;
        }
      }
    }
    await saveDetail(listId, d);
  }
}
