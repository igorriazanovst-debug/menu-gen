import 'package:dio/dio.dart';
import 'package:pretty_dio_logger/pretty_dio_logger.dart';
import 'token_storage.dart';

class ApiClient {
  late final Dio _dio;
  final TokenStorage tokenStorage;

  ApiClient({required this.tokenStorage}) {
    _dio = Dio(BaseOptions(
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 15),
      headers: {'Content-Type': 'application/json'},
    ));

    _dio.interceptors.addAll([
      _AuthInterceptor(tokenStorage: tokenStorage, dio: _dio),
      PrettyDioLogger(requestBody: true, responseBody: true, compact: true),
    ]);
  }

  // Базовый URL задаётся через environment (--dart-define)
  static const _baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000/api/v1',
  );

  Dio get dio => _dio;

  Future<Response<T>> get<T>(String path, {Map<String, dynamic>? params}) =>
      _dio.get('', queryParameters: params);

  Future<Response<T>> post<T>(String path, {dynamic data}) =>
      _dio.post('', data: data);

  Future<Response<T>> patch<T>(String path, {dynamic data}) =>
      _dio.patch('', data: data);

  Future<Response<T>> delete<T>(String path) =>
      _dio.delete('');
}

class _AuthInterceptor extends Interceptor {
  final TokenStorage tokenStorage;
  final Dio dio;

  _AuthInterceptor({required this.tokenStorage, required this.dio});

  @override
  Future<void> onRequest(
      RequestOptions options, RequestInterceptorHandler handler) async {
    final token = await tokenStorage.getAccessToken();
    if (token != null) {
      options.headers['Authorization'] = 'Bearer ';
    }
    handler.next(options);
  }

  @override
  Future<void> onError(
      DioException err, ErrorInterceptorHandler handler) async {
    if (err.response?.statusCode == 401) {
      final refreshed = await _tryRefresh();
      if (refreshed) {
        final token = await tokenStorage.getAccessToken();
        err.requestOptions.headers['Authorization'] = 'Bearer ';
        final response = await dio.fetch(err.requestOptions);
        return handler.resolve(response);
      }
    }
    handler.next(err);
  }

  Future<bool> _tryRefresh() async {
    final refresh = await tokenStorage.getRefreshToken();
    if (refresh == null) return false;
    try {
      final resp = await dio.post(
        '${ApiClient._baseUrl}/auth/refresh/',
        data: {'refresh': refresh},
        options: Options(headers: {}),
      );
      await tokenStorage.saveTokens(
        access:  resp.data['access'],
        refresh: resp.data['refresh'] ?? refresh,
      );
      return true;
    } catch (_) {
      await tokenStorage.clearTokens();
      return false;
    }
  }
}
