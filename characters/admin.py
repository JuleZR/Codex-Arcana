from django.contrib import admin
from .models import Race, Character, Skill, Language, CharacterLanguage, Disadvantage, Advantage, School

admin.site.register(Race)
admin.site.register(Character)
admin.site.register(Skill)
admin.site.register(Language)
admin.site.register(Disadvantage)
admin.site.register(Advantage)
admin.site.register(CharacterLanguage)
# admin.site.register(School)

@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ('school_name', 'name', 'level') # Spalten in der Übersicht
    list_filter = ('school_name', 'level')          # Filter am rechten Rand
