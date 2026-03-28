import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../core/api/api_client.dart';

abstract class FamilyEvent extends Equatable {
  const FamilyEvent();
  @override List<Object?> get props => [];
}
class FamilyLoadRequested extends FamilyEvent { const FamilyLoadRequested(); }
class FamilyInviteMemberRequested extends FamilyEvent {
  final String email;
  const FamilyInviteMemberRequested(this.email);
  @override List<Object?> get props => [email];
}
class FamilyRemoveMemberRequested extends FamilyEvent {
  final int memberId;
  const FamilyRemoveMemberRequested(this.memberId);
  @override List<Object?> get props => [memberId];
}

abstract class FamilyState extends Equatable {
  const FamilyState();
  @override List<Object?> get props => [];
}
class FamilyLoading extends FamilyState { const FamilyLoading(); }
class FamilyLoaded extends FamilyState {
  final Map<String, dynamic> family;
  const FamilyLoaded(this.family);
  @override List<Object?> get props => [family];
}
class FamilyError extends FamilyState {
  final String message;
  const FamilyError(this.message);
  @override List<Object?> get props => [message];
}

class FamilyBloc extends Bloc<FamilyEvent, FamilyState> {
  final ApiClient apiClient;
  FamilyBloc({required this.apiClient}) : super(const FamilyLoading()) {
    on<FamilyLoadRequested>(_onLoad);
    on<FamilyInviteMemberRequested>(_onInvite);
    on<FamilyRemoveMemberRequested>(_onRemove);
  }

  dynamic _data(dynamic r) { try { return r.data; } catch (_) { return r; } }

  Future<void> _onLoad(FamilyLoadRequested e, Emitter<FamilyState> emit) async {
    emit(const FamilyLoading());
    try {
      final r = await apiClient.get('/family/');
      emit(FamilyLoaded(Map<String, dynamic>.from(_data(r) as Map)));
    } catch (e) { emit(FamilyError(e.toString())); }
  }

  Future<void> _onInvite(FamilyInviteMemberRequested e, Emitter<FamilyState> emit) async {
    try {
      await apiClient.post('/family/invite/', data: {'email': e.email});
      add(const FamilyLoadRequested());
    } catch (e) { emit(FamilyError(e.toString())); }
  }

  Future<void> _onRemove(FamilyRemoveMemberRequested e, Emitter<FamilyState> emit) async {
    try {
      await apiClient.delete('/family/members/${e.memberId}/');
      add(const FamilyLoadRequested());
    } catch (e) { emit(FamilyError(e.toString())); }
  }
}