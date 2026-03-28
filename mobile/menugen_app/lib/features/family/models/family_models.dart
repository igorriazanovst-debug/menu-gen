class Family {
  final int id;
  final String name;
  final String ownerName;
  final List<FamilyMemberModel> members;
  const Family({required this.id, required this.name, required this.ownerName, required this.members});
  factory Family.fromJson(Map<String, dynamic> json) => Family(
    id: json['id'] as int,
    name: json['name'] as String? ?? '',
    ownerName: json['owner_name'] as String? ?? '',
    members: (json['members'] as List<dynamic>?)
        ?.map((m) => FamilyMemberModel.fromJson(m as Map<String, dynamic>)).toList() ?? [],
  );
}

class FamilyMemberModel {
  final int id;
  final int userId;
  final String name;
  final String? email;
  final String? avatarUrl;
  final String role;
  const FamilyMemberModel({required this.id, required this.userId, required this.name,
      this.email, this.avatarUrl, required this.role});
  factory FamilyMemberModel.fromJson(Map<String, dynamic> json) => FamilyMemberModel(
    id: json['id'] as int, userId: json['user_id'] as int, name: json['name'] as String,
    email: json['email'] as String?, avatarUrl: json['avatar_url'] as String?,
    role: json['role'] as String,
  );
}

class ShoppingListModel {
  final int id;
  final List<ShoppingItemModel> items;
  const ShoppingListModel({required this.id, required this.items});
  factory ShoppingListModel.fromJson(Map<String, dynamic> json) => ShoppingListModel(
    id: json['id'] as int,
    items: (json['items'] as List<dynamic>?)
        ?.map((i) => ShoppingItemModel.fromJson(i as Map<String, dynamic>)).toList() ?? [],
  );
}

class ShoppingItemModel {
  final int id;
  final String name;
  final double? quantity;
  final String? unit;
  final String? category;
  bool isPurchased;
  ShoppingItemModel({required this.id, required this.name, this.quantity, this.unit,
      this.category, required this.isPurchased});
  factory ShoppingItemModel.fromJson(Map<String, dynamic> json) => ShoppingItemModel(
    id: json['id'] as int, name: json['name'] as String,
    quantity: (json['quantity'] as num?)?.toDouble(), unit: json['unit'] as String?,
    category: json['category'] as String?,
    isPurchased: json['is_purchased'] as bool? ?? false,
  );
}
