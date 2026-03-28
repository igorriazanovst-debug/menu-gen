// coverage:ignore-file
// GENERATED CODE - DO NOT MODIFY BY HAND
part of 'fridge_item.dart';

mixin _\$FridgeItem {
  int get id => throw _privateConstructorUsedError;
  String get name => throw _privateConstructorUsedError;
  double? get quantity => throw _privateConstructorUsedError;
  String? get unit => throw _privateConstructorUsedError;
  String? get expiryDate => throw _privateConstructorUsedError;
  String? get productName => throw _privateConstructorUsedError;
  String? get productCategory => throw _privateConstructorUsedError;
  Map<String, dynamic> toJson() => throw _privateConstructorUsedError;
}

class _FridgeItem implements FridgeItem {
  const _FridgeItem({required this.id, required this.name, this.quantity,
      this.unit, this.expiryDate, this.productName, this.productCategory});
  @override final int id;
  @override final String name;
  @override final double? quantity;
  @override final String? unit;
  @override final String? expiryDate;
  @override final String? productName;
  @override final String? productCategory;
  @override
  Map<String, dynamic> toJson() => _\$FridgeItemToJson(this);
}
