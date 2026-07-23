# Generated manually for game groups and group-owned item instances.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def clear_proven_redundant_item_overrides(apps, schema_editor):
    CharacterItem = apps.get_model("charsheet", "CharacterItem")
    for instance in CharacterItem.objects.select_related(
        "item", "item__weaponstats", "item__armorstats", "item__shieldstats"
    ).iterator():
        item = instance.item
        comparisons = {
            "name_override": item.name,
            "price_override": item.price,
            "weight_override": item.weight,
            "size_class_override": item.size_class,
            "description": item.description or "",
        }
        weapon = getattr(item, "weaponstats", None)
        if weapon is not None:
            comparisons.update({
                "weapon_type_override_id": weapon.weapon_type_id,
                "weapon_min_st_override": weapon.min_st,
                "weapon_maneuver_attribute_override": weapon.maneuver_attribute_mode,
                "weapon_damage_source_override_id": weapon.damage_source_id,
                "weapon_damage_dice_amount_override": weapon.damage_dice_amount,
                "weapon_damage_dice_faces_override": weapon.damage_dice_faces,
                "weapon_damage_flat_bonus_override": weapon.damage_flat_bonus,
                "weapon_damage_flat_operator_override": weapon.damage_flat_operator,
                "weapon_damage_type_override": weapon.damage_type,
                "weapon_wield_mode_override": weapon.wield_mode,
                "weapon_h2_dice_amount_override": weapon.h2_dice_amount,
                "weapon_h2_dice_faces_override": weapon.h2_dice_faces,
                "weapon_h2_flat_bonus_override": weapon.h2_flat_bonus,
                "weapon_h2_flat_operator_override": weapon.h2_flat_operator,
                "weapon_h2_damage_type_override": weapon.h2_damage_type,
            })
        armor = getattr(item, "armorstats", None)
        if armor is not None:
            comparisons.update({
                "armor_rs_head_override": armor.rs_head,
                "armor_rs_torso_override": armor.rs_torso,
                "armor_rs_arm_left_override": armor.rs_arm_left,
                "armor_rs_arm_right_override": armor.rs_arm_right,
                "armor_rs_leg_left_override": armor.rs_leg_left,
                "armor_rs_leg_right_override": armor.rs_leg_right,
                "armor_rs_total_override": armor.rs_total,
                "armor_encumbrance_override": armor.encumbrance,
                "armor_min_st_override": armor.min_st,
            })
        shield = getattr(item, "shieldstats", None)
        if shield is not None:
            comparisons.update({
                "shield_rs_override": shield.rs,
                "shield_encumbrance_override": shield.encumbrance,
                "shield_min_st_override": shield.min_st,
            })
        changes = {}
        for attribute, base_value in comparisons.items():
            current = getattr(instance, attribute)
            if current != base_value:
                continue
            field_name = attribute.removesuffix("_id")
            field = CharacterItem._meta.get_field(field_name)
            changes[attribute] = "" if field.empty_strings_allowed else None
        if changes:
            CharacterItem.objects.filter(pk=instance.pk).update(**changes)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("charsheet", "0253_creaturesourcebinding_choice_label"),
    ]

    operations = [
        migrations.CreateModel(
            name="GameGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("is_archived", models.BooleanField(db_index=True, default=False)),
                (
                    "creator",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_game_groups",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["name", "id"]},
        ),
        migrations.CreateModel(
            name="GameGroupRole",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("leader", "Gruppenleitung"), ("gm", "Spielleiter")], default="gm", max_length=16)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("granted_at", models.DateTimeField(auto_now_add=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                (
                    "group",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="role_assignments", to="charsheet.gamegroup"),
                ),
                (
                    "user",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="game_group_roles", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={"ordering": ["group", "role", "user"]},
        ),
        migrations.CreateModel(
            name="GameGroupInvitation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("pending", "Ausstehend"), ("accepted", "Angenommen"), ("declined", "Abgelehnt"), ("withdrawn", "Zurückgezogen"), ("expired", "Abgelaufen")], default="pending", max_length=16)),
                ("message", models.TextField(blank=True, default="", max_length=1000)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                (
                    "character",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="game_group_invitations", to="charsheet.character"),
                ),
                (
                    "group",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="invitations", to="charsheet.gamegroup"),
                ),
                (
                    "invited_by",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sent_game_group_invitations", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.CreateModel(
            name="GameGroupMembership",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("active", "Aktiv"), ("left", "Verlassen"), ("removed", "Entfernt")], default="active", max_length=16)),
                ("joined_at", models.DateTimeField(auto_now_add=True)),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                (
                    "character",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="game_group_memberships", to="charsheet.character"),
                ),
                (
                    "group",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="memberships", to="charsheet.gamegroup"),
                ),
                (
                    "invitation",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="memberships", to="charsheet.gamegroupinvitation"),
                ),
            ],
            options={"ordering": ["group", "character", "-joined_at"]},
        ),
        migrations.AddConstraint(
            model_name="gamegrouprole",
            constraint=models.UniqueConstraint(fields=("group", "user"), name="uniq_game_group_role_user"),
        ),
        migrations.AddConstraint(
            model_name="gamegrouprole",
            constraint=models.UniqueConstraint(condition=models.Q(("is_active", True), ("role", "leader")), fields=("group",), name="uniq_active_game_group_leader"),
        ),
        migrations.AddConstraint(
            model_name="gamegroupinvitation",
            constraint=models.UniqueConstraint(condition=models.Q(("status", "pending")), fields=("group", "character"), name="uniq_pending_group_character_invite"),
        ),
        migrations.AddConstraint(
            model_name="gamegroupmembership",
            constraint=models.UniqueConstraint(condition=models.Q(("status", "active")), fields=("group", "character"), name="uniq_active_group_character_member"),
        ),
        migrations.AlterField(
            model_name="item",
            name="name",
            field=models.CharField(max_length=200),
        ),
        migrations.AddField(
            model_name="item",
            name="catalog_group",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="catalog_items", to="charsheet.gamegroup"),
        ),
        migrations.AddConstraint(
            model_name="item",
            constraint=models.UniqueConstraint(condition=models.Q(("catalog_group__isnull", True)), fields=("name",), name="uniq_global_item_name"),
        ),
        migrations.AddConstraint(
            model_name="item",
            constraint=models.UniqueConstraint(condition=models.Q(("catalog_group__isnull", False)), fields=("catalog_group", "name"), name="uniq_group_item_name"),
        ),
        migrations.AlterField(
            model_name="characteritem",
            name="owner",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to="charsheet.character"),
        ),
        migrations.AlterField(
            model_name="characteritem",
            name="original_owner_character",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="originally_owned_items", to="charsheet.character"),
        ),
        migrations.AddField(
            model_name="characteritem",
            name="group_owner",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="inventory_items", to="charsheet.gamegroup"),
        ),
        migrations.AddField(
            model_name="characteritem",
            name="original_owner_group",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="originally_owned_items", to="charsheet.gamegroup"),
        ),
        migrations.AddField(
            model_name="characteritem",
            name="group_origin_finalized",
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.AddConstraint(
            model_name="characteritem",
            constraint=models.CheckConstraint(
                condition=models.Q(models.Q(("group_owner__isnull", True), ("owner__isnull", False)), models.Q(("group_owner__isnull", False), ("owner__isnull", True)), _connector="OR"),
                name="character_item_exactly_one_owner",
            ),
        ),
        migrations.AddConstraint(
            model_name="characteritem",
            constraint=models.CheckConstraint(
                condition=models.Q(models.Q(("original_owner_character__isnull", False), ("original_owner_group__isnull", True)), models.Q(("original_owner_character__isnull", True), ("original_owner_group__isnull", False)), _connector="OR"),
                name="character_item_exactly_one_origin",
            ),
        ),
        migrations.AddConstraint(
            model_name="characteritem",
            constraint=models.CheckConstraint(
                condition=models.Q(("group_owner__isnull", True), models.Q(("original_owner_character__isnull", True), ("original_owner_group", models.F("group_owner")), ("owner__isnull", True)), _connector="OR"),
                name="character_item_group_owns_origin",
            ),
        ),
        migrations.AddField(
            model_name="itemtransfer",
            name="sender_group",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="sent_item_transfers", to="charsheet.gamegroup"),
        ),
        migrations.AddField(
            model_name="itemtransfer",
            name="initiated_by_user",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="initiated_group_item_transfers", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="itemownershipevent",
            name="actor_user",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="group_item_ownership_actions", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="itemownershipevent",
            name="original_owner_group",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="item_origin_history", to="charsheet.gamegroup"),
        ),
        migrations.AddField(
            model_name="itemownershipevent",
            name="from_group",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="item_ownership_departures", to="charsheet.gamegroup"),
        ),
        migrations.AddField(
            model_name="itemownershipevent",
            name="to_group",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="item_ownership_arrivals", to="charsheet.gamegroup"),
        ),
        migrations.RunPython(clear_proven_redundant_item_overrides, migrations.RunPython.noop),
    ]
