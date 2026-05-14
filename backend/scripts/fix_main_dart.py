#!/usr/bin/env python3
"""MG-profile-premium fix: пропатчить main.dart (false-skip)."""
import sys
from pathlib import Path

PATH = Path("/opt/menugen/mobile/menugen_app/lib/main.dart")
src = PATH.read_text(encoding="utf-8")

old = (
    "          create: (_) => AuthBloc(apiClient: apiClient, tokenStorage: tokenStorage)\n"
    "            ..add(const AuthCheckRequested()),"
)
new = (
    "          create: (_) => AuthBloc(\n"
    "            apiClient: apiClient,\n"
    "            tokenStorage: tokenStorage,\n"
    "            premiumGate: premiumGate,\n"
    "          )\n"
    "            ..add(const AuthCheckRequested()),"
)

if old not in src:
    print("anchor not found — already patched or source changed")
    print("current AuthBloc init:")
    for i, line in enumerate(src.splitlines(), 1):
        if "AuthBloc(" in line:
            print(f"  {i}: {line}")
    sys.exit(1)

src = src.replace(old, new, 1)
PATH.write_text(src, encoding="utf-8")
print(f"patched {PATH}")
