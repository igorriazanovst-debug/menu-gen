// MG_SELFUPDATE: когда предлагать обновление, а когда молчать.
//
// Вынесено отдельно от загрузки и установки, потому что ошибиться легче всего
// именно здесь: предложение, всплывающее при каждом запуске, раздражает
// сильнее, чем помогает, и его начинают закрывать не читая.
//
// Правила: обновление есть, эту версию не откладывали, и с прошлого показа
// прошли сутки.

const Duration kUpdateCooldown = Duration(hours: 24);

/// Магазины, которые сами обновляют приложение. Если копия пришла оттуда,
/// своим апдейтером мы не пользуемся: правила магазинов это запрещают, а
/// человек и так получит обновление привычным путём.
const Set<String> kStoreInstallers = {
  'ru.vk.store', // RuStore
  'com.android.vending', // Google Play
  'com.huawei.appmarket',
  'com.sec.android.app.samsungapps',
  'com.xiaomi.mipicks',
};

/// Можно ли этой копии обновлять себя самой.
///
/// [flag] — собрана ли сборка с апдейтером (в магазинной его нет физически).
/// [installerStore] — кто установил приложение, по данным системы.
///
/// Проверок две, и это не перестраховка: флаг защищает от того, что магазинная
/// сборка вообще содержит такой код, а проверка установщика — от ошибки в
/// сборке, когда сайтовый артефакт по недосмотру уехал в магазин.
bool selfUpdateAllowed({required bool flag, String? installerStore}) {
  if (!flag) return false;
  final installer = (installerStore ?? '').trim();
  return !kStoreInstallers.contains(installer);
}

/// Показывать ли предложение обновиться.
///
/// [skippedCode] — версия, которую человек уже отложил кнопкой «пропустить».
/// [lastPromptAt] — когда предлагали в прошлый раз (null — ещё ни разу).
bool shouldOfferUpdate({
  required int installedCode,
  int? latestCode,
  int? skippedCode,
  DateTime? lastPromptAt,
  required DateTime now,
  Duration cooldown = kUpdateCooldown,
}) {
  // Без номера сборки сравнивать нечего: молчим, а не гадаем по названию.
  if (latestCode == null) return false;
  if (latestCode <= installedCode) return false;
  if (skippedCode != null && skippedCode >= latestCode) return false;
  if (lastPromptAt != null && now.difference(lastPromptAt) < cooldown) return false;
  return true;
}
