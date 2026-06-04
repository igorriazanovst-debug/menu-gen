// MG_SHOPMOB001
import 'package:equatable/equatable.dart';

/// Mirror of backend `ShoppingList.Source`.
enum ShoppingSource {
  empty('empty', 'Пустой'),
  menu('menu', 'Из меню'),
  fridge('fridge', 'Меню − холодильник'),
  aiText('ai_text', 'ИИ из текста'),
  csv('csv', 'CSV');

  final String value;
  final String label;
  const ShoppingSource(this.value, this.label);

  static ShoppingSource fromValue(String? raw) {
    for (final s in ShoppingSource.values) {
      if (s.value == raw) return s;
    }
    return ShoppingSource.empty;
  }
}

class ShoppingItem extends Equatable {
  final int id;
  final String name;
  final double? quantity;
  final String unit;
  final String category;
  final String? categorySlug; // MG_SHOPMOB001
  final String? categoryName; // MG_SHOPMOB001
  final String? pricePerUnit; // MG_SHOPMOB001 (DRF Decimal => string|null)
  final String? lineTotal; // MG_SHOPMOB001
  final bool isPurchased;
  final String? purchasedByName;

  const ShoppingItem({
    required this.id,
    required this.name,
    required this.quantity,
    required this.unit,
    required this.category,
    this.categorySlug,
    this.categoryName,
    this.pricePerUnit,
    this.lineTotal,
    required this.isPurchased,
    this.purchasedByName,
  });

  factory ShoppingItem.fromJson(Map<String, dynamic> j) {
    final q = j['quantity'];
    return ShoppingItem(
      id: j['id'] as int,
      name: j['name'] as String? ?? '',
      quantity: q == null ? null : double.tryParse(q.toString()),
      unit: j['unit'] as String? ?? '',
      category: j['category'] as String? ?? '',
      categorySlug: j['category_slug'] as String?,
      categoryName: j['category_name'] as String?,
      pricePerUnit: j['price_per_unit']?.toString(),
      lineTotal: j['line_total']?.toString(),
      isPurchased: j['is_purchased'] as bool? ?? false,
      purchasedByName: j['purchased_by_name'] as String?,
    );
  }

  @override
  List<Object?> get props =>
      [id, name, quantity, unit, category, categorySlug, pricePerUnit, isPurchased];
}

class ShoppingCapabilities extends Equatable {
  final bool read;
  final bool toggle;
  final bool export;
  final bool manage;

  const ShoppingCapabilities({
    required this.read,
    required this.toggle,
    required this.export,
    required this.manage,
  });

  factory ShoppingCapabilities.fromJson(Map<String, dynamic>? j) {
    j ??= const {};
    return ShoppingCapabilities(
      read: j['read'] as bool? ?? false,
      toggle: j['toggle'] as bool? ?? false,
      export: j['export'] as bool? ?? false,
      manage: j['manage'] as bool? ?? false,
    );
  }

  @override
  List<Object?> get props => [read, toggle, export, manage];
}

class ShoppingListBrief extends Equatable {
  final int id;
  final String name;
  final ShoppingSource source;
  final bool isArchived;
  final int itemsTotal;
  final int itemsPurchased;
  final DateTime? createdAt; // MG_SHOPBUG_MOB

  const ShoppingListBrief({
    required this.id,
    required this.name,
    required this.source,
    required this.isArchived,
    required this.itemsTotal,
    required this.itemsPurchased,
    this.createdAt,
  });

  factory ShoppingListBrief.fromJson(Map<String, dynamic> j) => ShoppingListBrief(
        id: j['id'] as int,
        name: j['name'] as String? ?? '',
        source: ShoppingSource.fromValue(j['source'] as String?),
        isArchived: j['is_archived'] as bool? ?? false,
        itemsTotal: j['items_total'] as int? ?? 0,
        itemsPurchased: j['items_purchased'] as int? ?? 0,
        createdAt: DateTime.tryParse(j['created_at']?.toString() ?? ''),
      );

  @override
  List<Object?> get props =>
      [id, name, source, isArchived, itemsTotal, itemsPurchased, createdAt];
}

class ShoppingListDetail extends Equatable {
  final int id;
  final String name;
  final ShoppingSource source;
  final bool isArchived;
  final List<ShoppingItem> items;
  final ShoppingCapabilities capabilities;
  final String currency; // MG_SHOPMOB001
  final String? totalPrice; // MG_SHOPMOB001
  final DateTime? createdAt; // MG_SHOPBUG_MOB

  const ShoppingListDetail({
    required this.id,
    required this.name,
    required this.source,
    required this.isArchived,
    required this.items,
    required this.capabilities,
    this.currency = 'RUB',
    this.totalPrice,
    this.createdAt,
  });

  factory ShoppingListDetail.fromJson(Map<String, dynamic> j) {
    final raw = (j['items'] as List? ?? const []);
    return ShoppingListDetail(
      id: j['id'] as int,
      name: j['name'] as String? ?? '',
      source: ShoppingSource.fromValue(j['source'] as String?),
      isArchived: j['is_archived'] as bool? ?? false,
      items: raw
          .whereType<Map>()
          .map((e) => ShoppingItem.fromJson(Map<String, dynamic>.from(e)))
          .toList(),
      capabilities: ShoppingCapabilities.fromJson(
        j['capabilities'] == null ? null : Map<String, dynamic>.from(j['capabilities'] as Map),
      ),
      currency: j['currency'] as String? ?? 'RUB',
      totalPrice: j['total_price']?.toString(),
      createdAt: DateTime.tryParse(j['created_at']?.toString() ?? ''),
    );
  }

  @override
  List<Object?> get props => [
        id,
        name,
        source,
        isArchived,
        items,
        capabilities,
        currency,
        totalPrice,
        createdAt,
      ];
}

class ShoppingAccess extends Equatable {
  final int id;
  final String userEmail;
  final String? userName;
  final bool canToggle;
  final bool canExport;

  const ShoppingAccess({
    required this.id,
    required this.userEmail,
    required this.userName,
    required this.canToggle,
    required this.canExport,
  });

  factory ShoppingAccess.fromJson(Map<String, dynamic> j) => ShoppingAccess(
        id: j['id'] as int,
        userEmail: j['user_email'] as String? ?? '',
        userName: j['user_name'] as String?,
        canToggle: j['can_toggle'] as bool? ?? false,
        canExport: j['can_export'] as bool? ?? false,
      );

  @override
  List<Object?> get props => [id, userEmail, userName, canToggle, canExport];
}

class ShoppingHistoryEntry extends Equatable {
  final int id;
  final String name;
  final double? quantity;
  final String unit;
  final String category; // MG_SHOPMOB001
  final String? pricePerUnit; // MG_SHOPMOB001
  final String purchasedAt;

  const ShoppingHistoryEntry({
    required this.id,
    required this.name,
    required this.quantity,
    required this.unit,
    this.category = '',
    this.pricePerUnit,
    required this.purchasedAt,
  });

  factory ShoppingHistoryEntry.fromJson(Map<String, dynamic> j) {
    final q = j['quantity'];
    return ShoppingHistoryEntry(
      id: j['id'] as int,
      name: j['name'] as String? ?? '',
      quantity: q == null ? null : double.tryParse(q.toString()),
      unit: j['unit'] as String? ?? '',
      category: j['category'] as String? ?? '',
      pricePerUnit: j['price_per_unit']?.toString(),
      purchasedAt: j['purchased_at'] as String? ?? '',
    );
  }

  @override
  List<Object?> get props =>
      [id, name, quantity, unit, category, pricePerUnit, purchasedAt];
}

class ShoppingExportData {
  final String title;
  final String currency; // MG_SHOPMOB001
  final String? totalPrice; // MG_SHOPMOB001
  final DateTime? createdAt; // MG_SHOPBUG_MOB_FIX1
  final List<MapEntry<String, List<ShoppingItem>>> categories;

  ShoppingExportData({
    required this.title,
    required this.categories,
    this.currency = 'RUB',
    this.totalPrice,
    this.createdAt,
  });

  factory ShoppingExportData.fromJson(Map<String, dynamic> j) {
    final cats = (j['categories'] as List? ?? const []);
    final out = <MapEntry<String, List<ShoppingItem>>>[];
    for (final c in cats) {
      final cm = Map<String, dynamic>.from(c as Map);
      final items = (cm['items'] as List? ?? const [])
          .whereType<Map>()
          .map((e) {
            final em = Map<String, dynamic>.from(e);
            final q = em['quantity'];
            return ShoppingItem(
              id: 0,
              name: em['name'] as String? ?? '',
              quantity: q == null ? null : double.tryParse(q.toString()),
              unit: em['unit'] as String? ?? '',
              category: cm['category'] as String? ?? '',
              pricePerUnit: em['price_per_unit']?.toString(),
              lineTotal: em['line_total']?.toString(),
              isPurchased: em['is_purchased'] as bool? ?? false,
            );
          })
          .toList();
      out.add(MapEntry(cm['category'] as String? ?? '', items));
    }
    return ShoppingExportData(
      title: j['title'] as String? ?? 'Список',
      currency: j['currency'] as String? ?? 'RUB',
      totalPrice: j['total_price']?.toString(),
      createdAt: DateTime.tryParse(j['created_at']?.toString() ?? ''),
      categories: out,
    );
  }
}

// MG_SHOPMOB001: a single rubricator search result row.
class RubricResult {
  final int productId;
  final String name;
  final String unit;
  final String categorySlug;
  final String categoryName;
  final String subcategory;
  const RubricResult({
    required this.productId,
    required this.name,
    required this.unit,
    required this.categorySlug,
    required this.categoryName,
    required this.subcategory,
  });
  factory RubricResult.fromJson(Map<String, dynamic> j) => RubricResult(
        productId: j['product_id'] as int? ?? 0,
        name: j['name'] as String? ?? '',
        unit: j['unit'] as String? ?? '',
        categorySlug: j['category_slug'] as String? ?? '',
        categoryName: j['category_name'] as String? ?? '',
        subcategory: j['subcategory'] as String? ?? '',
      );
}

// MG_SHOPBUG_MOB: format a Decimal-string as money (2 dp). Defensive.
String fmtMoney(String? raw) {
  if (raw == null) return '';
  final n = double.tryParse(raw);
  if (n == null) return raw;
  return n.toStringAsFixed(2);
}

// MG_SHOPBUG_MOB: format a date as dd.MM.yyyy (locale-independent).
String fmtListDate(DateTime? d) {
  if (d == null) return '';
  String p(int v) => v.toString().padLeft(2, '0');
  return '${p(d.day)}.${p(d.month)}.${d.year}';
}

// MG_SHOPMOB001: render a currency code as a short symbol.
String currencySymbol(String code) {
  switch (code.toUpperCase()) {
    case 'RUB':
      return '₽';
    case 'USD':
      return r'$';
    case 'EUR':
      return '€';
    case 'GBP':
      return '£';
    case 'KZT':
      return '₸';
    case 'UAH':
      return '₴';
    case 'BYN':
      return 'Br';
    default:
      return code;
  }
}
