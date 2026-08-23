// MG_SELFUPDATE: проверка, загрузка и запуск установки обновления.
//
// Приложение не может установить обновление само — тихая установка доступна
// только системным приложениям. Мы скачиваем файл и передаём его системному
// установщику: подтверждение показывает Android, и оно остаётся за человеком.
//
// Работает только в сборке с сайта (см. update_policy.dart): копию из магазина
// обновляет магазин.

import 'dart:io';

import 'package:dio/dio.dart';
import 'package:open_filex/open_filex.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../api/api_client.dart';
import 'update_policy.dart';

/// Включается на этапе сборки: `--dart-define=SELF_UPDATE=true`.
/// По умолчанию выключено, поэтому в магазинный артефакт апдейтер не попадёт,
/// даже если о флаге забыть.
const bool kSelfUpdateEnabled = bool.fromEnvironment('SELF_UPDATE');

const _kLastPromptKey = 'selfupdate_last_prompt';
const _kSkippedCodeKey = 'selfupdate_skipped_code';

class AvailableUpdate {
  final String versionName;
  final int? versionCode;
  final String url;
  final int sizeBytes;
  final String notes;

  const AvailableUpdate({
    required this.versionName,
    required this.versionCode,
    required this.url,
    required this.sizeBytes,
    required this.notes,
  });

  static AvailableUpdate? fromJson(Map<String, dynamic>? m) {
    if (m == null) return null;
    final url = (m['url'] as String?) ?? '';
    if (url.isEmpty) return null;
    return AvailableUpdate(
      versionName: (m['version_name'] as String?) ?? '',
      versionCode: m['version_code'] is int ? m['version_code'] as int : int.tryParse('${m['version_code']}'),
      url: url,
      sizeBytes: m['size_bytes'] is int ? m['size_bytes'] as int : int.tryParse('${m['size_bytes']}') ?? 0,
      notes: (m['notes'] as String?) ?? '',
    );
  }

  String get sizeLabel {
    final mb = sizeBytes / (1024 * 1024);
    return mb >= 1 ? '${mb.toStringAsFixed(0)} МБ' : '';
  }
}

class UpdateService {
  final ApiClient apiClient;

  UpdateService(this.apiClient);

  /// Есть ли обновление, которое сейчас уместно предложить. null — нет.
  Future<AvailableUpdate?> check({DateTime? now}) async {
    final info = await PackageInfo.fromPlatform();
    if (!selfUpdateAllowed(flag: kSelfUpdateEnabled, installerStore: info.installerStore)) {
      return null;
    }

    final Map<String, dynamic> body;
    try {
      final r = await apiClient.get('/app/android/');
      body = (r is Map) ? Map<String, dynamic>.from(r) : <String, dynamic>{};
    } catch (_) {
      return null; // сеть моргнула — не повод беспокоить человека ошибкой
    }

    final update = AvailableUpdate.fromJson(
      body['build'] is Map ? Map<String, dynamic>.from(body['build'] as Map) : null,
    );
    if (update == null) return null;

    final prefs = await SharedPreferences.getInstance();
    final lastPromptMs = prefs.getInt(_kLastPromptKey);
    final allowed = shouldOfferUpdate(
      installedCode: int.tryParse(info.buildNumber) ?? 0,
      latestCode: update.versionCode,
      skippedCode: prefs.getInt(_kSkippedCodeKey),
      lastPromptAt: lastPromptMs == null ? null : DateTime.fromMillisecondsSinceEpoch(lastPromptMs),
      now: now ?? DateTime.now(),
    );
    return allowed ? update : null;
  }

  /// Запомнить, что предложение показано: чаще раза в сутки не повторяем.
  Future<void> markPrompted({DateTime? now}) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_kLastPromptKey, (now ?? DateTime.now()).millisecondsSinceEpoch);
  }

  /// «Пропустить эту версию» — до следующей молчим.
  Future<void> skip(AvailableUpdate update) async {
    final prefs = await SharedPreferences.getInstance();
    if (update.versionCode != null) {
      await prefs.setInt(_kSkippedCodeKey, update.versionCode!);
    }
  }

  /// Скачать файл во временный каталог. Возвращает путь.
  ///
  /// Размер сверяем с заявленным: оборванная загрузка даёт «повреждённый
  /// пакет» уже в установщике, и человеку непонятно, что произошло.
  Future<String> download(AvailableUpdate update, {void Function(int, int)? onProgress}) async {
    final dir = await getTemporaryDirectory();
    final path = '${dir.path}/menugen-${update.versionName}.apk';
    final file = File(path);
    if (await file.exists()) {
      await file.delete();
    }

    await Dio().download(update.url, path, onReceiveProgress: onProgress);

    final size = await file.length();
    if (update.sizeBytes > 0 && size != update.sizeBytes) {
      await file.delete();
      throw Exception('Файл скачался не полностью ($size из ${update.sizeBytes} байт)');
    }
    return path;
  }

  /// Отдать файл системному установщику. Дальше решает человек: Android
  /// показывает своё подтверждение, а после установки приложение закрывается.
  Future<void> install(String path) async {
    await OpenFilex.open(path, type: 'application/vnd.android.package-archive');
  }
}
