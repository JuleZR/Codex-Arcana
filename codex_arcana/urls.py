"""
URL configuration for codex_arcana project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path
from charsheet import views
from django.contrib.auth.views import LoginView
from django.views.static import serve
from django.conf import settings

urlpatterns = [
    path("admin/logout/", views.AppLogoutView.as_view(), name="admin_logout_override"),
    path("admin/", admin.site.urls),
    path("impressum/", views.impressum, name="impressum"),
    path("datenschutz/", views.datenschutz, name="datenschutz"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/account/update/", views.update_account_settings, name="update_account_settings"),
    path("character/new/", views.create_character, name="create_character"),
    path("character/<int:character_id>/edit/", views.edit_character, name="edit_character"),
    path("character/<int:character_id>/archive/", views.archive_character, name="archive_character"),
    path("character/<int:character_id>/unarchive/", views.unarchive_character, name="unarchive_character"),
    path("character/<int:character_id>/delete/", views.delete_character, name="delete_character"),
    path("character/draft/<int:draft_id>/delete/", views.delete_creation_draft, name="delete_creation_draft"),
    path("app/logout/", views.AppLogoutView.as_view(), name="app_logout"),
    path("sheet/", views.sheet, name="sheet"),
    path("character/<int:character_id>/", views.character_sheet, name="character_sheet"),
    path("character/<int:character_id>/diary/", views.character_diary_entries_api, name="character_diary_entries_api"),
    path("character/<int:character_id>/diary/import-legacy/", views.import_legacy_character_diary, name="import_legacy_character_diary"),
    path("character/<int:character_id>/diary/<int:entry_id>/edit/", views.edit_character_diary_entry, name="edit_character_diary_entry"),
    path("character/<int:character_id>/diary/<int:entry_id>/save/", views.save_character_diary_entry, name="save_character_diary_entry"),
    path("character/<int:character_id>/diary/<int:entry_id>/fix/", views.fix_character_diary_entry, name="fix_character_diary_entry"),
    path("character/<int:character_id>/diary/<int:entry_id>/delete/", views.delete_character_diary_entry, name="delete_character_diary_entry"),
    path("character/<int:character_id>/info/update/", views.update_character_info, name="update_character_info"),
    path("character/<int:character_id>/skills/<int:character_skill_id>/specification/update/", views.update_skill_specification, name="update_skill_specification"),
    path("character/<int:character_id>/techniques/<int:technique_id>/specification/update/", views.update_technique_specification, name="update_technique_specification"),
    path("character/<int:character_id>/adjust-personal-fame-point/", views.adjust_personal_fame_point, name="adjust_personal_fame_point"),
    path("character/<int:character_id>/adjust-damage/", views.adjust_current_damage, name="adjust_current_damage"),
    path("character/<int:character_id>/adjust-arcane-power/", views.adjust_current_arcane_power, name="adjust_current_arcane_power"),
    path("character/<int:character_id>/spells/<int:spell_id>/cast/", views.cast_spell, name="cast_spell"),
    path("character/<int:character_id>/adjust-money/", views.adjust_money, name="adjust_money"),
    path("character/<int:character_id>/adjust-experience/", views.adjust_experience, name="adjust_experience"),
    path("character/<int:character_id>/learn/apply/", views.apply_learning, name="apply_learning"),
    path("character/<int:character_id>/shop-item/create/", views.create_shop_item, name="create_shop_item"),
    path("character/<int:character_id>/shop/buy/", views.buy_shop_cart, name="buy_shop_cart"),
    path("character-item/<int:pk>/toggle-equip/", views.toggle_equip, name="toggle_equip"),
    path("character-item/<int:character_item_id>/rune/<int:rune_id>/specification/update/", views.update_rune_specification, name="update_rune_specification"),
    path("character-item/<int:pk>/runes/update/", views.update_character_item_runes, name="update_character_item_runes"),
    path("character-item/<int:pk>/consume/", views.consume_item, name="consume_item"),
    path("character-item/<int:pk>/remove/", views.remove_item, name="remove_item"),
    path("", LoginView.as_view(template_name="registration/login.html", redirect_authenticated_user=True), name="login"),
    path("api/roll/", views.roll_dice_view, name="roll_dice"),
    path("media/<path:path>", serve, {"document_root": settings.MEDIA_ROOT}),
]
