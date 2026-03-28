part of 'family_bloc.dart';

abstract class FamilyState extends Equatable {
  const FamilyState();
  @override List<Object?> get props => [];
}
class FamilyInitial extends FamilyState { const FamilyInitial(); }
class FamilyLoading extends FamilyState { const FamilyLoading(); }
class FamilyLoaded extends FamilyState {
  final Family family;
  const FamilyLoaded({required this.family});
  @override List<Object?> get props => [family];
}
class FamilyError extends FamilyState {
  final String message;
  const FamilyError({required this.message});
  @override List<Object?> get props => [message];
}
