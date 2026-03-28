part of 'diary_bloc.dart';
abstract class DiaryState extends Equatable {
  const DiaryState();
  @override List<Object?> get props => [];
}
class DiaryInitial extends DiaryState { const DiaryInitial(); }
class DiaryLoading extends DiaryState { const DiaryLoading(); }
class DiaryLoaded extends DiaryState {
  final List<DiaryEntry> entries;
  final String date;
  const DiaryLoaded({required this.entries, required this.date});
  @override List<Object?> get props => [entries, date];
}
class DiaryError extends DiaryState {
  final String message;
  const DiaryError({required this.message});
  @override List<Object?> get props => [message];
}
