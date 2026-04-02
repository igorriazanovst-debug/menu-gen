import '../api/api_client.dart';
import '../db/app_database.dart';

class SyncService {
  final ApiClient apiClient;
  final AppDatabase db;
  SyncService({required this.apiClient, required this.db});
  void start() {}
  Future<void> sync() async {}
}