class FridgeItem {
  final int id;
  final String name;
  final double? quantity;
  final String? unit;
  final String? expiryDate;
  final String? productName;
  final String? productCategory;

  const FridgeItem({
    required this.id,
    required this.name,
    this.quantity, this.unit, this.expiryDate,
    this.productName, this.productCategory,
  });

  factory FridgeItem.fromJson(Map<String, dynamic> json) => FridgeItem(
        id: json['id'] as int? ?? 0,
        name: json['name'] as String? ?? '',
        quantity: (json['quantity'] as num?)?.toDouble(),
        unit: json['unit'] as String?,
        expiryDate: json['expiry_date'] as String?,
        productName: json['product_name'] as String?,
        productCategory: json['product_category'] as String?,
      );

  Map<String, dynamic> toJson() => {
        'id': id, 'name': name,
        if (quantity != null) 'quantity': quantity,
        if (unit != null) 'unit': unit,
        if (expiryDate != null) 'expiry_date': expiryDate,
        if (productName != null) 'product_name': productName,
        if (productCategory != null) 'product_category': productCategory,
      };
}