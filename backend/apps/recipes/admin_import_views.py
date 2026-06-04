# MG_IMPORT_TOOL_V1 — кастомные views для импорта рецептов через Django Admin
from __future__ import annotations

import json

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path
from django.utils.decorators import method_decorator
from django.views import View


# ── форма загрузки ────────────────────────────────────────────────────────────

class UploadImportForm(forms.Form):
    xlsx_file = forms.FileField(
        label="Excel-шаблон (.xlsx)",
        help_text="Файл по стандартному шаблону (лист Recipes, 32 колонки).",
    )
    use_ai = forms.BooleanField(
        label="Считать КБЖУ через AI (Яндекс GPT)",
        required=False,
        initial=True,
    )


# ── helper: сериализуем preview_data (Decimal → float) ───────────────────────

def _prep_preview(data_list):
    """Конвертирует Decimal/int в float/int для JSON."""
    from decimal import Decimal

    result = []
    for d in data_list:
        row = {}
        for k, v in d.items():
            if isinstance(v, Decimal):
                row[k] = float(v)
            else:
                row[k] = v
        result.append(row)
    return result


# ── view: загрузка + парсинг + превью ────────────────────────────────────────

@method_decorator(staff_member_required, name="dispatch")
class ImportUploadView(View):
    template_name = "admin/recipes/recipe_import_upload.html"

    def get(self, request):
        form = UploadImportForm()
        return render(request, self.template_name, {"form": form, "title": "Импорт рецептов"})

    def post(self, request):
        from .import_helpers import enrich_kbju, parse_row, read_xlsx_rows
        from .models import RecipeImportSession

        form = UploadImportForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "title": "Импорт рецептов"})

        xlsx_file = request.FILES["xlsx_file"]
        use_ai = form.cleaned_data["use_ai"]

        session = RecipeImportSession(
            status=RecipeImportSession.Status.PENDING,
            created_by=request.user if request.user.is_authenticated else None,
        )
        session.uploaded_file = xlsx_file
        session.save()

        try:
            rows = read_xlsx_rows(session.uploaded_file.path)
        except ValueError as exc:
            session.status = RecipeImportSession.Status.ERROR
            session.parse_errors = [str(exc)]
            session.save()
            messages.error(request, f"Ошибка чтения файла: {exc}")
            return redirect(f"../")

        all_errors = []
        prepared = []
        for rec in rows:
            data, errs = parse_row(rec)
            if errs and data is None:
                # пример-строка — пропускаем тихо
                continue
            all_errors.extend(errs)
            if data and not errs:
                prepared.append(data)

        if all_errors:
            session.status = RecipeImportSession.Status.ERROR
            session.parse_errors = all_errors
            session.save()
            messages.error(request, f"Найдены ошибки в файле ({len(all_errors)} шт.).")
            return render(
                request,
                self.template_name,
                {
                    "form": UploadImportForm(),
                    "title": "Импорт рецептов",
                    "parse_errors": all_errors,
                },
            )

        # обогащаем КБЖУ (может занять время из-за AI)
        warns = enrich_kbju(prepared, use_ai=use_ai)

        session.status = RecipeImportSession.Status.PREVIEW
        session.preview_data = _prep_preview(prepared)
        session.warnings = warns
        session.recipes_count = len(prepared)
        session.save()

        return redirect(f"../{session.pk}/preview/")


# ── view: превью ─────────────────────────────────────────────────────────────

@method_decorator(staff_member_required, name="dispatch")
class ImportPreviewView(View):
    template_name = "admin/recipes/recipe_import_preview.html"

    def get(self, request, session_pk):
        from .models import RecipeImportSession

        session = get_object_or_404(RecipeImportSession, pk=session_pk)
        if session.status not in (
            RecipeImportSession.Status.PREVIEW,
            RecipeImportSession.Status.ERROR,
        ):
            messages.warning(request, "Сессия уже обработана или не готова к превью.")
            return redirect("../../")

        return render(
            request,
            self.template_name,
            {
                "session": session,
                "recipes": session.preview_data,
                "warnings": session.warnings,
                "title": f"Превью импорта ({session.recipes_count} рецептов)",
            },
        )

    def post(self, request, session_pk):
        """Пользователь нажал «Подтвердить импорт»."""
        from .import_helpers import enrich_kbju, save_recipes
        from .models import RecipeImportSession

        session = get_object_or_404(RecipeImportSession, pk=session_pk)
        if session.status != RecipeImportSession.Status.PREVIEW:
            messages.error(request, "Сессия не в состоянии PREVIEW.")
            return redirect("../../")

        if request.POST.get("action") == "cancel":
            session.status = RecipeImportSession.Status.ERROR
            session.parse_errors = ["Отменено пользователем"]
            session.save()
            messages.info(request, "Импорт отменён.")
            return redirect("../../")

        # восстанавливаем Decimal из JSON-превью
        from decimal import Decimal

        data_list = []
        for row in session.preview_data:
            d = dict(row)
            for fld in (
                "kcal_per_100g",
                "proteins_per_100g",
                "fats_per_100g",
                "carbs_per_100g",
                "sugars_per_100g",
                "oil_tsp",
            ):
                if d.get(fld) is not None:
                    d[fld] = Decimal(str(d[fld]))
            data_list.append(d)

        try:
            created = save_recipes(data_list)
        except Exception as exc:
            session.status = RecipeImportSession.Status.ERROR
            session.parse_errors = [str(exc)]
            session.save()
            messages.error(request, f"Ошибка при сохранении: {exc}")
            return redirect(f"../{session_pk}/preview/")

        session.status = RecipeImportSession.Status.DONE
        session.imported_count = created
        session.save()
        messages.success(request, f"Импортировано рецептов: {created}")
        return redirect("../../")
