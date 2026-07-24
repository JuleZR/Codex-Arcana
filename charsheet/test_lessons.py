from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.forms.models import inlineformset_factory
from django.template.loader import render_to_string
from django.urls import reverse

from charsheet.constants import SCHOOL_COMBAT
from charsheet.engine.character_creation_engine import CharacterCreationEngine
from charsheet.learning import process_learning_submission
from charsheet.sheet_context import build_character_sheet_context
from charsheet.lesson_rules import (
    LessonRuleError,
    activate_lesson,
    format_lesson_costs,
    format_lesson_requirements,
    lesson_requirements_met,
    potential_budget_guard,
    resolve_activation_costs,
)
from charsheet.models import (
    Character,
    CharacterCreationDraft,
    CharacterLesson,
    CharacterSchool,
    Lesson,
    LessonCost,
    Race,
    School,
    SchoolType,
    Technique,
)
from charsheet.admin import (
    LessonAdmin,
    LessonAdminForm,
    LessonCostInline,
    LessonCostInlineForm,
    LessonCostInlineFormSet,
)


class LessonRuleTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="lesson-user", password="test12345")
        self.race = Race.objects.create(name="Mensch")
        self.character = Character.objects.create(
            owner=self.user,
            race=self.race,
            name="Rika",
            current_experience=40,
            current_arcane_power=5,
        )
        self.school_type, _created = SchoolType.objects.get_or_create(
            slug=SCHOOL_COMBAT,
            defaults={"name": "Kampfschule"},
        )
        self.school = School.objects.create(name="Klingenorden", type=self.school_type)
        self.other_school = School.objects.create(name="Schattenpfad", type=self.school_type)
        self.technique = Technique.objects.create(name="Schnitt im Wind", school=self.school, level=3)
        self.other_technique = Technique.objects.create(name="Schritt im Schatten", school=self.other_school, level=1)
        CharacterSchool.objects.create(character=self.character, school=self.school, level=3)

    def lesson(self, name="Abbitte erzwingen", slug="abbitte-erzwingen", **kwargs):
        kwargs.setdefault("technique", self.technique)
        return Lesson.objects.create(name=name, slug=slug, school=self.school, **kwargs)

    def test_slug_is_globally_unique(self):
        self.lesson()
        duplicate = Lesson(
            name="Andere Lektion",
            slug="abbitte-erzwingen",
            school=self.other_school,
            technique=self.other_technique,
        )
        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_lesson_requires_combat_school_technique_from_same_school_and_source_reference(self):
        lesson = self.lesson(source_reference="Quellenband, S. 285")
        lesson.full_clean()
        self.assertEqual(lesson.source_reference, "Quellenband, S. 285")

        mismatched = self.lesson(name="Falsche Schule", slug="falsche-schule", technique=self.other_technique)
        with self.assertRaises(ValidationError):
            mismatched.full_clean()

        arcane_type, _created = SchoolType.objects.get_or_create(
            slug="lesson-test-magic-school",
            defaults={"name": "Lektions-Test-Magieschule"},
        )
        arcane_school = School.objects.create(name="Lektions-Test-Zirkel", type=arcane_type)
        arcane_technique = Technique.objects.create(name="Lektions-Test-Schritt", school=arcane_school, level=1)
        non_combat = Lesson(
            name="Nichtkampf-Lektion",
            slug="nichtkampf-lektion",
            school=arcane_school,
            technique=arcane_technique,
        )
        with self.assertRaises(ValidationError):
            non_combat.full_clean()

    def test_custom_cost_requires_label(self):
        lesson = self.lesson()
        cost = LessonCost(
            lesson=lesson,
            cost_type=LessonCost.CostType.CUSTOM,
            value=1,
        )
        with self.assertRaises(ValidationError):
            cost.full_clean()

    def test_alternative_cost_groups_require_at_least_two_entries(self):
        lesson = self.lesson()
        LessonCost.objects.create(
            lesson=lesson,
            cost_type=LessonCost.CostType.LIFE_POINTS,
            value=2,
            operator=LessonCost.Operator.OR,
            alternative_group=1,
        )
        with self.assertRaises(LessonRuleError):
            resolve_activation_costs(lesson, {1: lesson.costs.get().id})

    def test_admin_cost_inline_rejects_deleting_group_down_to_one_entry(self):
        lesson = self.lesson()
        first = LessonCost.objects.create(
            lesson=lesson,
            cost_type=LessonCost.CostType.LIFE_POINTS,
            value=2,
            operator=LessonCost.Operator.OR,
            alternative_group=1,
        )
        second = LessonCost.objects.create(
            lesson=lesson,
            cost_type=LessonCost.CostType.FAME,
            value=1,
            operator=LessonCost.Operator.OR,
            alternative_group=1,
        )
        formset_class = inlineformset_factory(
            Lesson,
            LessonCost,
            form=LessonCostInlineForm,
            formset=LessonCostInlineFormSet,
            fields=("cost_type", "value", "operator", "custom_label", "description", "alternative_group", "sort_order"),
            can_delete=True,
            extra=0,
        )
        prefix = "costs"
        formset = formset_class(
            instance=lesson,
            prefix=prefix,
            data={
                f"{prefix}-TOTAL_FORMS": "2",
                f"{prefix}-INITIAL_FORMS": "2",
                f"{prefix}-MIN_NUM_FORMS": "0",
                f"{prefix}-MAX_NUM_FORMS": "1000",
                f"{prefix}-0-id": str(first.id),
                f"{prefix}-0-lesson": str(lesson.id),
                f"{prefix}-0-cost_type": first.cost_type,
                f"{prefix}-0-value": str(first.value),
                f"{prefix}-0-operator": first.operator,
                f"{prefix}-0-custom_label": "",
                f"{prefix}-0-description": "",
                f"{prefix}-0-alternative_group": "1",
                f"{prefix}-0-sort_order": "0",
                f"{prefix}-1-id": str(second.id),
                f"{prefix}-1-lesson": str(lesson.id),
                f"{prefix}-1-cost_type": second.cost_type,
                f"{prefix}-1-value": str(second.value),
                f"{prefix}-1-operator": second.operator,
                f"{prefix}-1-custom_label": "",
                f"{prefix}-1-description": "",
                f"{prefix}-1-alternative_group": "1",
                f"{prefix}-1-sort_order": "0",
                f"{prefix}-1-DELETE": "on",
            },
        )
        self.assertFalse(formset.is_valid())
        self.assertIn("mindestens zwei Kosten", str(formset.non_form_errors()))

    def test_cost_expression_and_exact_alternative_selection(self):
        lesson = self.lesson()
        LessonCost.objects.create(
            lesson=lesson,
            cost_type=LessonCost.CostType.ARCANE_POWER,
            value=1,
        )
        lp = LessonCost.objects.create(
            lesson=lesson,
            cost_type=LessonCost.CostType.LIFE_POINTS,
            value=2,
            operator=LessonCost.Operator.OR,
            alternative_group=1,
        )
        fame = LessonCost.objects.create(
            lesson=lesson,
            cost_type=LessonCost.CostType.FAME,
            value=1,
            operator=LessonCost.Operator.OR,
            alternative_group=1,
        )
        self.assertEqual(format_lesson_costs(lesson), "1 KP + (2 LP ODER 1 Ruhmpunkt)")
        automatic, manual = resolve_activation_costs(lesson, {1: fame.id})
        self.assertEqual([row.value for row in automatic], [1])
        self.assertEqual([row.id for row in manual], [fame.id])
        with self.assertRaises(LessonRuleError):
            resolve_activation_costs(lesson, {})
        with self.assertRaises(LessonRuleError):
            resolve_activation_costs(lesson, {1: lp.id, 2: fame.id})

    def test_lesson_requirement_is_its_school_technique(self):
        lesson = self.lesson()
        self.assertEqual(format_lesson_requirements(lesson), "Klingenorden III - Schnitt im Wind")
        self.assertTrue(lesson_requirements_met(lesson, character=self.character))
        self.assertTrue(lesson_requirements_met(lesson, learned_technique_ids={self.technique.id}))
        self.assertFalse(lesson_requirements_met(lesson, learned_technique_ids={self.other_technique.id}))
        CharacterSchool.objects.filter(character=self.character, school=self.school).update(level=2)
        self.assertFalse(lesson_requirements_met(lesson, character=self.character))

    def test_admin_cost_inline_carries_and_or_choice(self):
        form = LessonCostInlineForm()
        self.assertIn("operator", form.fields)
        self.assertEqual(form.fields["operator"].choices[0][1], "UND")
        self.assertEqual(form.fields["operator"].choices[1][1], "ODER")

    def test_admin_lesson_uses_direct_school_limited_technique_dropdown_and_only_cost_inline(self):
        lesson = self.lesson()
        form = LessonAdminForm(instance=lesson)
        self.assertNotIn("technique", getattr(LessonAdmin, "autocomplete_fields", ()))
        self.assertEqual(LessonAdmin.inlines, (LessonCostInline,))
        self.assertIn("charsheet/js/lesson_admin_v4.js", str(form.media))
        technique_names = [technique.name for technique in form.fields["technique"].queryset]
        self.assertIn("Schnitt im Wind", technique_names)
        self.assertNotIn("Schritt im Schatten", technique_names)
        technique_labels = [form.fields["technique"].label_from_instance(technique) for technique in form.fields["technique"].queryset]
        self.assertIn("Klingenorden III - Schnitt im Wind", technique_labels)

    def test_admin_lesson_technique_endpoint_filters_by_school_and_labels_level(self):
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save(update_fields=["is_staff", "is_superuser"])
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("admin:charsheet_lesson_techniques"),
            {"school": self.school.id},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        labels = [row["label"] for row in response.json()["results"]]
        self.assertIn("Klingenorden III - Schnitt im Wind", labels)
        self.assertNotIn("Schattenpfad I - Schritt im Schatten", labels)

    def test_activation_deducts_only_kp_and_reports_manual_costs(self):
        lesson = self.lesson()
        LessonCost.objects.create(
            lesson=lesson,
            cost_type=LessonCost.CostType.ARCANE_POWER,
            value=2,
        )
        LessonCost.objects.create(
            lesson=lesson,
            cost_type=LessonCost.CostType.EXPERIENCE,
            value=3,
        )
        CharacterLesson.objects.create(
            character=self.character,
            lesson=lesson,
            acquisition_type=CharacterLesson.AcquisitionType.MANUAL,
        )
        unconfirmed = activate_lesson(self.character, lesson.id)
        self.assertFalse(unconfirmed["ok"])
        self.assertEqual(unconfirmed["error"], "manual_confirmation_required")
        result = activate_lesson(self.character, lesson.id, manual_costs_confirmed=True)
        self.character.refresh_from_db()
        self.assertTrue(result["ok"])
        self.assertEqual(self.character.current_arcane_power, 3)
        self.assertEqual(result["manual_costs"], ["3 EP"])
        self.assertFalse(result["potential_check"]["supported"])
        self.assertTrue(result["potential_check"]["allowed"])

    def test_activation_is_atomic_when_kp_are_insufficient(self):
        lesson = self.lesson()
        LessonCost.objects.create(
            lesson=lesson,
            cost_type=LessonCost.CostType.ARCANE_POWER,
            value=6,
        )
        CharacterLesson.objects.create(character=self.character, lesson=lesson)
        result = activate_lesson(self.character, lesson.id)
        self.character.refresh_from_db()
        self.assertFalse(result["ok"])
        self.assertEqual(self.character.current_arcane_power, 5)

    def test_potential_guard_explicitly_reports_unsupported_state(self):
        result = potential_budget_guard(self.character, 2)
        self.assertEqual(
            result,
            {
                "supported": False,
                "allowed": True,
                "required_kp": 2,
                "remaining_potential": None,
            },
        )

    def test_lessons_add_arcane_power_and_fame_without_mutating_manual_fame(self):
        lesson = self.lesson()
        before_kp = self.character.get_engine(refresh=True).calculate_arcane_power()
        CharacterLesson.objects.create(character=self.character, lesson=lesson)
        engine = self.character.get_engine(refresh=True)
        self.assertEqual(engine.calculate_arcane_power(), before_kp + 1)
        self.assertEqual(engine.auto_lesson_fame_points(), 1)
        self.character.refresh_from_db()
        self.assertEqual(self.character.personal_fame_point, 0)

    def test_creation_phase_four_counts_lesson_cp(self):
        lesson = self.lesson(purchase_cost=9)
        draft = CharacterCreationDraft.objects.create(
            owner=self.user,
            race=self.race,
            current_phase=4,
            state={"phase_4": {"schools": {str(self.school.id): 3}, "lessons": [lesson.id]}},
        )
        engine = CharacterCreationEngine(draft)
        self.assertEqual(engine.phase_4_lessons(), {lesson.id})
        self.assertEqual(engine.sum_phase_4_lesson_cost(), 9)
        self.assertTrue(engine._phase_4_lessons_are_valid())

    def test_learning_and_regular_unlearning_use_recorded_ep(self):
        lesson = self.lesson(purchase_cost=8)
        previous_kp_max = self.character.get_engine(refresh=True).calculate_arcane_power()
        self.character.current_arcane_power = previous_kp_max
        self.character.save(update_fields=["current_arcane_power"])
        level, message = process_learning_submission(
            self.character,
            {f"learn_lesson_add_{lesson.id}": "1"},
        )
        self.assertEqual(level, "success", message)
        self.character.refresh_from_db()
        entry = CharacterLesson.objects.get(character=self.character, lesson=lesson)
        self.assertEqual(entry.paid_ep, 8)
        self.assertIsNotNone(entry.learned_at)
        self.assertEqual(self.character.current_experience, 32)
        self.assertEqual(self.character.current_arcane_power, previous_kp_max + 1)

        lesson.purchase_cost = 12
        lesson.save(update_fields=["purchase_cost"])
        level, message = process_learning_submission(
            self.character,
            {f"learn_lesson_add_{lesson.id}": "-1"},
        )
        self.assertEqual(level, "success", message)
        self.character.refresh_from_db()
        self.assertFalse(CharacterLesson.objects.filter(character=self.character, lesson=lesson).exists())
        self.assertEqual(self.character.current_experience, 40)
        self.assertEqual(self.character.current_arcane_power, previous_kp_max)

    def test_unlearning_one_ep_lesson_refunds_it_once_and_keeps_unrelated_lessons(self):
        first = self.lesson()
        second = self.lesson(name="Zweite Lektion", slug="zweite-lektion")
        CharacterLesson.objects.create(
            character=self.character,
            lesson=first,
            acquisition_type=CharacterLesson.AcquisitionType.EXPERIENCE,
            paid_ep=8,
        )
        CharacterLesson.objects.create(
            character=self.character,
            lesson=second,
            acquisition_type=CharacterLesson.AcquisitionType.EXPERIENCE,
            paid_ep=8,
        )
        level, message = process_learning_submission(
            self.character,
            {f"learn_lesson_add_{first.id}": "-1"},
        )
        self.assertEqual(level, "success", message)
        self.character.refresh_from_db()
        self.assertFalse(CharacterLesson.objects.filter(character=self.character, lesson=first).exists())
        self.assertTrue(CharacterLesson.objects.filter(character=self.character, lesson=second).exists())
        self.assertEqual(self.character.current_experience, 48)

    def test_lowering_school_blocks_if_locked_lesson_would_become_invalid(self):
        lesson = self.lesson()
        CharacterLesson.objects.create(
            character=self.character,
            lesson=lesson,
            acquisition_type=CharacterLesson.AcquisitionType.CREATION,
        )
        level, _message = process_learning_submission(
            self.character,
            {f"learn_school_add_{self.school.id}": "-1"},
        )
        self.assertEqual(level, "error")
        self.character.refresh_from_db()
        self.assertEqual(self.character.learned_lessons.count(), 1)
        self.assertEqual(self.character.current_experience, 40)
        self.assertEqual(CharacterSchool.objects.get(character=self.character, school=self.school).level, 3)

    def test_lowering_a_school_cascades_invalid_ep_lesson(self):
        lesson = self.lesson()
        CharacterLesson.objects.create(
            character=self.character,
            lesson=lesson,
            acquisition_type=CharacterLesson.AcquisitionType.EXPERIENCE,
            paid_ep=8,
        )
        level, message = process_learning_submission(
            self.character,
            {f"learn_school_add_{self.school.id}": "-1"},
        )
        self.assertEqual(level, "success", message)
        self.character.refresh_from_db()
        self.assertFalse(self.character.learned_lessons.exists())
        self.assertEqual(self.character.current_experience, 56)

    def test_activation_route_is_owner_only_and_returns_updated_partials(self):
        lesson = self.lesson()
        LessonCost.objects.create(
            lesson=lesson,
            cost_type=LessonCost.CostType.ARCANE_POWER,
            value=1,
        )
        CharacterLesson.objects.create(character=self.character, lesson=lesson)
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("activate_lesson", args=[self.character.id, lesson.id]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual({row["target"] for row in payload["partials"]}, {"sheetDamagePanel", "sheetLessonPanel"})
        lesson_html = next(row["html"] for row in payload["partials"] if row["target"] == "sheetLessonPanel")
        self.assertIn('id="lessonFilterInput"', lesson_html)
        self.assertIn("data-lesson-card-trigger", lesson_html)
        self.assertIn("lesson_cost_button", lesson_html)
        self.assertIn("data-activate-lesson", lesson_html)
        self.assertNotIn("lesson_activate_hint", lesson_html)

    def test_read_only_lesson_tab_is_searchable_but_not_activatable(self):
        lesson = self.lesson()
        other_lesson = Lesson.objects.create(
            name="Schritt im Schatten",
            slug="schritt-im-schatten",
            school=self.other_school,
            technique=self.other_technique,
        )
        CharacterLesson.objects.create(character=self.character, lesson=lesson)
        CharacterLesson.objects.create(character=self.character, lesson=other_lesson)
        context = build_character_sheet_context(self.character, read_only=True)
        html = render_to_string("charsheet/partials/_sheet_secondary_page.html", context)
        self.assertIn(">Lektionen<", html)
        self.assertIn('id="lessonFilterInput"', html)
        self.assertIn("data-lesson-school-filter", html)
        self.assertNotIn("data-activate-lesson", html)

    def test_learning_menu_only_offers_lessons_with_met_requirements(self):
        available = self.lesson(name="Bereite Lektion", slug="bereite-lektion")
        unavailable = Lesson.objects.create(
            name="Verborgene Lektion",
            slug="verborgene-lektion",
            school=self.other_school,
            technique=self.other_technique,
        )
        context = build_character_sheet_context(self.character)
        lesson_names = [
            row["name"]
            for group in context["learn_lesson_groups"]
            for row in group["rows"]
        ]
        self.assertIn(available.name, lesson_names)
        self.assertNotIn(unavailable.name, lesson_names)

    def test_lesson_tooltip_contains_fluff_quote_block_marker(self):
        lesson = self.lesson(
            fluff_quote="Ich sah es kommen.",
            fluff_quote_speaker="Meisterin Varra",
        )
        CharacterLesson.objects.create(character=self.character, lesson=lesson)
        context = build_character_sheet_context(self.character)
        html = render_to_string("charsheet/partials/_lesson_panel.html", context)
        self.assertIn("[[LESSONQUOTE]]", html)
        self.assertIn("Ich sah es kommen.", html)
        self.assertIn("[[SPEAKER:Meisterin Varra]]", html)
        self.assertNotIn("Erwerb:", html)
        self.assertNotIn("Anwendung:", html)
