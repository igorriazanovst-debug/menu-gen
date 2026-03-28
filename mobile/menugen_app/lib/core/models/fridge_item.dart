import 'package:freezed_annotation/freezed_annotation.dart';
part 'fridge_item.freezed.dart';
part 'fridge_item.g.dart';

@freezed
class FridgeItem with _$FridgeItem {
  const factory FridgeItem({
    required int id,
    required String name,
    double? quantity,
    String? unit,
    String? expiryDate,
    String? productName,
    String? productCategory,
  }) = _FridgeItem;

  factory FridgeItem.fromJson(Map<String, dynamic> json) => _$FridgeItemFromJson(json);
}
