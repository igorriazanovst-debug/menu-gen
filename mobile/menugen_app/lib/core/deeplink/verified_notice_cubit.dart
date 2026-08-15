// MG_VERIFYDEEPLINK: «e-mail подтверждён» — состояние приложения, а не экрана.
//
// Держать это в State экрана входа нельзя: смена AuthState пересоздаёт роутер
// (main.dart), а с ним и экран — отметка исчезла бы сама собой. Кубит живёт
// выше роутера, поэтому переживает и переход по ссылке, и любой редирект.
import 'package:flutter_bloc/flutter_bloc.dart';

import 'verified_link.dart';

class VerifiedNoticeCubit extends Cubit<String?> {
  VerifiedNoticeCubit() : super(null);

  /// Пришла ссылка. Не про подтверждение — ничего не меняем.
  void handleLink(Uri? uri) {
    final email = verifiedEmailFromLink(uri);
    if (email == null) return;
    emit(email);
  }

  /// Отметку показали и она отработала (вошли либо ушли с экрана).
  void clear() => emit(null);
}
