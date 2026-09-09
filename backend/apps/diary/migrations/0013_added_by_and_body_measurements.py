"""MG_HEADKEEPS + MG_BODYSIZE: кто внёс запись и обхваты тела по датам.

Миграция аддитивная: три новых необязательных поля и новая таблица. Пустой
`added_by` у существующих записей читается как «внёс сам владелец» — так оно и
было, переписывать их не нужно.
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("family", "0007_family_invite"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("diary", "0012_entry_grams"),
    ]

    operations = [
        migrations.AddField(
            model_name="diaryentry",
            name="added_by",
            field=models.ForeignKey(
                blank=True,
                help_text="Кто внёс запись, если не сам владелец (MG_HEADKEEPS).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="waterlog",
            name="added_by",
            field=models.ForeignKey(
                blank=True,
                help_text="Кто внёс запись, если не сам владелец (MG_HEADKEEPS).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="weightlog",
            name="added_by",
            field=models.ForeignKey(
                blank=True,
                help_text="Кто внёс запись, если не сам владелец (MG_HEADKEEPS).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.CreateModel(
            name="BodyMeasurement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("neck_cm", models.DecimalField(blank=True, decimal_places=1, max_digits=4, null=True)),
                ("chest_cm", models.DecimalField(blank=True, decimal_places=1, max_digits=4, null=True)),
                ("under_bust_cm", models.DecimalField(blank=True, decimal_places=1, max_digits=4, null=True)),
                ("waist_cm", models.DecimalField(blank=True, decimal_places=1, max_digits=4, null=True)),
                ("hips_cm", models.DecimalField(blank=True, decimal_places=1, max_digits=4, null=True)),
                ("note", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "added_by",
                    models.ForeignKey(
                        blank=True,
                        help_text="Кто внёс запись, если не сам владелец (MG_HEADKEEPS).",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "member",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="body_measurements",
                        to="family.familymember",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="body_measurements",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "body_measurements",
                "ordering": ["-date"],
                "indexes": [
                    models.Index(fields=["user_id", "-date"], name="body_measur_user_id_13108d_idx"),
                    models.Index(fields=["member_id", "-date"], name="body_measur_member__d1e253_idx"),
                ],
                "unique_together": {("user", "date")},
            },
        ),
    ]
