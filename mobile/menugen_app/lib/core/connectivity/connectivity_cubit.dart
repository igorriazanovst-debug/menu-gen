import 'dart:async';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

enum ConnectivityStatus { online, offline }

class ConnectivityCubit extends Cubit<ConnectivityStatus> {
  late final StreamSubscription _sub;

  ConnectivityCubit() : super(ConnectivityStatus.online) {
    _sub = Connectivity().onConnectivityChanged.listen((results) {
      final isOnline = results.any((r) => r != ConnectivityResult.none);
      emit(isOnline ? ConnectivityStatus.online : ConnectivityStatus.offline);
    });
  }

  @override
  Future<void> close() {
    _sub.cancel();
    return super.close();
  }
}
