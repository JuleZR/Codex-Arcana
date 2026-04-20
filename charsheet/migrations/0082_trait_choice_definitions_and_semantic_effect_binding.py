from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("charsheet", "0081_traitsemanticeffect"),
    ]

    operations = [
        migrations.CreateModel(
            name="TraitChoiceDefinition",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(help_text="Readable label that identifies this trait choice in rulebook terms.", max_length=120)),
                ("target_kind", models.CharField(choices=[("attribute", "Attribute"), ("skill", "Skill"), ("skill_category", "Skill Category"), ("item", "Item"), ("item_category", "Item Category"), ("specialization", "Specialization"), ("text", "Free Text"), ("entity", "Other Entity")], help_text="What kind of thing must be selected for this trait decision.", max_length=20)),
                ("description", models.TextField(blank=True, default="", help_text="Short rulebook prompt that explains what exactly must be chosen.")),
                ("min_choices", models.PositiveSmallIntegerField(default=1, help_text="Minimum number of stored selections required for this trait decision.", validators=[django.core.validators.MinValueValidator(0)])),
                ("max_choices", models.PositiveSmallIntegerField(default=1, help_text="Maximum number of stored selections allowed for this trait decision.", validators=[django.core.validators.MinValueValidator(1)])),
                ("is_required", models.BooleanField(default=True, help_text="If enabled, the trait stays incomplete until this decision reaches min_choices.")),
                ("allowed_skill_family", models.SlugField(blank=True, default="", max_length=50)),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("allowed_attribute", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="trait_choice_definitions", to="charsheet.attribute")),
                ("allowed_skill_category", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="trait_choice_definitions", to="charsheet.skillcategory")),
                ("trait", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="choice_definitions", to="charsheet.trait")),
            ],
            options={
                "ordering": ["trait__trait_type", "trait__name", "sort_order", "name", "id"],
            },
        ),
        migrations.CreateModel(
            name="CharacterTraitChoice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("selected_item_category", models.CharField(blank=True, default="", max_length=30)),
                ("selected_text", models.CharField(blank=True, default="", max_length=255)),
                ("selected_object_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("character_trait", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="choices", to="charsheet.charactertrait")),
                ("definition", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="character_choices", to="charsheet.traitchoicedefinition")),
                ("selected_attribute", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="character_trait_choices", to="charsheet.attribute")),
                ("selected_content_type", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="character_trait_choice_targets", to="contenttypes.contenttype")),
                ("selected_item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="character_trait_choices", to="charsheet.item")),
                ("selected_skill", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="character_trait_choices", to="charsheet.skill")),
                ("selected_skill_category", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="character_trait_choices", to="charsheet.skillcategory")),
                ("selected_specialization", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="character_trait_choices", to="charsheet.specialization")),
            ],
            options={
                "ordering": ["character_trait__owner__name", "character_trait__trait__name", "definition__sort_order", "id"],
            },
        ),
        migrations.AlterField(
            model_name="traitsemanticeffect",
            name="target_key",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="traitsemanticeffect",
            name="target_choice_definition",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="semantic_effects", to="charsheet.traitchoicedefinition"),
        ),
        migrations.AddConstraint(
            model_name="charactertraitchoice",
            constraint=models.UniqueConstraint(condition=models.Q(("selected_attribute__isnull", False)), fields=("character_trait", "definition", "selected_attribute"), name="uniq_character_trait_choice_selected_attribute"),
        ),
        migrations.AddConstraint(
            model_name="charactertraitchoice",
            constraint=models.UniqueConstraint(condition=models.Q(("selected_skill__isnull", False)), fields=("character_trait", "definition", "selected_skill"), name="uniq_character_trait_choice_selected_skill"),
        ),
        migrations.AddConstraint(
            model_name="charactertraitchoice",
            constraint=models.UniqueConstraint(condition=models.Q(("selected_skill_category__isnull", False)), fields=("character_trait", "definition", "selected_skill_category"), name="uniq_character_trait_choice_selected_category"),
        ),
        migrations.AddConstraint(
            model_name="charactertraitchoice",
            constraint=models.UniqueConstraint(condition=models.Q(("selected_item__isnull", False)), fields=("character_trait", "definition", "selected_item"), name="uniq_character_trait_choice_selected_item"),
        ),
        migrations.AddConstraint(
            model_name="charactertraitchoice",
            constraint=models.UniqueConstraint(condition=models.Q(("selected_specialization__isnull", False)), fields=("character_trait", "definition", "selected_specialization"), name="uniq_character_trait_choice_selected_specialization"),
        ),
        migrations.AddConstraint(
            model_name="charactertraitchoice",
            constraint=models.UniqueConstraint(condition=~models.Q(("selected_item_category", "")), fields=("character_trait", "definition", "selected_item_category"), name="uniq_character_trait_choice_selected_item_category"),
        ),
        migrations.AddConstraint(
            model_name="charactertraitchoice",
            constraint=models.UniqueConstraint(condition=models.Q(("selected_object_id__isnull", False)), fields=("character_trait", "definition", "selected_content_type", "selected_object_id"), name="uniq_character_trait_choice_selected_entity"),
        ),
    ]
