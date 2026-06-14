import 'dart:async';

import 'package:dio/dio.dart';

import '../config/app_config.dart';
import 'api_client.dart';
import 'api_exception.dart';
import 'token_storage.dart';

/// Dio-backed [ApiClient] that:
///  * attaches Bearer tokens from [TokenStorage]
///  * silently refreshes on 401 once
///  * converts every non-2xx into [ApiException]
///  * broadcasts [ApiException]s on [errorStream] so cross-cutting cubits
///    (e.g. PremiumGateCubit) can react without each bloc re-implementing
///    error parsing.
class DioApiClient implements ApiClient {
  late final Dio _dio;
  final TokenStorage tokenStorage;
  // MG_TOKENFIX: single-flight guard so concurrent 401s share one refresh.
  Future<bool>? _refreshing;

  final StreamController<ApiException> _errors =
      StreamController<ApiException>.broadcast();

  /// Stream of ApiExceptions emitted by this client. Used by
  /// [PremiumGateCubit] to detect 403s globally.
  Stream<ApiException> get errorStream => _errors.stream;

  DioApiClient({required this.tokenStorage}) {
    _dio = Dio(BaseOptions(
      baseUrl: AppConfig.apiBaseUrl,
      connectTimeout: const Duration(seconds: 15),
      receiveTimeout: const Duration(seconds: 15),
      headers: {'Content-Type': 'application/json'},
    ));

    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        final token = await tokenStorage.getAccessToken();
        if (token != null) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        handler.next(options);
      },
      onError: (error, handler) async {
        // MG_TOKENFIX: refresh once per request, sharing a single in-flight
        // refresh across concurrent 401s (otherwise parallel refreshes rotate
        // the token against each other and blacklist it -> spurious logout).
        final alreadyRetried = error.requestOptions.extra['__retried'] == true;
        if (error.response?.statusCode == 401 && !alreadyRetried) {
          _refreshing ??= _refreshTokens();
          final ok = await _refreshing!;
          _refreshing = null;
          if (ok) {
            final newAccess = await tokenStorage.getAccessToken();
            final opts = error.requestOptions;
            opts.extra['__retried'] = true;
            opts.headers['Authorization'] = 'Bearer $newAccess';
            try {
              return handler.resolve(await _dio.fetch(opts));
            } on DioException catch (e) {
              return handler.next(e);
            }
          } else {
            await tokenStorage.clearTokens();
          }
        }
        handler.next(error);
      },
    ));
  }

  /// MG_TOKENFIX: refresh the access token and PERSIST the rotated refresh
  /// token. The backend uses ROTATE_REFRESH_TOKENS + BLACKLIST_AFTER_ROTATION,
  /// so reusing the old refresh on the next cycle fails; keeping the new one
  /// lets the session live until the refresh lifetime (days), not minutes.
  Future<bool> _refreshTokens() async {
    final refresh = await tokenStorage.getRefreshToken();
    if (refresh == null) return false;
    try {
      final resp = await Dio().post(
        '${AppConfig.apiBaseUrl}/auth/refresh/',
        data: {'refresh': refresh},
      );
      final data = resp.data;
      final newAccess = data is Map ? data['access'] as String? : null;
      if (newAccess == null) return false;
      final newRefresh =
          (data is Map ? data['refresh'] as String? : null) ?? refresh;
      await tokenStorage.saveTokens(access: newAccess, refresh: newRefresh);
      return true;
    } catch (_) {
      return false;
    }
  }

  void dispose() {
    _errors.close();
    _dio.close(force: true);
  }

  /// Convert a DioException into a typed [ApiException] and broadcast it.
  Never _throw(DioException e) {
    final resp = e.response;
    String message;
    String? errorCode;
    dynamic body = resp?.data;

    if (body is Map) {
      // DRF default error shape: {"detail": "..."}.
      // Also tolerate {"error_code": "..."} for forward-compat.
      message = (body['detail'] ??
              body['message'] ??
              body['error'] ??
              'Ошибка сервера')
          .toString();
      final ec = body['error_code'];
      if (ec is String) errorCode = ec;
    } else if (body is String && body.isNotEmpty) {
      message = body;
    } else {
      // MG_T10: friendly text for network/timeout errors (no HTTP response)
      // instead of Dio's raw English "The connection errored..." string.
      message = 'Нет подключения к интернету';
    }

    final ex = ApiException(
      message: message,
      statusCode: resp?.statusCode,
      errorCode: errorCode,
      body: body,
    );
    if (!_errors.isClosed) _errors.add(ex);
    throw ex;
  }

  Future<T> _run<T>(Future<Response<dynamic>> Function() call) async {
    try {
      final r = await call();
      return r.data as T;
    } on DioException catch (e) {
      _throw(e);
    }
  }

  @override
  Future<dynamic> get(String path, {Map<String, dynamic>? params}) =>
      _run(() => _dio.get(path, queryParameters: params));

  @override
  Future<dynamic> post(String path, {Map<String, dynamic>? data}) =>
      _run(() => _dio.post(path, data: data));

  @override
  Future<dynamic> put(String path, {Map<String, dynamic>? data}) =>
      _run(() => _dio.put(path, data: data));

  @override
  Future<dynamic> patch(String path, {Map<String, dynamic>? data}) =>
      _run(() => _dio.patch(path, data: data));

  @override
  Future<dynamic> delete(String path) =>
      _run(() => _dio.delete(path));
}
