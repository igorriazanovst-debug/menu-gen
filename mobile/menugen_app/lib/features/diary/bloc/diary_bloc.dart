import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';
import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/db/app_database.dart';
import '../../../core/models/diary_entry.dart';

part 'diary_event.dart';
part 'diary_state.dart';

class DiaryBloc extends Bloc<DiaryEvent, DiaryState> {
  final ApiClient apiClient;
  final AppDatabase db;

  DiaryBloc({required this.apiClient, required this.db}) : super(const DiaryInitial()) {
    on<DiaryLoadRequested>(_onLoad);
  }

  Future<void> _onLoad(DiaryLoadRequested event, Emitter<DiaryState> emit) async {
    emit(const DiaryLoading());
    try {
      final resp = await apiClient.get('/diary/', params: {'date': event.date});
      final entries = (resp.data['results'] as List)
          .map((j) => DiaryEntry.fromJson(j as Map<String, dynamic>)).toList();
      emit(DiaryLoaded(entries: entries, date: event.date));
    } catch (e) {
      emit(DiaryError(message: ApiException.fromDio(e).message));
    }
  }
}
