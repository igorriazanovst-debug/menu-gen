"""Admin forms & widgets for Recipe editing (RA-001).

Pure-Django implementation, no extra pip packages.
- ingredients / steps  -> dynamic table widgets (JSON list[dict])
- allergens / suitable_for / categories -> multi-select checkbox widgets (JSON list[str])
All labels / help texts are wrapped in gettext_lazy for RU/EN switching.
"""

import json

from django import forms
from django.utils.html import escape as _html_escape
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from .models import Cuisine, Recipe

# ── Allowed values for the multi-select JSON fields ──────────────────────────
# (value, human label). Labels are translatable.
ALLERGEN_CHOICES = [
    ("eggs", _("Eggs")),
    ("milk", _("Milk")),
    ("gluten", _("Gluten")),
    ("fish", _("Fish")),
    ("shellfish", _("Shellfish")),
    ("nuts", _("Tree nuts")),
    ("peanuts", _("Peanuts")),
    ("soy", _("Soy")),
    ("sesame", _("Sesame")),
]

SUITABLE_FOR_CHOICES = [
    ("breakfast", _("Breakfast")),
    ("lunch", _("Lunch")),
    ("dinner", _("Dinner")),
    ("snack", _("Snack")),
]

# categories: per decision, allowed values = DishType
CATEGORY_CHOICES = list(Recipe.DishType.choices)


# ── Widgets ──────────────────────────────────────────────────────────────────
class _JSONListMultiCheckbox(forms.Widget):
    """Renders a JSON list[str] as a group of checkboxes from a fixed choice set.

    Unknown values already stored in DB are preserved and shown as checked
    extra checkboxes so the admin never silently drops data.
    """

    template_checkbox = (
        '<label style="display:inline-block;margin:2px 14px 2px 0;white-space:nowrap;">'
        '<input type="checkbox" name="{name}" value="{value}"{checked}> {label}</label>'
    )

    def __init__(self, choices=(), attrs=None):
        super().__init__(attrs)
        self.choices = list(choices)

    def value_from_datadict(self, data, files, name):
        if hasattr(data, "getlist"):
            return data.getlist(name)
        return data.get(name, [])

    def format_value(self, value):
        if value is None:
            return []
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (ValueError, TypeError):
                value = [value]
        return [str(v) for v in value] if isinstance(value, (list, tuple)) else [str(value)]

    def render(self, name, value, attrs=None, renderer=None):
        selected = set(self.format_value(value))
        known = {str(v) for v, _label in self.choices}
        rows = []
        for val, label in self.choices:
            checked = " checked" if str(val) in selected else ""
            rows.append(self.template_checkbox.format(name=name, value=val, label=label, checked=checked))
        # preserve unknown legacy values
        for extra in sorted(selected - known):
            if not extra:
                continue
            rows.append(
                self.template_checkbox.format(
                    name=name,
                    value=extra,
                    label="%s (%s)" % (extra, _("legacy")),
                    checked=" checked",
                )
            )
        return mark_safe('<div class="mg-multicheck" style="max-width:760px;">%s</div>' % "".join(rows))


class _IngredientsWidget(forms.Widget):
    """Editable table for ingredients: name | quantity | unit | grams.

    Stores list[dict] with keys: name, quantity, unit, grams.
    """

    def value_from_datadict(self, data, files, name):
        getlist = data.getlist if hasattr(data, "getlist") else (lambda k: data.get(k, []))
        names = getlist("%s_name" % name)
        qtys = getlist("%s_quantity" % name)
        units = getlist("%s_unit" % name)
        grams = getlist("%s_grams" % name)
        out = []
        for i, nm in enumerate(names):
            nm = (nm or "").strip()
            if not nm:
                continue
            g_raw = grams[i] if i < len(grams) else ""
            try:
                g_val = float(g_raw) if str(g_raw).strip() != "" else 0
            except (ValueError, TypeError):
                g_val = 0
            out.append(
                {
                    "name": nm,
                    "quantity": (qtys[i] if i < len(qtys) else "").strip(),
                    "unit": (units[i] if i < len(units) else "").strip(),
                    "grams": g_val,
                }
            )
        return out

    def format_value(self, value):
        if value is None:
            return []
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (ValueError, TypeError):
                value = []
        return value if isinstance(value, list) else []

    def render(self, name, value, attrs=None, renderer=None):
        items = self.format_value(value)
        h_name = str(_("Name"))
        h_qty = str(_("Quantity"))
        h_unit = str(_("Unit"))
        h_grams = str(_("Grams"))
        h_del = str(_("Delete"))
        h_add = str(_("Add ingredient"))
        rows = []
        for it in items:
            rows.append(
                self._row(
                    name, it.get("name", ""), it.get("quantity", ""), it.get("unit", ""), it.get("grams", ""), h_del
                )
            )  # noqa: E127
        empty_row = self._row(name, "", "", "", "", h_del)
        return mark_safe(
            """
<div class="mg-ing" data-name="{name}">
  <table class="mg-ing-table" style="border-collapse:collapse;width:100%;max-width:820px;">
    <thead><tr style="text-align:left;">
      <th style="padding:4px;">{h_name}</th>
      <th style="padding:4px;width:90px;">{h_qty}</th>
      <th style="padding:4px;width:90px;">{h_unit}</th>
      <th style="padding:4px;width:90px;">{h_grams}</th>
      <th style="padding:4px;width:60px;"></th>
    </tr></thead>
    <tbody class="mg-ing-body">{rows}</tbody>
  </table>
  <template class="mg-ing-tpl">{empty}</template>
  <button type="button" class="mg-ing-add" style="margin-top:6px;">+ {h_add}</button>
</div>
<script>(function(){{
  var root=document.currentScript.previousElementSibling;
  function bindDel(scope){{scope.querySelectorAll('.mg-ing-del').forEach(function(b){{
    if(b.dataset.b)return;b.dataset.b=1;b.addEventListener('click',function(){{b.closest('tr').remove();}});}});}}
  var body=root.querySelector('.mg-ing-body');var tpl=root.querySelector('.mg-ing-tpl');
  root.querySelector('.mg-ing-add').addEventListener('click',function(){{
    var tr=document.createElement('tr');tr.innerHTML=tpl.innerHTML;body.appendChild(tr);bindDel(tr);}});
  bindDel(root);
}})();</script>
""".format(
                name=name,
                h_name=h_name,
                h_qty=h_qty,
                h_unit=h_unit,
                h_grams=h_grams,
                h_add=h_add,
                rows="".join(rows),
                empty=empty_row,
            )
        )

    @staticmethod
    def _row(name, nm, qty, unit, grams, h_del):
        def esc(v):
            return _html_escape("" if v is None else str(v))

        return (
            "<tr>"
            '<td style="padding:2px;"><input type="text" name="{n}_name" value="{nm}" style="width:100%;"></td>'
            '<td style="padding:2px;"><input type="text" name="{n}_quantity" value="{q}" style="width:100%;"></td>'
            '<td style="padding:2px;"><input type="text" name="{n}_unit" value="{u}" style="width:100%;"></td>'
            '<td style="padding:2px;"><input type="text" name="{n}_grams" value="{g}" style="width:100%;"></td>'
            '<td style="padding:2px;text-align:center;">'
            '<button type="button" class="mg-ing-del" title="{d}">✕</button></td>'
            "</tr>"
        ).format(n=name, nm=esc(nm), q=esc(qty), u=esc(unit), g=esc(grams), d=h_del)


class _StepsWidget(forms.Widget):
    """Editable ordered list of steps. Stores list[dict] {text, order}."""

    def value_from_datadict(self, data, files, name):
        getlist = data.getlist if hasattr(data, "getlist") else (lambda k: data.get(k, []))
        texts = getlist("%s_text" % name)
        out = []
        order = 1
        for t in texts:
            t = (t or "").strip()
            if not t:
                continue
            out.append({"text": t, "order": order})
            order += 1
        return out

    def format_value(self, value):
        if value is None:
            return []
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (ValueError, TypeError):
                value = []
        return value if isinstance(value, list) else []

    def render(self, name, value, attrs=None, renderer=None):
        items = sorted(self.format_value(value), key=lambda x: x.get("order", 0))
        h_step = str(_("Step"))
        h_del = str(_("Delete"))
        h_add = str(_("Add step"))
        rows = []
        for it in items:
            rows.append(self._row(name, it.get("text", ""), h_del))
        empty_row = self._row(name, "", h_del)
        return mark_safe(
            """
<div class="mg-steps" data-name="{name}">
  <ol class="mg-steps-body" style="padding-left:20px;max-width:820px;">{rows}</ol>
  <template class="mg-steps-tpl">{empty}</template>
  <button type="button" class="mg-steps-add" style="margin-top:6px;">+ {h_add}</button>
  <span style="margin-left:8px;color:#888;font-size:11px;">{h_step}</span>
</div>
<script>(function(){{
  var root=document.currentScript.previousElementSibling;
  function bindDel(scope){{scope.querySelectorAll('.mg-step-del').forEach(function(b){{
    if(b.dataset.b)return;b.dataset.b=1;b.addEventListener('click',function(){{b.closest('li').remove();}});}});}}
  var body=root.querySelector('.mg-steps-body');var tpl=root.querySelector('.mg-steps-tpl');
  root.querySelector('.mg-steps-add').addEventListener('click',function(){{
    var li=document.createElement('li');li.innerHTML=tpl.innerHTML;body.appendChild(li);bindDel(li);}});
  bindDel(root);
}})();</script>
""".format(
                name=name, h_add=h_add, h_step=h_step, rows="".join(rows), empty=empty_row
            )
        )

    @staticmethod
    def _row(name, text, h_del):
        esc = _html_escape("" if text is None else str(text))
        return (
            '<li style="margin:3px 0;">'
            '<textarea name="{n}_text" rows="2" style="width:90%;vertical-align:middle;">{t}</textarea>'
            ' <button type="button" class="mg-step-del" title="{d}">✕</button>'
            "</li>"
        ).format(n=name, t=esc, d=h_del)


# ── Form fields wrapping the widgets ─────────────────────────────────────────
class _PassthroughField(forms.Field):
    """Field whose widget already returns the final Python value (list)."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("required", False)
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        return value if value is not None else []

    def has_changed(self, initial, data):
        return json.dumps(initial or [], sort_keys=True, ensure_ascii=False) != json.dumps(
            data or [], sort_keys=True, ensure_ascii=False
        )


# ── PHOTO_UPLOAD_ADMIN: URL input + local-file upload button ─────────────────
class _MediaUploadWidget(forms.TextInput):
    """Text input for a media URL plus a button to upload a local file.

    The file is POSTed to the same API endpoint the web client uses
    (`/api/v1/recipes/upload-media/`); the returned absolute URL is written
    back into the text input. No host/url is hardcoded — the path is relative
    and resolved against the current origin in the browser.
    """

    class Media:
        pass

    def __init__(self, media_type="image", attrs=None):
        self.media_type = media_type
        super().__init__(attrs)

    def render(self, name, value, attrs=None, renderer=None):
        base = super().render(name, value, attrs=attrs, renderer=renderer)
        accept = "image/*" if self.media_type == "image" else "video/mp4,video/webm,video/quicktime"
        hint = (
            str(_("JPEG/PNG/WebP/GIF — up to 10 MB"))
            if self.media_type == "image"
            else str(_("MP4/WebM/MOV — up to 200 MB"))
        )
        btn = str(_("Upload file"))
        uploading = str(_("Uploading…"))
        err = str(_("Upload failed"))
        html = (
            '<div class="mg-media-upload" style="margin-top:6px;">'
            "{base}"
            '<div style="margin-top:6px;">'
            '<button type="button" class="mg-media-btn" '
            'style="padding:4px 10px;">{btn}</button>'
            '<input type="file" class="mg-media-file" accept="{accept}" style="display:none;">'
            '<span class="mg-media-status" style="margin-left:10px;color:#888;font-size:11px;">{hint}</span>'
            "</div>"
            "</div>"
            "<script>(function(){{"
            "var root=document.currentScript.previousElementSibling;"
            "var input=root.querySelector(\"input[name='{name}']\")"
            '||root.querySelector("input[type=text],input:not([type])");'
            'var btn=root.querySelector(".mg-media-btn");'
            'var file=root.querySelector(".mg-media-file");'
            'var status=root.querySelector(".mg-media-status");'
            'function csrf(){{var m=document.cookie.match(/csrftoken=([^;]+)/);return m?m[1]:"";}}'
            'btn.addEventListener("click",function(){{file.click();}});'
            'file.addEventListener("change",function(){{'
            "var f=file.files&&file.files[0];if(!f)return;"
            'status.textContent="{uploading}";'
            'var fd=new FormData();fd.append("file",f);fd.append("media_type","{mtype}");'
            'fetch("/api/v1/recipes/upload-media/",{{method:"POST",body:fd,'
            'headers:{{"X-CSRFToken":csrf()}},credentials:"same-origin"}})'
            ".then(function(r){{if(!r.ok)throw new Error(r.status);return r.json();}})"
            '.then(function(d){{if(input&&d&&d.url){{input.value=d.url;}}status.textContent=d&&d.url?d.url:"{err}";}})'
            '.catch(function(e){{status.textContent="{err}: "+e;}})'
            '.finally(function(){{file.value="";}});'
            "}});"
            "}})();</script>"
        ).format(
            base=base,
            btn=btn,
            accept=accept,
            hint=hint,
            name=name,
            uploading=uploading,
            mtype=self.media_type,
            err=err,
        )
        return mark_safe(html)


# ── /PHOTO_UPLOAD_ADMIN ──────────────────────────────────────────────────────




class _CuisineSelectWidget(forms.Select):
    """<select> populated live from Cuisine table (active only, sorted)."""

    def __init__(self, attrs=None):
        super().__init__(attrs)

    def _get_choices(self):
        try:
            qs = Cuisine.objects.filter(is_active=True).order_by("sort_order", "name")
            opts = [("", "---------")] + [(c.name, c.name) for c in qs]
        except Exception:
            opts = [("", "---------")]
        return opts

    def render(self, name, value, attrs=None, renderer=None):
        self.choices = self._get_choices()
        return super().render(name, value, attrs=attrs, renderer=renderer)

    def value_from_datadict(self, data, files, name):
        return data.get(name, "")

# ── The admin form ────────────────────────────────────────────────────────────
class RecipeAdminForm(forms.ModelForm):
    ingredients = _PassthroughField(widget=_IngredientsWidget(), label=_("Ingredients"))
    steps = _PassthroughField(widget=_StepsWidget(), label=_("Steps"))
    allergens = _PassthroughField(widget=_JSONListMultiCheckbox(choices=ALLERGEN_CHOICES), label=_("Allergens"))
    suitable_for = _PassthroughField(
        widget=_JSONListMultiCheckbox(choices=SUITABLE_FOR_CHOICES), label=_("Suitable for (meal)")
    )
    categories = _PassthroughField(widget=_JSONListMultiCheckbox(choices=CATEGORY_CHOICES), label=_("Categories"))
    country = forms.CharField(
        required=False,
        widget=_CuisineSelectWidget(),
        label=_("Country / cuisine"),
    )

    image_url = forms.URLField(
        required=False,
        widget=_MediaUploadWidget(media_type="image"),
        label=_("Image URL"),
    )
    video_url = forms.URLField(
        required=False,
        widget=_MediaUploadWidget(media_type="video"),
        label=_("Video URL"),
    )

    class Meta:
        model = Recipe
        fields = "__all__"


# MG_RA002b_country_select_list
class RecipeChangelistForm(forms.ModelForm):
    """Form used by RecipeAdmin.get_changelist_form() for list_editable.

    Overrides the country widget to a <select> from the Cuisine table.
    dish_type and source already have model-level choices so Django renders
    them as <select> automatically; only country needs the override.
    """

    country = forms.CharField(
        required=False,
        widget=_CuisineSelectWidget(),
        label=_("Country / cuisine"),
    )

    class Meta:
        model = Recipe
        fields = ("title", "dish_type", "country", "source")

