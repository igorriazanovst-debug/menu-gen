"""
Nutritionist Agent — post-processes scraped recipes using Claude API.

Responsibilities:
  1. Classify meal_type (breakfast / lunch / dinner) for recipes without a tag.
  2. Fill in missing КБЖУ by estimating from ingredient list.
  3. Filter out recipes nutritionally unsuitable for their meal type.
  4. Select a balanced set: 100 per meal type with cuisine diversity.

Usage:
    ANTHROPIC_API_KEY=sk-... python nutritionist_agent.py \
        [--input scraped_recipes.json] \
        [--output enriched_recipes.json] \
        [--target 100]

Environment:
    ANTHROPIC_API_KEY  — required
"""
import argparse
import json
import logging
import os
import re
from pathlib import Path

import anthropic

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Nutritionist rules per meal type
# ---------------------------------------------------------------------------

MEAL_RULES = {
    "breakfast": {
        "cal_min": 200, "cal_max": 550,
        "note": "Завтрак: сложные углеводы + белок, умеренные жиры.",
    },
    "lunch": {
        "cal_min": 400, "cal_max": 900,
        "note": "Обед: полноценный приём, сбалансированный БЖУ.",
    },
    "dinner": {
        "cal_min": 280, "cal_max": 680,
        "note": "Ужин: лёгкий белок + овощи, минимум быстрых углеводов.",
    },
}

SYSTEM_PROMPT = """\
Ты опытный нутрициолог и диетолог. Работаешь с базой рецептов восточноевропейской, \
итальянской и французской кухонь. Твоя задача — оценивать рецепты с точки зрения \
современной нутрициологии, классифицировать приёмы пищи и рассчитывать КБЖУ на 100г.\
"""


def _make_client() -> anthropic.Anthropic:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set.")
    return anthropic.Anthropic(api_key=key)


# ---------------------------------------------------------------------------
# Step 1: classify meal type
# ---------------------------------------------------------------------------

def classify_meal_type(client: anthropic.Anthropic, recipe: dict) -> str:
    ingredients_preview = ", ".join(
        i["name"] for i in recipe.get("ingredients", [])[:10]
    )
    nutrition_str = json.dumps(recipe.get("nutrition", {}), ensure_ascii=False)

    prompt = (
        f"Рецепт: «{recipe['title']}»\n"
        f"Кухня: {recipe.get('country', '—')}\n"
        f"Ингредиенты: {ingredients_preview}\n"
        f"КБЖУ (на 100г): {nutrition_str}\n\n"
        "Определи оптимальный тип приёма пищи для этого блюда.\n"
        "Ответь ОДНИМ словом без объяснений: breakfast, lunch или dinner."
    )

    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=10,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    result = resp.content[0].text.strip().lower()
    return result if result in ("breakfast", "lunch", "dinner") else "lunch"


# ---------------------------------------------------------------------------
# Step 2: fill in missing КБЖУ
# ---------------------------------------------------------------------------

def fill_nutrition(client: anthropic.Anthropic, recipe: dict) -> dict:
    nutrition = recipe.get("nutrition", {})
    required = {"calories", "proteins", "fats", "carbs"}

    if required.issubset(nutrition.keys()):
        return nutrition  # already complete

    ingredients_text = "\n".join(
        f"  - {i['name']} {i.get('quantity', '')} {i.get('unit', '')}".strip()
        for i in recipe.get("ingredients", [])[:12]
    )
    existing = json.dumps(nutrition, ensure_ascii=False) if nutrition else "нет данных"
    missing = required - nutrition.keys()

    prompt = (
        f"Рецепт: «{recipe['title']}»\n"
        f"Порций: {recipe.get('servings') or 4}\n"
        f"Ингредиенты:\n{ingredients_text}\n"
        f"Имеющиеся данные КБЖУ: {existing}\n"
        f"Недостающие поля: {', '.join(missing)}\n\n"
        "Рассчитай недостающие значения КБЖУ на 100 г готового блюда.\n"
        "Верни ТОЛЬКО валидный JSON — без пояснений, без markdown:\n"
        '{"calories":{"value":"X","unit":"kcal"},'
        '"proteins":{"value":"X","unit":"g"},'
        '"fats":{"value":"X","unit":"g"},'
        '"carbs":{"value":"X","unit":"g"}}'
    )

    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=150,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text.strip()

    # Extract first JSON object from response
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            merged = {**nutrition, **json.loads(m.group())}
            return merged
        except json.JSONDecodeError:
            pass

    logger.warning("Could not parse nutrition response for «%s»", recipe["title"])
    return nutrition


# ---------------------------------------------------------------------------
# Step 3: nutritional suitability gate
# ---------------------------------------------------------------------------

def is_suitable(recipe: dict, meal_type: str) -> bool:
    """Reject recipes whose caloric density is clearly wrong for the meal type."""
    cal_str = recipe.get("nutrition", {}).get("calories", {}).get("value", "")
    if not cal_str:
        return True  # no data → keep, can't reject

    try:
        cal = float(cal_str)
    except ValueError:
        return True

    if cal == 0:
        return True

    rule = MEAL_RULES[meal_type]
    return rule["cal_min"] <= cal <= rule["cal_max"]


# ---------------------------------------------------------------------------
# Step 4: select balanced set (cuisine diversity)
# ---------------------------------------------------------------------------

def select_balanced(
    pool_by_meal: dict[str, list[dict]],
    target: int = 100,
) -> list[dict]:
    final: list[dict] = []

    for meal_type, pool in pool_by_meal.items():
        # Prefer recipes with complete nutrition
        complete = [r for r in pool if len(r.get("nutrition", {})) >= 4]
        partial  = [r for r in pool if len(r.get("nutrition", {})) < 4]
        ordered  = complete + partial

        # Group by country for round-robin
        by_country: dict[str, list[dict]] = {}
        for r in ordered:
            by_country.setdefault(r.get("country", "?"), []).append(r)

        selected: list[dict] = []
        countries = list(by_country.keys())
        idx = 0
        while len(selected) < target and any(by_country.values()):
            country = countries[idx % len(countries)]
            if by_country.get(country):
                selected.append(by_country[country].pop(0))
            idx += 1

        logger.info(
            "%s: pool=%d complete=%d → selected=%d",
            meal_type, len(pool), len(complete), len(selected),
        )
        final.extend(selected[:target])

    return final


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run(input_path: Path, output_path: Path, target: int = 100) -> None:
    client = _make_client()

    raw_recipes: list[dict] = json.loads(input_path.read_text(encoding="utf-8"))
    logger.info("Loaded %d scraped recipes", len(raw_recipes))

    pool_by_meal: dict[str, list[dict]] = {
        "breakfast": [],
        "lunch":     [],
        "dinner":    [],
    }

    for i, recipe in enumerate(raw_recipes, 1):
        title = recipe.get("title", "?")
        logger.info("[%d/%d] %s", i, len(raw_recipes), title[:60])

        # --- classify ---
        meal_type = recipe.get("meal_type")
        if meal_type not in pool_by_meal:
            meal_type = classify_meal_type(client, recipe)
            recipe["meal_type"] = meal_type

        # --- fill nutrition ---
        recipe["nutrition"] = fill_nutrition(client, recipe)

        # --- update categories ---
        cats = recipe.get("categories", [])
        if meal_type not in cats:
            cats.append(meal_type)
        recipe["categories"] = cats

        # --- suitability gate ---
        if not is_suitable(recipe, meal_type):
            logger.debug("SKIP (caloric mismatch) %s", title[:60])
            continue

        pool_by_meal[meal_type].append(recipe)

    for mt, pool in pool_by_meal.items():
        logger.info("%s pool: %d recipes", mt, len(pool))

    enriched = select_balanced(pool_by_meal, target=target)
    output_path.write_text(
        json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("Saved %d enriched recipes → %s", len(enriched), output_path)


def main():
    parser = argparse.ArgumentParser(description="Nutritionist agent for recipe enrichment")
    base = Path(__file__).parent
    parser.add_argument("--input",  default=str(base / "scraped_recipes.json"))
    parser.add_argument("--output", default=str(base / "enriched_recipes.json"))
    parser.add_argument("--target", type=int, default=100, help="Recipes per meal type")
    args = parser.parse_args()

    run(Path(args.input), Path(args.output), target=args.target)


if __name__ == "__main__":
    main()
