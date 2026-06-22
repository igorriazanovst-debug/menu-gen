import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../core/api/api_client.dart';

// ── Events ────────────────────────────────────────────────────────────────────

abstract class FamilyEvent extends Equatable {
  const FamilyEvent();
  @override
  List<Object?> get props => [];
}

class FamilyLoadRequested extends FamilyEvent {
  const FamilyLoadRequested();
}

class FamilyInviteMemberRequested extends FamilyEvent {
  final String? email;
  final String? phone;
  const FamilyInviteMemberRequested({this.email, this.phone});
  @override
  List<Object?> get props => [email, phone];
}

// MG_MANAGEDMEMBER: add a member card without inviting an existing user.
class FamilyCreateManagedRequested extends FamilyEvent {
  final String name;
  const FamilyCreateManagedRequested(this.name);
  @override
  List<Object?> get props => [name];
}

// MG_MANAGEDMEMBER: give a managed member their own login.
class FamilyAttachAccountRequested extends FamilyEvent {
  final int memberId;
  final String? email;
  final String? phone;
  final String? password;
  const FamilyAttachAccountRequested({
    required this.memberId,
    this.email,
    this.phone,
    this.password,
  });
  @override
  List<Object?> get props => [memberId, email, phone, password];
}

class FamilyRemoveMemberRequested extends FamilyEvent {
  final int memberId;
  const FamilyRemoveMemberRequested(this.memberId);
  @override
  List<Object?> get props => [memberId];
}

class FamilyUpdateMemberRequested extends FamilyEvent {
  final int memberId;
  final Map<String, dynamic> data;
  const FamilyUpdateMemberRequested({required this.memberId, required this.data});
  @override
  List<Object?> get props => [memberId, data];
}

// MG_SHOPMOB002: head changes the family currency (PATCH /family/).
class FamilyUpdateCurrencyRequested extends FamilyEvent {
  final String currency;
  const FamilyUpdateCurrencyRequested(this.currency);
  @override
  List<Object?> get props => [currency];
}

// ── States ────────────────────────────────────────────────────────────────────

abstract class FamilyState extends Equatable {
  const FamilyState();
  @override
  List<Object?> get props => [];
}

class FamilyLoading extends FamilyState {
  const FamilyLoading();
}

class FamilyLoaded extends FamilyState {
  final Map<String, dynamic> family;
  const FamilyLoaded(this.family);
  @override
  List<Object?> get props => [family];
}

class FamilyActionInProgress extends FamilyState {
  final Map<String, dynamic> family;
  const FamilyActionInProgress(this.family);
  @override
  List<Object?> get props => [family];
}

class FamilyError extends FamilyState {
  final String message;
  final Map<String, dynamic>? family;
  const FamilyError(this.message, {this.family});
  @override
  List<Object?> get props => [message, family];
}

// ── Bloc ──────────────────────────────────────────────────────────────────────

class FamilyBloc extends Bloc<FamilyEvent, FamilyState> {
  final ApiClient apiClient;

  FamilyBloc({required this.apiClient}) : super(const FamilyLoading()) {
    on<FamilyLoadRequested>(_onLoad);
    on<FamilyInviteMemberRequested>(_onInvite);
    on<FamilyCreateManagedRequested>(_onCreateManaged); // MG_MANAGEDMEMBER
    on<FamilyAttachAccountRequested>(_onAttachAccount); // MG_MANAGEDMEMBER
    on<FamilyRemoveMemberRequested>(_onRemove);
    on<FamilyUpdateMemberRequested>(_onUpdate);
    on<FamilyUpdateCurrencyRequested>(_onUpdateCurrency); // MG_SHOPMOB002
  }

  dynamic _data(dynamic r) {
    try {
      return r.data;
    } catch (_) {
      return r;
    }
  }

  Map<String, dynamic>? get _currentFamily {
    final s = state;
    if (s is FamilyLoaded) return s.family;
    if (s is FamilyActionInProgress) return s.family;
    if (s is FamilyError) return s.family;
    return null;
  }

  Future<void> _onLoad(FamilyLoadRequested e, Emitter<FamilyState> emit) async {
    emit(const FamilyLoading());
    try {
      final r = await apiClient.get('/family/');
      emit(FamilyLoaded(Map<String, dynamic>.from(_data(r) as Map)));
    } catch (e) {
      emit(FamilyError(e.toString()));
    }
  }

  Future<void> _onInvite(
      FamilyInviteMemberRequested e, Emitter<FamilyState> emit) async {
    final current = _currentFamily;
    if (current != null) emit(FamilyActionInProgress(current));
    try {
      final body = <String, dynamic>{};
      if (e.email != null && e.email!.isNotEmpty) body['email'] = e.email;
      if (e.phone != null && e.phone!.isNotEmpty) body['phone'] = e.phone;
      await apiClient.post('/family/invite/', data: body);
      add(const FamilyLoadRequested());
    } catch (e) {
      emit(FamilyError(e.toString(), family: current));
    }
  }

  // MG_MANAGEDMEMBER
  Future<void> _onCreateManaged(
      FamilyCreateManagedRequested e, Emitter<FamilyState> emit) async {
    final current = _currentFamily;
    if (current != null) emit(FamilyActionInProgress(current));
    try {
      await apiClient.post('/family/members/create-managed/',
          data: {'name': e.name});
      add(const FamilyLoadRequested());
    } catch (err) {
      emit(FamilyError(err.toString(), family: current));
    }
  }

  // MG_MANAGEDMEMBER
  Future<void> _onAttachAccount(
      FamilyAttachAccountRequested e, Emitter<FamilyState> emit) async {
    final current = _currentFamily;
    if (current != null) emit(FamilyActionInProgress(current));
    try {
      final body = <String, dynamic>{};
      if (e.email != null && e.email!.isNotEmpty) body['email'] = e.email;
      if (e.phone != null && e.phone!.isNotEmpty) body['phone'] = e.phone;
      if (e.password != null && e.password!.isNotEmpty) {
        body['password'] = e.password;
      }
      await apiClient.post('/family/members/${e.memberId}/attach-account/',
          data: body);
      add(const FamilyLoadRequested());
    } catch (err) {
      emit(FamilyError(err.toString(), family: current));
    }
  }

  Future<void> _onRemove(
      FamilyRemoveMemberRequested e, Emitter<FamilyState> emit) async {
    final current = _currentFamily;
    if (current != null) emit(FamilyActionInProgress(current));
    try {
      await apiClient.delete('/family/members/${e.memberId}/');
      add(const FamilyLoadRequested());
    } catch (e) {
      emit(FamilyError(e.toString(), family: current));
    }
  }

  Future<void> _onUpdate(
      FamilyUpdateMemberRequested e, Emitter<FamilyState> emit) async {
    final current = _currentFamily;
    if (current != null) emit(FamilyActionInProgress(current));
    try {
      await apiClient.patch(
        '/family/members/${e.memberId}/update/',
        data: e.data,
      );
      add(const FamilyLoadRequested());
    } catch (e) {
      emit(FamilyError(e.toString(), family: current));
    }
  }

  // MG_SHOPMOB002
  Future<void> _onUpdateCurrency(
      FamilyUpdateCurrencyRequested e, Emitter<FamilyState> emit) async {
    final current = _currentFamily;
    if (current != null) emit(FamilyActionInProgress(current));
    try {
      await apiClient.patch('/family/', data: {'currency': e.currency});
      add(const FamilyLoadRequested());
    } catch (err) {
      emit(FamilyError(err.toString(), family: current));
    }
  }
}
