// GENERATED CODE - DO NOT MODIFY BY HAND
part of 'fridge_item.dart';

FridgeItem _\$FridgeItemFromJson(Map<String, dynamic> json) => _FridgeItem(
      id: json['id'] as int,
      name: json['name'] as String,
      quantity: (json['quantity'] as num?)?.toDouble(),
      unit: json['unit'] as String?,
      expiryDate: json['expiry_date'] as String?,
      productName: json['product_name'] as String?,
      productCategory: json['product_category'] as String?,
    );

Map<String, dynamic> _\$FridgeItemToJson(_FridgeItem instance) => <String, dynamic>{
      'id': instance.id,
      'name': instance.name,
      'quantity': instance.quantity,
      'unit': instance.unit,
      'expiry_date': instance.expiryDate,
      'product_name': instance.productName,
      'product_category': instance.productCategory,
    };
