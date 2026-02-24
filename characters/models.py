from django.db import models

# Create your models here.
class Race(models.Model):
    name = models.CharField(max_length=100)

    #min and max attributes for character creation
    min_st = models.IntegerField(default=0)
    min_con = models.IntegerField(default=0)
    min_dex = models.IntegerField(default=0)
    min_per = models.IntegerField(default=0)
    min_int = models.IntegerField(default=0)
    min_wil = models.IntegerField(default=0)
    min_cha = models.IntegerField(default=0)

    max_st = models.IntegerField(default=0)
    max_con = models.IntegerField(default=0)
    max_dex = models.IntegerField(default=0)
    max_per = models.IntegerField(default=0)
    max_int = models.IntegerField(default=0)
    max_wil = models.IntegerField(default=0)
    max_cha = models.IntegerField(default=0)

    #movement rates in feet per round
    base_movement = models.IntegerField(default=0)
    march_movement = models.IntegerField(default=0)
    sprint_movement = models.IntegerField(default=0)
    swimming_movement = models.IntegerField(default=0)

    # size class: 1 = tiny, 2 = small, 3 = medium, 4 = large, 5 = huge
    size_class = models.IntegerField(default=2)

    # skill bonuses and special abilities as JSON fields, with the skill/ability
    # name as the key and the bonus/description as the value
    skill_bonus = models.JSONField(default=dict)
    special_abilities = models.JSONField(default=dict)

    # character creation points for attributes and free points
    start_attribute_points = models.IntegerField(default=40)
    start_skill_points = models.IntegerField(default=50)
    start_free_points = models.IntegerField(default=30)

    def __str__(self):
        return self.name
    
class Skill(models.Model):
    name = models.CharField(max_length=100)
    base_attribute = models.CharField(max_length=3, choices=[
        ('ST', 'Strength'),
        ('KON', 'Constitution'),
        ('GE', 'Geschick'),
        ('WA', 'Wahrnehmung'),
        ('INT', 'Intelligenz'),
        ('WIL', 'Willenskraft'),
        ('CHA', 'Charisma')
    ])
    max_level = models.IntegerField(default=10)

    def __str__(self):
        return self.name

class Disadvantage(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()

    max_levels = models.IntegerField(default=0)
    points_per_level = models.IntegerField(default=0)

    def __str__(self):
        return self.name
    
class Advantage(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()

    max_levels = models.IntegerField(default=0)
    points_per_level = models.IntegerField(default=0)

    def __str__(self):
        return self.name

class School(models.Model):
    school_name = models.CharField(max_length=100)
    name = models.CharField(max_length=100)
    description = models.TextField()
    level = models.IntegerField(default=0)
    skill_bonus = models.JSONField(default=dict)

    def __str__(self):
        return f"{self.school_name}: {self.name} (Rang {self.level})"

class Language(models.Model):
    name = models.CharField(max_length=100)
    max_level = models.IntegerField(default=3)

    def __str__(self):
        return self.name

class CharacterLanguage(models.Model):
    character = models.ForeignKey('Character', on_delete=models.CASCADE)
    language = models.ForeignKey(Language, on_delete=models.CASCADE)
    level = models.IntegerField(default=1)
    can_write = models.BooleanField(default=False) # Kann DIESER Charakter sie schreiben?

    def save(self, *args, **kwargs):
        if self.level > self.language.max_level:
            self.level = self.language.max_level
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.character.name} spricht {self.language.name} (Stufe {self.level})"


class Character(models.Model):
    name = models.CharField(max_length=100)
    race = models.ForeignKey(Race, on_delete=models.CASCADE)

    # attributes
    strength = models.IntegerField()
    constitution = models.IntegerField()
    dexterity = models.IntegerField()
    perception = models.IntegerField()
    intelligence = models.IntegerField()
    willpower = models.IntegerField()
    charisma = models.IntegerField()

    learned_languages = models.ManyToManyField(Language, through=CharacterLanguage)

    # skills, schools, advantages, and disadvantages as JSON fields,
    # with the skill/school/advantage/disadvantage

    skills = models.JSONField(default=dict, blank=True)
    schools = models.JSONField(default=dict, blank=True)
    advantages = models.JSONField(default=dict, blank=True)
    disadvantages = models.JSONField(default=dict, blank=True)

    experience_points = models.IntegerField(default=0)
    damage_points = models.IntegerField(default=0)

    def _get_attribute_mod(self, value):
        return value - 5

    # Attribute modifiers based on the formula attribute - 5,
    # which gives a range of -4 to +7 for attributes between 0 and 10
    @property
    def st_mod(self):
        return self._get_attribute_mod(self.strength)
    @property
    def con_mod(self):
        return self._get_attribute_mod(self.constitution)
    @property
    def dex_mod(self):
        return self._get_attribute_mod(self.dexterity)
    @property
    def per_mod(self):
        return self._get_attribute_mod(self.perception)
    @property
    def int_mod(self):
        return self._get_attribute_mod(self.intelligence)
    @property
    def wil_mod(self):
        return self._get_attribute_mod(self.willpower)
    @property
    def cha_mod(self):
        return self._get_attribute_mod(self.charisma)

    @property
    def initiative(self):
        return self.per_mod

    @property
    def arcane_power(self):
        return self.willpower

    @property
    def potential(self):
        return self.willpower // 2

    @property
    def defense_value(self):
        return 14 + self.dex_mod + self.per_mod

    @property
    def mental_resistance(self):
        return 14 + self.int_mod + self.wil_mod

    @property
    def schock_resistance(self):
        return 14 + self.st_mod + self.con_mod

    @property
    def max_hp(self):
        return self.constitution * 6

    @property
    def wound_thresholds(self):
        c = self.constitution
        bonus_stages = 0
        result = {}
        schools_data: dict = self.schools
        leaned_tech = schools_data.keys() # pylint: disable=no-member
        relevant_schools = School.objects.filter(name__in=leaned_tech) # pylint: disable=no-member

        for school in relevant_schools:
            bonus_stages += school.skill_bonus.get('Wundstufe', 0)

        total_multiplyer = 6 + bonus_stages
        names = ["Angeschlagen",
                 "Verletzt",
                 "Verwundet",
                 "Schwer Verwundet",
                 "Außer Gefecht",
                 "Koma"]
        result = {}

        for i in range(1, total_multiplyer + 1):
            name_index = (i -1) - bonus_stages

            if name_index < 0:
                current_name = ""
            else:
                current_name = names[name_index]

            result[current_name] = c * i

        return result

    def __str__(self):
        return f"{self.name} ({self.race.name})"
