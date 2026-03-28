abstract class ApiClient {
  Future<dynamic> get(String path, {Map<String, dynamic>? params});
  Future<dynamic> post(String path, {Map<String, dynamic>? data});
  Future<dynamic> put(String path, {Map<String, dynamic>? data});
  Future<dynamic> patch(String path, {Map<String, dynamic>? data});
  Future<dynamic> delete(String path);
}