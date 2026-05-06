#!/bin/bash
set -uo pipefail
ROOT="/opt/menugen"
COMPOSE="$ROOT/docker-compose.yml"

echo "=== пути к MenuGenerateView ==="
docker compose -f "$COMPOSE" exec -T backend python manage.py shell -c "
from django.urls import get_resolver
resolver = get_resolver()
def walk(patterns, prefix=''):
    for p in patterns:
        if hasattr(p, 'url_patterns'):
            walk(p.url_patterns, prefix + str(p.pattern))
        else:
            cb = getattr(p, 'callback', None)
            name = getattr(cb, '__qualname__', getattr(cb, '__name__', '?')) if cb else '?'
            full = prefix + str(p.pattern)
            if 'menu' in full.lower() or 'Menu' in name:
                print(f'{full:60s} -> {name}')
walk(resolver.url_patterns)
"
