// MG_LEGAL: публичные юридические данные (GET /legal/ — один объект на всё).
//
// Один запрос отдаёт сразу реквизиты, оферту и политику обработки ПД, поэтому
// отдельных эндпоинтов на документ нет: экраны переиспользуют одну загрузку.

class LegalInfo {
  final String companyName;
  final String inn;
  final String ogrnip;
  final String legalAddress;
  final String email;
  final String phone;
  final String bankName;
  final String bankBik;
  final String bankAccount;
  final String corrAccount;
  final String requisitesExtra;
  final String offerText;
  final String privacyText;
  final String? logoUrl;
  final String updatedAt;

  const LegalInfo({
    this.companyName = '',
    this.inn = '',
    this.ogrnip = '',
    this.legalAddress = '',
    this.email = '',
    this.phone = '',
    this.bankName = '',
    this.bankBik = '',
    this.bankAccount = '',
    this.corrAccount = '',
    this.requisitesExtra = '',
    this.offerText = '',
    this.privacyText = '',
    this.logoUrl,
    this.updatedAt = '',
  });

  static String _str(Map<String, dynamic> json, String key) {
    final value = json[key];
    return value == null ? '' : value.toString();
  }

  factory LegalInfo.fromJson(Map<String, dynamic> json) => LegalInfo(
        companyName: _str(json, 'company_name'),
        inn: _str(json, 'inn'),
        ogrnip: _str(json, 'ogrnip'),
        legalAddress: _str(json, 'legal_address'),
        email: _str(json, 'email'),
        phone: _str(json, 'phone'),
        bankName: _str(json, 'bank_name'),
        bankBik: _str(json, 'bank_bik'),
        bankAccount: _str(json, 'bank_account'),
        corrAccount: _str(json, 'corr_account'),
        requisitesExtra: _str(json, 'requisites_extra'),
        offerText: _str(json, 'offer_text'),
        privacyText: _str(json, 'privacy_text'),
        logoUrl: (json['logo_url'] as String?)?.isEmpty ?? true ? null : json['logo_url'] as String,
        updatedAt: _str(json, 'updated_at'),
      );

  /// Реквизиты не заполнены в админке — экран покажет заглушку вместо пустых строк.
  bool get hasRequisites => companyName.isNotEmpty || inn.isNotEmpty;
}
