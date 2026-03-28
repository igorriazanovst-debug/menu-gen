part of 'diary_bloc.dart';
abstract class DiaryEvent extends Equatable {
  const DiaryEvent();
  @override List<Object?> get props => [];
}
class DiaryLoadRequested extends DiaryEvent {
  final String date;
  const DiaryLoadRequested(this.date);
  @override List<Object?> get props => [date];
}
