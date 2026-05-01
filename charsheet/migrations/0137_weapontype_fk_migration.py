from django.db import migrations, models
import django.db.models.deletion


DEFAULT_WEAPON_TYPES = [
    ("longsword", "Langschwert"),
    ("two_handed_sword", "Zweihandschwert"),
    ("shortsword", "Kurzschwert"),
    ("curved_sword", "Krummschwert"),
    ("short_curved", "Kurzkrummschwert"),
    ("rapier", "Degen / Rapier"),
    ("dagger", "Dolch"),
    ("axe", "Axt"),
    ("two_handed_axe", "Zweihandaxt"),
    ("hammer", "Hammer"),
    ("two_handed_hammer", "Zweihandhammer"),
    ("mace", "Kolben / Keule"),
    ("flail", "Flegel / Geissel"),
    ("spear", "Speer"),
    ("lance", "Lanze"),
    ("polearm", "Stangenwaffe"),
    ("staff", "Stab"),
    ("chain", "Kettenwaffe"),
    ("whip", "Peitsche"),
    ("fist", "Faustwaffe / Unbewaffnet"),
    ("bow", "Bogen"),
    ("crossbow", "Armbrust"),
    ("blowgun", "Blasrohr"),
    ("trap", "Netz / Falle"),
    ("special", "Sonderwaffe"),
]


def infer_weapon_type(name: str) -> str:
    normalized = (name or "").strip().lower()
    if not normalized:
        return ""
    if (
        "zweihander" in normalized
        or "zweihandschwert" in normalized
        or "zweihandkhopesh" in normalized
        or "zweihandkrummschwert" in normalized
        or "claymore" in normalized
    ):
        return "two_handed_sword"
    if "kurzschwert" in normalized:
        return "shortsword"
    if "khopesh" in normalized or "krummschwert" in normalized or "sabel" in normalized or "sidarr sing" in normalized:
        return "curved_sword"
    if "langschwert" in normalized or "breitschwert" in normalized or "bastardschwert" in normalized:
        return "longsword"
    if "schwert" in normalized or "sing" in normalized:
        return "longsword"
    if "rapier" in normalized or "degen" in normalized or "florett" in normalized:
        return "rapier"
    if any(token in normalized for token in ("dolch", "messer", "stilett", "main gauche", "khatar")):
        return "dagger"
    if "zweihandstreitaxt" in normalized or "trollzweihandaxt" in normalized:
        return "two_handed_axe"
    if "axt" in normalized or "beil" in normalized:
        return "axe"
    if "zweihandkriegshammer" in normalized or "zweihandtrollkriegshammer" in normalized:
        return "two_handed_hammer"
    if "kriegshammer" in normalized or "hammer" in normalized:
        return "hammer"
    if "zweihandflegel" in normalized or "geissel" in normalized:
        return "flail"
    if any(token in normalized for token in ("streitkolben", "keule", "knuppel", "totschlager", "morgenstern")):
        return "mace"
    if "turnierlanze" in normalized or "lanze" in normalized:
        return "lance"
    if "dreizack" in normalized or "speer" in normalized or "wurfspiess" in normalized or "wurfspie" in normalized:
        return "spear"
    if any(token in normalized for token in ("hellebarde", "glefe", "pike", "berdyche", "kriegsgabel", "gaffel", "haken", "stangenaxt", "sense")):
        return "polearm"
    if "sichel" in normalized:
        return "curved_sword"
    if "kampfstab" in normalized:
        return "staff"
    if "kette" in normalized or "mornabat" in normalized:
        return "chain"
    if "peitsche" in normalized or "lasso" in normalized:
        return "whip"
    if any(token in normalized for token in ("faust", "tritt", "cestus", "handschuh", "panzerschuh")):
        return "fist"
    if "armbrust" in normalized:
        return "crossbow"
    if "bogen" in normalized:
        return "bow"
    if "blasrohr" in normalized:
        return "blowgun"
    if any(token in normalized for token in ("netz", "fussangeln", "fangeisen", "spikes")):
        return "trap"
    return "special"


def _fallback_weapon_type_name(slug: str) -> str:
    return str(slug or "").replace("_", " ").strip().title() or "Unbekannt"


def seed_weapon_types(apps, schema_editor):
    WeaponType = apps.get_model("charsheet", "WeaponType")
    for index, (slug, name) in enumerate(DEFAULT_WEAPON_TYPES, start=1):
        WeaponType.objects.update_or_create(
            slug=slug,
            defaults={"name": name, "sort_order": index},
        )


def migrate_weapon_type_data(apps, schema_editor):
    WeaponType = apps.get_model("charsheet", "WeaponType")
    WeaponStats = apps.get_model("charsheet", "WeaponStats")
    CharacterWeaponMastery = apps.get_model("charsheet", "CharacterWeaponMastery")
    CharacterItem = apps.get_model("charsheet", "CharacterItem")

    by_slug = {entry.slug: entry for entry in WeaponType.objects.all()}

    def ensure_weapon_type(slug: str):
        slug = str(slug or "").strip().lower()
        if not slug:
            return None
        if slug not in by_slug:
            by_slug[slug] = WeaponType.objects.create(
                slug=slug,
                name=_fallback_weapon_type_name(slug),
                sort_order=len(by_slug) + 1,
            )
        return by_slug[slug]

    for stats in WeaponStats.objects.select_related("item").all():
        slug = str(getattr(stats, "weapon_type", "") or "").strip().lower()
        if not slug:
            slug = infer_weapon_type(getattr(getattr(stats, "item", None), "name", ""))
        stats.weapon_type_fk = ensure_weapon_type(slug)
        stats.save(update_fields=["weapon_type_fk"])

    for mastery in CharacterWeaponMastery.objects.select_related("weapon_item__weaponstats", "weapon_item").all():
        slug = str(getattr(mastery, "weapon_type", "") or "").strip().lower()
        weapon_item = getattr(mastery, "weapon_item", None)
        weapon_stats = getattr(weapon_item, "weaponstats", None) if weapon_item is not None else None
        if not slug and weapon_stats is not None:
            slug = str(getattr(weapon_stats, "weapon_type", "") or "").strip().lower()
        if not slug and weapon_item is not None:
            slug = infer_weapon_type(getattr(weapon_item, "name", ""))
        mastery.weapon_type_fk = ensure_weapon_type(slug)
        mastery.save(update_fields=["weapon_type_fk"])

    for character_item in CharacterItem.objects.all():
        slug = str(getattr(character_item, "weapon_type_override", "") or "").strip().lower()
        character_item.weapon_type_override_fk = ensure_weapon_type(slug)
        character_item.save(update_fields=["weapon_type_override_fk"])


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0136_characteritem_weapon_type_override_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="WeaponType",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(max_length=50, unique=True)),
                ("name", models.CharField(max_length=100, unique=True)),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
            ],
            options={"ordering": ["sort_order", "name"]},
        ),
        migrations.RunPython(seed_weapon_types, migrations.RunPython.noop),
        migrations.AddField(
            model_name="characteritem",
            name="weapon_type_override_fk",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="character_item_overrides", to="charsheet.weapontype"),
        ),
        migrations.AddField(
            model_name="characterweaponmastery",
            name="weapon_type_fk",
            field=models.ForeignKey(blank=True, help_text="Der regeltechnische Waffentyp, auf den diese Meisterschaft wirkt.", null=True, on_delete=django.db.models.deletion.PROTECT, related_name="character_masteries", to="charsheet.weapontype"),
        ),
        migrations.AddField(
            model_name="weaponstats",
            name="weapon_type_fk",
            field=models.ForeignKey(blank=True, help_text="Regeltechnischer Waffentyp fuer Waffenmeister und aehnliche Effekte.", null=True, on_delete=django.db.models.deletion.PROTECT, related_name="weapon_stats", to="charsheet.weapontype"),
        ),
        migrations.RunPython(migrate_weapon_type_data, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="characterweaponmastery",
            name="uniq_character_weapon_mastery_weapon_type",
        ),
        migrations.RemoveField(model_name="characteritem", name="weapon_type_override"),
        migrations.RemoveField(model_name="characterweaponmastery", name="weapon_type"),
        migrations.RemoveField(model_name="weaponstats", name="weapon_type"),
        migrations.RenameField(model_name="characteritem", old_name="weapon_type_override_fk", new_name="weapon_type_override"),
        migrations.RenameField(model_name="characterweaponmastery", old_name="weapon_type_fk", new_name="weapon_type"),
        migrations.RenameField(model_name="weaponstats", old_name="weapon_type_fk", new_name="weapon_type"),
        migrations.AddConstraint(
            model_name="characterweaponmastery",
            constraint=models.UniqueConstraint(fields=("character", "school", "weapon_type"), name="uniq_character_weapon_mastery_weapon_type"),
        ),
    ]
