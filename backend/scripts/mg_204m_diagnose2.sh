#!/usr/bin/env bash
# MG-204 mobile — диагноз 2: дамп ключевых файлов целиком
set -u

MOB="/opt/menugen/mobile/menugen_app"

dump() {
  local path="$1"
  echo
  echo "================================================================"
  echo "FILE: $path"
  echo "================================================================"
  if [ -f "$path" ]; then
    nl -ba "$path"
  else
    echo "  ОТСУТСТВУЕТ"
  fi
}

dump "${MOB}/lib/features/family/models/family_models.dart"
dump "${MOB}/lib/features/family/bloc/family_bloc.dart"
dump "${MOB}/lib/features/family/screens/family_screen.dart"
dump "${MOB}/lib/features/profile/screens/profile_screen.dart"
dump "${MOB}/lib/core/models/user.dart"
dump "${MOB}/lib/core/api/dio_api_client.dart"
dump "${MOB}/lib/core/api/api_client.dart"

echo
echo "================================================================"
echo "DUMP DONE"
echo "================================================================"
