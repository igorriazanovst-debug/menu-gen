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
        // 401 refresh-once path (preserves prior behaviour).
        if (error.response?.statusCode == 401) {
          final refresh = await tokenStorage.getRefreshToken();
          if (refresh != null) {
            try {
              final resp = await Dio().post(
                '${AppConfig.apiBaseUrl}/auth/refresh/',
                data: {'refresh': refresh},
              );
              final newAccess = resp.data['access'] as String;
              await tokenStorage.saveTokens(
                  access: newAccess, refresh: refresh);
              error.requestOptions.headers['Authorization'] =
                  'Bearer $newAccess';
              return handler.resolve(await _dio.fetch(error.requestOptions));
            } catch (_) {
              await tokenStorage.clearTokens();
            }
          }
        }
        handler.next(error);
      },
    ));
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
      message = e.message ?? 'Сетевая ошибка';
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
