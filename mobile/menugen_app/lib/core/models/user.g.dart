// GENERATED CODE - DO NOT MODIFY BY HAND
part of 'user.dart';

User _$UserFromJson(Map<String, dynamic> json) => _User(
      id: json['id'] as int,
      name: json['name'] as String,
      email: json['email'] as String?,
      phone: json['phone'] as String?,
      vkId: json['vk_id'] as String?,
      avatarUrl: json['avatar_url'] as String?,
      userType: json['user_type'] as String? ?? 'user',
      allergies: (json['allergies'] as List<dynamic>?)
              ?.map((e) => e as String).toList() ?? [],
      dislikedProducts: (json['disliked_products'] as List<dynamic>?)
              ?.map((e) => e as String).toList() ?? [],
      profile: json['profile'] == null
          ? null
          : UserProfile.fromJson(json['profile'] as Map<String, dynamic>),
    );

Map<String, dynamic> _$UserToJson(_User instance) => <String, dynamic>{
      'id': instance.id,
      'name': instance.name,
      'email': instance.email,
      'phone': instance.phone,
      'vk_id': instance.vkId,
      'avatar_url': instance.avatarUrl,
      'user_type': instance.userType,
      'allergies': instance.allergies,
      'disliked_products': instance.dislikedProducts,
      'profile': instance.profile?.toJson(),
    };

UserProfile _$UserProfileFromJson(Map<String, dynamic> json) => _UserProfile(
      birthYear: json['birth_year'] as int?,
      gender: json['gender'] as String?,
      heightCm: json['height_cm'] as int?,
      weightKg: (json['weight_kg'] as num?)?.toDouble(),
      activityLevel: json['activity_level'] as String? ?? 'moderate',
      goal: json['goal'] as String? ?? 'healthy',
      calorieTarget: json['calorie_target'] as int?,
    );

Map<String, dynamic> _$UserProfileToJson(_UserProfile instance) => <String, dynamic>{
      'birth_year': instance.birthYear,
      'gender': instance.gender,
      'height_cm': instance.heightCm,
      'weight_kg': instance.weightKg,
      'activity_level': instance.activityLevel,
      'goal': instance.goal,
      'calorie_target': instance.calorieTarget,
    };
