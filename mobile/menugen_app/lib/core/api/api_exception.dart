/// Typed exception thrown by [DioApiClient] on non-2xx responses.
///
/// Wraps DRF error shape `{"detail": "..."}` and exposes [isPremiumLocked]
/// for callers that need to react to MG-606 premium gating (HTTP 403 from
/// IsFamilyPremiumOrReadOnly).
class ApiException implements Exception {
  /// HTTP status code; `null` for network errors / timeouts.
  final int? statusCode;

  /// Optional machine-readable error code if backend ever provides one
  /// (currently DRF returns only `detail`). Kept for future compatibility.
  final String? errorCode;

  /// Human-readable message (from `detail` if present, else fallback).
  final String message;

  /// Raw response body (if any), useful for debugging / extra fields.
  final dynamic body;

  const ApiException({
    required this.message,
    this.statusCode,
    this.errorCode,
    this.body,
  });

  /// True iff the response is a Premium gate denial.
  ///
  /// MG-606: `IsFamilyPremiumOrReadOnly` returns 403 for both read (no
  /// premium history) and write (no active premium) denials. Mobile uses
  /// status code alone — backend does not provide an error_code field.
  bool get isPremiumLocked => statusCode == 403;

  /// Freemium: 403 из-за исчерпания бесплатной квоты генераций меню
  /// (бэкенд шлёт `{"code": "menu_quota_exceeded"}`), а не premium-гейт.
  bool get isQuotaExceeded => statusCode == 403 && errorCode == 'menu_quota_exceeded';

  bool get isUnauthorized => statusCode == 401;
  bool get isNotFound => statusCode == 404;
  bool get isThrottled => statusCode == 429; // MG_SKIN: DRF rate limit
  bool get isServerError => statusCode != null && statusCode! >= 500;
  bool get isNetwork => statusCode == null;

  @override
  String toString() =>
      'ApiException(status=$statusCode, code=$errorCode, message=$message)';
}
