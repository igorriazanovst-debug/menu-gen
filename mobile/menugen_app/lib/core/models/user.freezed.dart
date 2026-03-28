// coverage:ignore-file
// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, unused_element
part of 'user.dart';

mixin _$User {
  int get id => throw _privateConstructorUsedError;
  String get name => throw _privateConstructorUsedError;
  String? get email => throw _privateConstructorUsedError;
  String? get phone => throw _privateConstructorUsedError;
  String? get vkId => throw _privateConstructorUsedError;
  String? get avatarUrl => throw _privateConstructorUsedError;
  String get userType => throw _privateConstructorUsedError;
  List<String> get allergies => throw _privateConstructorUsedError;
  List<String> get dislikedProducts => throw _privateConstructorUsedError;
  UserProfile? get profile => throw _privateConstructorUsedError;
  Map<String, dynamic> toJson() => throw _privateConstructorUsedError;
  @JsonKey(ignore: true)
  $UserCopyWith<User> get copyWith => throw _privateConstructorUsedError;
}

abstract class $UserCopyWith<$Res> {
  factory $UserCopyWith(User value, $Res Function(User) then) =
      _$UserCopyWithImpl<$Res, User>;
  @useResult
  $Res call({int id, String name, String? email, String? phone, String? vkId,
      String? avatarUrl, String userType, List<String> allergies,
      List<String> dislikedProducts, UserProfile? profile});
}

class _$UserCopyWithImpl<$Res, $Val extends User> implements $UserCopyWith<$Res> {
  _$UserCopyWithImpl(this._value, this._then);
  final $Val _value;
  final $Res Function($Val) _then;
  @pragma('vm:prefer-inline')
  @override
  $Res call({Object? id=null, Object? name=null, Object? email=freezed,
      Object? phone=freezed, Object? vkId=freezed, Object? avatarUrl=freezed,
      Object? userType=null, Object? allergies=null, Object? dislikedProducts=null,
      Object? profile=freezed}) {
    return _then(_value.copyWith(
      id: null == id ? _value.id : id as int,
      name: null == name ? _value.name : name as String,
      email: freezed == email ? _value.email : email as String?,
      phone: freezed == phone ? _value.phone : phone as String?,
      vkId: freezed == vkId ? _value.vkId : vkId as String?,
      avatarUrl: freezed == avatarUrl ? _value.avatarUrl : avatarUrl as String?,
      userType: null == userType ? _value.userType : userType as String,
      allergies: null == allergies ? _value.allergies : allergies as List<String>,
      dislikedProducts: null == dislikedProducts ? _value.dislikedProducts : dislikedProducts as List<String>,
      profile: freezed == profile ? _value.profile : profile as UserProfile?,
    ) as $Val);
  }
}

class _User implements User {
  const _User({required this.id, required this.name, this.email, this.phone,
      this.vkId, this.avatarUrl, required this.userType,
      this.allergies = const [], this.dislikedProducts = const [], this.profile});
  @override final int id;
  @override final String name;
  @override final String? email;
  @override final String? phone;
  @override final String? vkId;
  @override final String? avatarUrl;
  @override final String userType;
  @override final List<String> allergies;
  @override final List<String> dislikedProducts;
  @override final UserProfile? profile;

  @override
  Map<String, dynamic> toJson() => _$UserToJson(this);

  @override
  @JsonKey(ignore: true)
  _$UserCopyWith<_User> get copyWith => _$_UserCopyWithImpl<_User>(this, _$identity);
}

abstract class _$UserCopyWith<$Res> implements $UserCopyWith<$Res> {
  factory _$UserCopyWith(_User value, $Res Function(_User) then) =
      _$_UserCopyWithImpl<$Res, _User>;
}

class _$_UserCopyWithImpl<$Res> extends _$UserCopyWithImpl<$Res, _User>
    implements _$UserCopyWith<$Res> {
  _$_UserCopyWithImpl(_User super.value, super.then);
}

// ignore: unused_element
T _$identity<T>(T value) => value;
// ignore: unused_element
const freezed = Object();

mixin _$UserProfile {
  int? get birthYear => throw _privateConstructorUsedError;
  String? get gender => throw _privateConstructorUsedError;
  int? get heightCm => throw _privateConstructorUsedError;
  double? get weightKg => throw _privateConstructorUsedError;
  String get activityLevel => throw _privateConstructorUsedError;
  String get goal => throw _privateConstructorUsedError;
  int? get calorieTarget => throw _privateConstructorUsedError;
  Map<String, dynamic> toJson() => throw _privateConstructorUsedError;
  @JsonKey(ignore: true)
  $UserProfileCopyWith<UserProfile> get copyWith => throw _privateConstructorUsedError;
}

abstract class $UserProfileCopyWith<$Res> {
  factory $UserProfileCopyWith(UserProfile value, $Res Function(UserProfile) then) =
      _$UserProfileCopyWithImpl<$Res, UserProfile>;
}

class _$UserProfileCopyWithImpl<$Res, $Val extends UserProfile>
    implements $UserProfileCopyWith<$Res> {
  _$UserProfileCopyWithImpl(this._value, this._then);
  final $Val _value;
  final $Res Function($Val) _then;
  @override
  $Res call({Object? birthYear=freezed, Object? gender=freezed, Object? heightCm=freezed,
      Object? weightKg=freezed, Object? activityLevel=null, Object? goal=null,
      Object? calorieTarget=freezed}) {
    return _then(_value.copyWith(
      birthYear: freezed == birthYear ? _value.birthYear : birthYear as int?,
      gender: freezed == gender ? _value.gender : gender as String?,
      heightCm: freezed == heightCm ? _value.heightCm : heightCm as int?,
      weightKg: freezed == weightKg ? _value.weightKg : weightKg as double?,
      activityLevel: null == activityLevel ? _value.activityLevel : activityLevel as String,
      goal: null == goal ? _value.goal : goal as String,
      calorieTarget: freezed == calorieTarget ? _value.calorieTarget : calorieTarget as int?,
    ) as $Val);
  }
}

class _UserProfile implements UserProfile {
  const _UserProfile({this.birthYear, this.gender, this.heightCm, this.weightKg,
      this.activityLevel = 'moderate', this.goal = 'healthy', this.calorieTarget});
  @override final int? birthYear;
  @override final String? gender;
  @override final int? heightCm;
  @override final double? weightKg;
  @override final String activityLevel;
  @override final String goal;
  @override final int? calorieTarget;

  @override
  Map<String, dynamic> toJson() => _$UserProfileToJson(this);

  @override
  @JsonKey(ignore: true)
  _$UserProfileCopyWith<_UserProfile> get copyWith =>
      _$_UserProfileCopyWithImpl<_UserProfile>(this, _$identity);
}

abstract class _$UserProfileCopyWith<$Res> implements $UserProfileCopyWith<$Res> {
  factory _$UserProfileCopyWith(_UserProfile v, $Res Function(_UserProfile) t) =
      _$_UserProfileCopyWithImpl<$Res, _UserProfile>;
}
class _$_UserProfileCopyWithImpl<$Res> extends _$UserProfileCopyWithImpl<$Res, _UserProfile>
    implements _$UserProfileCopyWith<$Res> {
  _$_UserProfileCopyWithImpl(_UserProfile super.value, super.then);
}
