part of 'family_bloc.dart';

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
