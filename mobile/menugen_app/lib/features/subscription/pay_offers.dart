// MG_PAYPERIOD: периоды покупки на стороне приложения.
//
// Выгоду длинного периода считает бэкенд — здесь только разбор ответа, чтобы
// цифры в приложении и в вебе не разъезжались.

/// Периоды конкретного тарифа, в порядке от короткого к длинному.
List<Map<String, dynamic>> offersForPlan(
  List<Map<String, dynamic>> offers,
  String? planCode,
) {
  if (planCode == null) return const [];
  return offers.where((o) => o['plan_code'] == planCode).toList();
}

/// Выбранный период: сохранённый выбор, иначе первый доступный.
Map<String, dynamic>? selectedOffer(
  List<Map<String, dynamic>> planOffers,
  String? chosenCode,
) {
  if (planOffers.isEmpty) return null;
  for (final o in planOffers) {
    if (o['code'] == chosenCode) return o;
  }
  return planOffers.first;
}

/// Цена периода целым числом рублей: «2990 ₽».
String offerPrice(Map<String, dynamic> offer) {
  final raw = offer['price']?.toString() ?? '0';
  return '${raw.split('.').first} ₽';
}

/// Подпись под ценой для длинного периода — чтобы было с чем сравнить.
String? offerPriceNote(Map<String, dynamic> offer) {
  final months = offer['months'];
  if (months is! int || months <= 1) return null;
  final perMonth = double.tryParse(offer['price_per_month']?.toString() ?? '');
  if (perMonth == null) return null;
  return '${perMonth.round()} ₽ в месяц';
}

/// Скидка длинного периода в процентах, 0 — если её нет.
int offerDiscount(Map<String, dynamic> offer) {
  final d = offer['discount_percent'];
  return d is int ? d : 0;
}
