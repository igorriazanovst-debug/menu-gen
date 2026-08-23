// MG_SELFUPDATE: предложение обновиться и загрузка с прогрессом.
//
// Диалог не блокирующий: «Позже» закрывает его, «Пропустить версию» убирает до
// следующей. Размер показываем до загрузки — 50 мегабайт по мобильной сети без
// предупреждения это неприятный сюрприз.

import 'package:flutter/material.dart';

import 'update_service.dart';

Future<void> showUpdatePrompt(
  BuildContext context,
  UpdateService service,
  AvailableUpdate update,
) async {
  await service.markPrompted();
  if (!context.mounted) return;

  final action = await showDialog<String>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: Text('Версия ${update.versionName}'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (update.notes.isNotEmpty) Text(update.notes),
          if (update.notes.isNotEmpty) const SizedBox(height: 8),
          Text(
            update.sizeLabel.isEmpty
                ? 'Обновление скачается и предложит установку.'
                : 'Скачается ${update.sizeLabel}, затем Android предложит установку.',
            style: const TextStyle(fontSize: 12, color: Colors.black54),
          ),
        ],
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx, 'skip'), child: const Text('Пропустить версию')),
        TextButton(onPressed: () => Navigator.pop(ctx, 'later'), child: const Text('Позже')),
        FilledButton(onPressed: () => Navigator.pop(ctx, 'update'), child: const Text('Обновить')),
      ],
    ),
  );

  if (action == 'skip') {
    await service.skip(update);
    return;
  }
  if (action != 'update' || !context.mounted) return;

  await _downloadAndInstall(context, service, update);
}

Future<void> _downloadAndInstall(
  BuildContext context,
  UpdateService service,
  AvailableUpdate update,
) async {
  final progress = ValueNotifier<double>(0);
  showDialog<void>(
    context: context,
    barrierDismissible: false,
    builder: (_) => AlertDialog(
      title: const Text('Загрузка обновления'),
      content: ValueListenableBuilder<double>(
        valueListenable: progress,
        builder: (_, value, __) => Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            LinearProgressIndicator(value: value > 0 ? value : null),
            const SizedBox(height: 8),
            Text(value > 0 ? '${(value * 100).round()}%' : 'Начинаем…'),
          ],
        ),
      ),
    ),
  );

  try {
    final path = await service.download(
      update,
      onProgress: (received, total) {
        if (total > 0) progress.value = received / total;
      },
    );
    if (context.mounted) Navigator.of(context).pop(); // закрыть прогресс
    await service.install(path);
  } catch (e) {
    if (context.mounted) {
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Не удалось скачать обновление: $e')),
      );
    }
  } finally {
    progress.dispose();
  }
}
