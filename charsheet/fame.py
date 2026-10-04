"""Permanent transfers of earned personal fame ranks."""

from django.db import transaction

from charsheet.models import Character


@transaction.atomic
def spend_personal_fame_rank(character) -> bool:
    """Convert one available personal rank into a permanent sacrifice rank."""
    from charsheet.sheet_context import build_fame_partial_context

    locked = Character.objects.select_for_update().get(pk=character.pk)
    if build_fame_partial_context(locked)["effective_personal_fame_rank"] < 1:
        return False
    locked.sacrifice_rank += 1
    locked.save(update_fields=["sacrifice_rank"])
    character.sacrifice_rank = locked.sacrifice_rank
    return True
