import 'package:freezed_annotation/freezed_annotation.dart';
part 'user.freezed.dart';
part 'user.g.dart';

@freezed
class User with _$User {
  const factory User({
    required int id,
    required String name,
    String? email,
    String? phone,
    String? vkId,
    String? avatarUrl,
    required String userType,
    @Default([]) List<String> allergies,
    @Default([]) List<String> dislikedProducts,
    UserProfile? profile,
  }) = _User;

  factory User.fromJson(Map<String, dynamic> json) => _$UserFromJson(json);
}

@freezed
class UserProfile with _$UserProfile {
  const factory UserProfile({
    int? birthYear,
    String? gender,
    int? heightCm,
    double? weightKg,
    @Default('moderate') String activityLevel,
    @Default('healthy') String goal,
    int? calorieTarget,
  }) = _UserProfile;

  factory UserProfile.fromJson(Map<String, dynamic> json) => _$UserProfileFromJson(json);
}
