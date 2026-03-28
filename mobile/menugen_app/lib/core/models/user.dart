class AppUser {
  final int id;
  final String name;
  final String email;
  const AppUser({required this.id, required this.name, required this.email});
  factory AppUser.fromJson(Map<String, dynamic> json) => AppUser(
        id: json['id'] as int? ?? 0,
        name: json['name'] as String? ?? '',
        email: json['email'] as String? ?? '',
      );
  Map<String, dynamic> toJson() => {'id': id, 'name': name, 'email': email};
}