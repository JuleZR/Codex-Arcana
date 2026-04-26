from django.db import migrations, models
import django.db.models.deletion
from django.utils.text import slugify


def populate_rune_slugs(apps, schema_editor):
    Rune = apps.get_model("charsheet", "Rune")
    used_slugs = set()
    for rune in Rune.objects.order_by("id"):
        base_slug = (slugify(rune.name) or f"rune-{rune.pk}")[:110]
        slug = base_slug
        suffix = 2
        while slug in used_slugs or Rune.objects.exclude(pk=rune.pk).filter(slug=slug).exists():
            slug = f"{base_slug}-{suffix}"
            suffix += 1
        rune.slug = slug
        rune.save(update_fields=["slug"])
        used_slugs.add(slug)


def migrate_character_item_runes(apps, schema_editor):
    CharacterItem = apps.get_model("charsheet", "CharacterItem")
    ItemRune = apps.get_model("charsheet", "ItemRune")

    for character_item in CharacterItem.objects.prefetch_related("item__runes", "runes").iterator():
        rune_ids = []
        rune_ids.extend(character_item.item.runes.values_list("id", flat=True))
        rune_ids.extend(character_item.runes.values_list("id", flat=True))
        for rune_id in dict.fromkeys(rune_ids):
            if ItemRune.objects.filter(item_id=character_item.id, rune_id=rune_id).exists():
                continue
            ItemRune.objects.create(
                item_id=character_item.id,
                rune_id=rune_id,
                crafter_level=0,
                allows_duplicate=False,
                is_active=True,
            )


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0126_modifier_attribute_target_kind"),
    ]

    operations = [
        migrations.AddField(
            model_name="rune",
            name="slug",
            field=models.SlugField(blank=True, max_length=120, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="rune",
            name="allowed_item_types",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Leere Liste bedeutet: alle Item-Typen erlaubt.",
            ),
        ),
        migrations.AddField(
            model_name="rune",
            name="is_level_scaled",
            field=models.BooleanField(
                default=False,
                help_text="Wenn aktiv, skaliert der Effekt mit dem gespeicherten Waffenmeister-Level der ItemRune.",
            ),
        ),
        migrations.AlterField(
            model_name="modifier",
            name="scale_source",
            field=models.CharField(
                blank=True,
                choices=[
                    ("school_level", "School level"),
                    ("fame_total", "Fame total"),
                    ("trait_level", "Trait Level"),
                    ("skill_level", "Skill level"),
                    ("skill_total", "Skill total"),
                    ("rune_crafter_level", "Rune crafter level"),
                ],
                max_length=30,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="modifier",
            name="cap_source",
            field=models.CharField(
                blank=True,
                choices=[
                    ("school_level", "School level"),
                    ("fame_total", "Fame total"),
                    ("trait_level", "Trait Level"),
                    ("skill_level", "Skill level"),
                    ("skill_total", "Skill total"),
                    ("rune_crafter_level", "Rune crafter level"),
                ],
                max_length=30,
                null=True,
            ),
        ),
        migrations.CreateModel(
            name="ItemRune",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "crafter_level",
                    models.PositiveSmallIntegerField(
                        default=0,
                        help_text="Waffenmeister-Stufe beim Anbringen oder Verbessern dieser Rune.",
                    ),
                ),
                ("allows_duplicate", models.BooleanField(default=False, editable=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="item_runes",
                        to="charsheet.characteritem",
                    ),
                ),
                (
                    "rune",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="item_assignments",
                        to="charsheet.rune",
                    ),
                ),
            ],
            options={
                "ordering": ["item", "rune__name", "id"],
            },
        ),
        migrations.RunPython(populate_rune_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="rune",
            name="slug",
            field=models.SlugField(max_length=120, unique=True),
        ),
        migrations.RunPython(migrate_character_item_runes, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="itemrune",
            constraint=models.UniqueConstraint(
                condition=models.Q(allows_duplicate=False),
                fields=("item", "rune"),
                name="unique_non_duplicate_rune_per_item",
            ),
        ),
    ]
