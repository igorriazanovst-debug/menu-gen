import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';
import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../models/family_models.dart';

part 'family_event.dart';
part 'family_state.dart';

class FamilyBloc extends Bloc<FamilyEvent, FamilyState> {
  final ApiClient apiClient;

  FamilyBloc({required this.apiClient}) : super(const FamilyInitial()) {
    on<FamilyLoadRequested>(_onLoad);
    on<FamilyInviteMemberRequested>(_onInvite);
    on<FamilyRemoveMemberRequested>(_onRemove);
  }

  Future<void> _onLoad(FamilyLoadRequested event, Emitter<FamilyState> emit) async {
    emit(const FamilyLoading());
    try {
      final resp = await apiClient.get('/family/');
      emit(FamilyLoaded(family: Family.fromJson(resp.data as Map<String, dynamic>)));
    } catch (e) {
      emit(FamilyError(message: ApiException.fromDio(e).message));
    }
  }

  Future<void> _onInvite(FamilyInviteMemberRequested event, Emitter<FamilyState> emit) async {
    try {
      await apiClient.post('/family/invite/', data: {'email': event.email});
      add(FamilyLoadRequested());
    } catch (e) {
      emit(FamilyError(message: ApiException.fromDio(e).message));
    }
  }

  Future<void> _onRemove(FamilyRemoveMemberRequested event, Emitter<FamilyState> emit) async {
    try {
      await apiClient.delete('/family/members/\${event.memberId}/');
      add(FamilyLoadRequested());
    } catch (e) {
      emit(FamilyError(message: ApiException.fromDio(e).message));
    }
  }
}
