class ApiException implements Exception {
  final int? statusCode;
  final String message;

  const ApiException({this.statusCode, required this.message});

  factory ApiException.fromDio(dynamic error) {
    if (error?.response != null) {
      final data = error.response!.data;
      String msg = 'Ошибка сервера';
      if (data is Map) {
        msg = data['detail'] ?? data.values.first?.toString() ?? msg;
      }
      return ApiException(statusCode: error.response!.statusCode, message: msg);
    }
    return const ApiException(message: 'Нет соединения с сервером');
  }

  @override
  String toString() => 'ApiException(): ';
}
