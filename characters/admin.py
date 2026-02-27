from django.contrib import admin
from .models import (
    Race, Character, Skill, Language,
    CharacterLanguage, Disadvantage, Advantage, School,
    SpecialAbility, ChoiceBonus
)

# --- INLINES ---

class ChoiceBonusInline(admin.StackedInline):
    model = ChoiceBonus
    extra = 1
    filter_horizontal = ('available_skills',)
    verbose_name = "Wählbare Fertigkeit"
    verbose_name_plural = "Wählbare Fertigkeiten"

class LanguageInline(admin.TabularInline):
    model = CharacterLanguage
    extra = 1

# --- ADMIN CLASSES ---

@admin.register(Race)
class RaceAdmin(admin.ModelAdmin):
    filter_horizontal = ('special_abilities',)
    inlines = [ChoiceBonusInline]
    save_on_top = True

    fieldsets = (
        (None, {'fields': ('name', 'size_class')}),
        ('Attribute (Min/Max)', {
            'fields': (
                ('min_st', 'max_st'), ('min_con', 'max_con'),
                ('min_dex', 'max_dex'), ('min_per', 'max_per'),
                ('min_int', 'max_int'), ('min_wil', 'max_wil'),
                ('min_cha', 'max_cha')
            )
        }),
        ('Bodenbewegung', {
            'fields': (('base_movement', 'march_movement'),
                       ('sprint_movement', 'swimming_movement'))
        }),
        ('Flugfähigkeit', {
            'fields': (
                'can_fly', 
                ('base_fly_speed', 'march_fly_speed', 'sprint_fly_speed')
            )
        }),
        ('Punkte & Boni (JSON)', {
            'fields': (('start_attribute_points', 'start_skill_points',
                        'start_free_points'), 'skill_bonus'),
        }),
        ('Rassen-Sonderfähigkeiten', {
            'fields': ('special_abilities',),
        }),
    )

@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    # Diese Felder sind berechnete Properties aus deinem Model
    readonly_fields = (
        'st_mod', 'con_mod', 'dex_mod', 'per_mod', 'int_mod', 'wil_mod', 'cha_mod',
        'max_hp', 'initiative', 'mental_resistance', 'schock_resistance', 
        'arcane_power', 'potential', 'defense_value'
    )

    fieldsets = (
        ('Allgemein', {
            'fields': ('name', 'race')
        }),
        ('Attribute', {
            'fields': (
                ('strength', 'st_mod'),
                ('constitution', 'con_mod'),
                ('dexterity', 'dex_mod'),
                ('perception', 'per_mod'),
                ('intelligence', 'int_mod'),
                ('willpower', 'wil_mod'),
                ('charisma', 'cha_mod'),
            )
        }),
        ('Abgeleitete Werte (Berechnet)', {
            'fields': (
                ('max_hp', 'schock_resistance'),
                ('mental_resistance', 'defense_value'),
                ('initiative', 'arcane_power', 'potential'),
            ),
        }),
        ('Wissen & Entwicklung', {
            'fields': ('experience_points', 'damage_points'),
        }),
        ('Zusätzliche Informationen (JSON)', {
            'fields': ('skills', 'schools', 'advantages', 'disadvantages'),
            'classes': ('collapse',),
        }),
    )

    inlines = [LanguageInline]

@admin.register(SpecialAbility)
class SpecialAbilityAdmin(admin.ModelAdmin):
    list_display = ('name', 'rs_bonus', 'sr_bonus', 'damage_dice')
    search_fields = ('name',)

@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ('school_name', 'name', 'level')
    list_filter = ('school_name', 'level')

# Einfache Registrierungen für den Rest
admin.site.register(Skill)
admin.site.register(Language)
admin.site.register(Disadvantage)
admin.site.register(Advantage)