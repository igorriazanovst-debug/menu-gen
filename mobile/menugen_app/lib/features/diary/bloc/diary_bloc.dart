import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../core/api/api_client.dart';
import '../../../core/db/app_database.dart';

abstract class DiaryEvent extends Equatable {
  const DiaryEvent();
  @override List<Object?> get props => [];
}
class DiaryLoadRequested extends DiaryEvent {
  final String date;
  const DiaryLoadRequested(this.date);
  @override List<Object?> get props => [date];
}

abstract class DiaryState extends Equatable {
  const DiaryState();
  @override List<Object?> get props => [];
}
class DiaryLoading extends DiaryState { const DiaryLoading(); }
class DiaryLoaded extends DiaryState {
  final String date;
  final List<Map<String, dynamic>> entries;
  const DiaryLoaded({required this.date, required this.entries});
  @override List<Object?> get props => [date, entries];
}
class DiaryError extends DiaryState {
  final String message;
  const DiaryError(this.message);
  @override List<Object?> get props => [message];
}

class DiaryBloc extends Bloc<DiaryEvent, DiaryState> {
  final ApiClient apiClient;
  final AppDatabase db;
  DiaryBloc({required this.apiClient, required this.db}) : super(const DiaryLoading()) {
    on<DiaryLoadRequested>(_onLoad);
  }

  dynamic _data(dynamic r) { try { return r.data; } catch (_) { return r; } }

  Future<void> _onLoad(DiaryLoadRequested e, Emitter<DiaryState> emit) async {
    emit(const DiaryLoading());
    try {
      final r = await apiClient.get('/diary/', params: {'date': e.date});
      final d = _data(r);
      final results = d is Map
          ? (d['results'] as List? ?? []).map((i) => Map<String, dynamic>.from(i as Map)).toList()
          : <Map<String, dynamic>>[];
      emit(DiaryLoaded(date: e.date, entries: results));
    } catch (e) { emit(DiaryError(e.toString())); }
  }
}