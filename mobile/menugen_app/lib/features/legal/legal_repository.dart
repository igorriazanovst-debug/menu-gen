// MG_LEGAL: загрузка публичных юридических данных.
import '../../core/api/api_client.dart';
import 'models/legal_info.dart';

class LegalRepository {
  final ApiClient apiClient;

  const LegalRepository(this.apiClient);

  /// GET /legal/ — эндпоинт публичный (AllowAny), токен не нужен.
  Future<LegalInfo> load() async {
    final resp = await apiClient.get('/legal/');
    if (resp is! Map) {
      throw const FormatException('Неожиданный ответ /legal/');
    }
    return LegalInfo.fromJson(Map<String, dynamic>.from(resp));
  }
}

/// Какой из трёх документов показывать.
enum LegalDoc { offer, privacy, requisites }

extension LegalDocX on LegalDoc {
  String get slug => switch (this) {
        LegalDoc.offer => 'offer',
        LegalDoc.privacy => 'privacy',
        LegalDoc.requisites => 'requisites',
      };

  String get title => switch (this) {
        LegalDoc.offer => 'Публичная оферта',
        LegalDoc.privacy => 'Политика обработки персональных данных',
        LegalDoc.requisites => 'Реквизиты',
      };

  /// Короткая подпись для плитки в списке.
  String get subtitle => switch (this) {
        LegalDoc.offer => 'Условия использования сервиса',
        LegalDoc.privacy => 'Как мы обрабатываем ваши данные',
        LegalDoc.requisites => 'Данные продавца и банковские реквизиты',
      };
}

LegalDoc legalDocFromSlug(String? slug) => switch (slug) {
      'offer' => LegalDoc.offer,
      'requisites' => LegalDoc.requisites,
      _ => LegalDoc.privacy,
    };
