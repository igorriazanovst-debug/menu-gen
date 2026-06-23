"""
Build a YandexART prompt for a recipe (decision 1-B: template + LLM slots).

Fixed brand style (top view, rustic oak table, soft daylight, muted-but-natural
colors) is constant for every recipe. A text LLM (YandexGPT) fills only the
per-dish slots: dish_visual, garnish, dishware, cutlery, color_hint — i.e. it
varies the dishware/cutlery from the recipe, as requested.

Public API:
    slots  = build_slots(title, ingredients, steps, dish_type)   # LLM (+fallback)
    prompt = assemble_prompt(title, slots)                        # final ART text
    prompt = build_prompt(title, ingredients, steps, dish_type)   # convenience
"""

from __future__ import annotations

import json
import re
from typing import Optional

from django.conf import settings

from apps.common.ai_provider import AIRequestError, get_ai_client

# ── per dish_type fallback dishware/cutlery (used if LLM fails) ──────────────
_DISH_DEFAULTS = {
    "soup": ("глубокой керамической миске", "ложка"),
    "main": ("белой фарфоровой тарелке", "вилка и нож"),
    "salad": ("керамической тарелке", "вилка"),
    "side": ("керамической тарелке", "вилка"),
    "dessert": ("небольшой десертной тарелке", "десертная ложка"),
    "drink": ("стеклянном стакане", ""),
    "bakery": ("деревянной доске", ""),
    "sauce": ("небольшой соуснице", "ложка"),
    "snack": ("керамической тарелке", ""),
    "breakfast_dish": ("керамической тарелке", "ложка"),
}
_DISH_LABELS = {
    "soup": "первое (суп)",
    "main": "второе/горячее",
    "salad": "салат",
    "side": "гарнир",
    "dessert": "десерт",
    "drink": "напиток",
    "bakery": "выпечка",
    "sauce": "соус",
    "snack": "перекус",
    "breakfast_dish": "блюдо на завтрак",
}

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def _ingredient_names(ingredients, limit: int = 8) -> list[str]:
    """Pull readable ingredient names from the recipe's JSON list."""
    out: list[str] = []
    for it in ingredients or []:
        if isinstance(it, dict):
            name = (it.get("name") or it.get("raw") or "").strip()
        else:
            name = str(it).strip()
        if name:
            out.append(name)
        if len(out) >= limit:
            break
    return out


def _strip_fences(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = _FENCE_RE.sub("", t)
    return t.strip()


def _system() -> str:
    return (
        "Ты — фуд-стилист. По рецепту опиши, как готовое блюдо выглядит на "
        "фотокарточке для меню. Верни СТРОГО JSON без markdown и без пояснений, "
        "формат: "
        '{"dish_visual":"...","garnish":"...","dishware":"...","cutlery":"...","color_hint":"..."}. '
        "Поля: dish_visual — 1–2 предложения: что это за блюдо, его консистенция/"
        "текстура и главные видимые компоненты; garnish — чем украшено (зелень и "
        "т.п.) или пустая строка; dishware — в чём подаётся, В ПРЕДЛОЖНОМ ПАДЕЖЕ "
        "(отвечает на «в чём?»: глубокой керамической миске / белой фарфоровой "
        "тарелке / деревянной доске / стеклянном стакане…), без слова «в»; "
        "cutlery — прибор рядом (ложка / вилка и нож / десертная ложка) или пустая "
        "строка; color_hint — реальный естественный цвет/оттенок блюда (например: "
        "борщ — насыщённый свекольный красный; окрошка — бледный кремовый). "
        "Посуду и прибор подбирай ПО ТИПУ блюда: суп → глубокая миска + ложка; "
        "второе → тарелка + вилка и нож; салат → тарелка/миска + вилка; гарнир → "
        "тарелка + вилка; десерт → десертная тарелка + ложка; напиток → стакан/"
        "чашка, без прибора; выпечка → доска/тарелка, обычно без прибора. "
        "Пиши на русском, кратко, без брендов и без названий сайтов."
    )


def _user(title: str, ingredients, steps, dish_type: Optional[str]) -> str:
    names = _ingredient_names(ingredients)
    parts = [f"Название: {title}"]
    if dish_type:
        parts.append(f"Тип блюда: {_DISH_LABELS.get(dish_type, dish_type)}")
    if names:
        parts.append("Ингредиенты: " + ", ".join(names))
    if steps:
        first = steps[0] if isinstance(steps[0], str) else json.dumps(steps[0], ensure_ascii=False)
        parts.append("Первый шаг: " + str(first)[:300])
    return "\n".join(parts)


def _fallback_slots(title: str, dish_type: Optional[str]) -> dict:
    dishware, cutlery = _DISH_DEFAULTS.get(dish_type or "", ("керамической тарелке", "вилка"))
    return {
        "dish_visual": f"Блюдо «{title}», аккуратно поданное и готовое к подаче",
        "garnish": "",
        "dishware": dishware,
        "cutlery": cutlery,
        "color_hint": "естественные, приглушённые цвета блюда",
    }


def build_slots(title: str, ingredients=None, steps=None, dish_type: Optional[str] = None) -> dict:
    """Ask the text LLM for per-dish slots; fall back to dish_type defaults."""
    client = get_ai_client()
    model = getattr(settings, "AI_IMAGE_PROMPT_MODEL", "") or getattr(settings, "AI_TEXT_MODEL", "")
    if model and type(client).__name__ == "YandexAIClient":
        setattr(client, "_text_model", model)

    try:
        raw = client.complete(
            prompt=_user(title, ingredients, steps, dish_type),
            system=_system(),
            max_tokens=400,
            temperature=0.3,
        )
    except AIRequestError:
        return _fallback_slots(title, dish_type)

    cleaned = _strip_fences(raw)
    try:
        parsed = json.loads(cleaned)
    except ValueError:
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not m:
            return _fallback_slots(title, dish_type)
        try:
            parsed = json.loads(m.group(0))
        except ValueError:
            return _fallback_slots(title, dish_type)

    if not isinstance(parsed, dict):
        return _fallback_slots(title, dish_type)

    fb = _fallback_slots(title, dish_type)
    out = {}
    for key in ("dish_visual", "garnish", "dishware", "cutlery", "color_hint"):
        val = parsed.get(key)
        out[key] = str(val).strip() if val is not None else ""
    # keep sensible defaults where the model returned nothing essential
    if not out["dish_visual"]:
        out["dish_visual"] = fb["dish_visual"]
    if not out["dishware"]:
        out["dishware"] = fb["dishware"]
    if not out["color_hint"]:
        out["color_hint"] = fb["color_hint"]
    return out


def assemble_prompt(title: str, slots: dict) -> str:
    """Slot the per-dish parts into the fixed brand template."""
    dish_visual = (slots.get("dish_visual") or "").strip().rstrip(".")
    garnish = (slots.get("garnish") or "").strip().rstrip(".")
    dishware = (slots.get("dishware") or "керамической тарелке").strip().rstrip(".")
    cutlery = (slots.get("cutlery") or "").strip().rstrip(".")
    color_hint = (slots.get("color_hint") or "естественные, приглушённые цвета").strip().rstrip(".")

    lines = [
        f"Фотореалистичный вид сверху готового блюда «{title}» на деревенском "
        "дубовом столе без скатерти. Мягкий естественный дневной свет. "
        "Дубовый стол имеет видимую текстуру древесины, тёплый, но не яркий.",
        f"{dish_visual}.",
    ]
    if garnish:
        lines.append(f"Украшено {garnish}.")
    lines.append(f"Подаётся в {dishware}.")
    if cutlery:
        lines.append(f"Рядом — {cutlery}.")
    lines.append(
        f"Цвета приглушённые и неяркие, но естественные для блюда ({color_hint}). "
        "Общая тональность мягкая и натуральная."
    )
    lines.append("Без текста, без надписей, без логотипов, без рук и людей. Квадратный кадр 1:1.")
    return " ".join(lines)


def build_prompt(title: str, ingredients=None, steps=None, dish_type: Optional[str] = None) -> str:
    """Convenience: slots (LLM) -> assembled ART prompt."""
    return assemble_prompt(title, build_slots(title, ingredients, steps, dish_type))
