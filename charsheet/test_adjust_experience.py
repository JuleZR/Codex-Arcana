from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from charsheet.models import Character, Race


class AdjustExperienceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="ep-tester", password="secret")
        self.race = Race.objects.create(name="Mensch")
        self.character = Character.objects.create(
            owner=self.user,
            race=self.race,
            name="Arin",
            overall_experience=100,
            current_experience=40,
        )
        self.client.force_login(self.user)
        self.url = reverse("adjust_experience", args=[self.character.id])

    def test_plain_delta_changes_current_and_overall_experience(self):
        response = self.client.post(self.url, {"delta": "10"})

        self.assertEqual(response.status_code, 302)
        self.character.refresh_from_db()
        self.assertEqual(self.character.current_experience, 50)
        self.assertEqual(self.character.overall_experience, 110)

    def test_positive_trailing_star_spends_only_current_experience(self):
        self.client.post(self.url, {"delta": "10*"})

        self.character.refresh_from_db()
        self.assertEqual(self.character.current_experience, 30)
        self.assertEqual(self.character.overall_experience, 100)

    def test_negative_leading_star_restores_only_current_experience(self):
        self.client.post(self.url, {"delta": "*-5"})

        self.character.refresh_from_db()
        self.assertEqual(self.character.current_experience, 45)
        self.assertEqual(self.character.overall_experience, 100)

    def test_starred_spending_cannot_make_current_experience_negative(self):
        self.client.post(self.url, {"delta": "*50"})

        self.character.refresh_from_db()
        self.assertEqual(self.character.current_experience, 0)
        self.assertEqual(self.character.overall_experience, 100)
