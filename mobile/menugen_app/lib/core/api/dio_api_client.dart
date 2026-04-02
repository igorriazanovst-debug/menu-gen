import 'package:dio/dio.dart';
import 'api_client.dart';
import 'token_storage.dart';
import '../config/app_config.dart';

class DioApiClient implements ApiClient {
  late final Dio _dio;
  final TokenStorage tokenStorage;

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
        if (token != null) options.headers['Authorization'] = 'Bearer $token';
        handler.next(options);
      },
      onError: (error, handler) async {
        if (error.response?.statusCode == 401) {
          final refresh = await tokenStorage.getRefreshToken();
          if (refresh != null) {
            try {
              final resp = await Dio().post(
                '${AppConfig.apiBaseUrl}/auth/refresh/',
                data: {'refresh': refresh},
              );
              final newAccess = resp.data['access'] as String;
              await tokenStorage.saveTokens(access: newAccess, refresh: refresh);
              error.requestOptions.headers['Authorization'] = 'Bearer $newAccess';
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

  @override
  Future<dynamic> get(String path, {Map<String, dynamic>? params}) async =>
      (await _dio.get(path, queryParameters: params)).data;

  @override
  Future<dynamic> post(String path, {Map<String, dynamic>? data}) async =>
      (await _dio.post(path, data: data)).data;

  @override
  Future<dynamic> put(String path, {Map<String, dynamic>? data}) async =>
      (await _dio.put(path, data: data)).data;

  @override
  Future<dynamic> patch(String path, {Map<String, dynamic>? data}) async =>
      (await _dio.patch(path, data: data)).data;

  @override
  Future<dynamic> delete(String path) async =>
      (await _dio.delete(path)).data;
}