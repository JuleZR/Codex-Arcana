"""Shared JPEG conversion for uploaded and existing non-symbol images."""

from io import BytesIO
from pathlib import PurePosixPath

from PIL import Image, ImageOps
from django.core.files.base import ContentFile
from django.db.models import ImageField
from django.db.models.signals import pre_save
from django.dispatch import receiver


def convertible_image_fields(model):
    """Keep symbol fields and rune glyphs in their original format."""
    for field in model._meta.concrete_fields:
        if not isinstance(field, ImageField):
            continue
        if "symbol" in field.name or field.name == "aspect_image" or (
            model._meta.label_lower == "charsheet.rune"
            and field.name == "image"
        ):
            continue
        yield field


def is_jpeg_name(name):
    return PurePosixPath(name).suffix.lower() in {".jpg", ".jpeg"}


def jpeg_content(source, name):
    """Orient images correctly and flatten transparency onto white."""
    source.seek(0)
    with Image.open(source) as original:
        # Avoid repeatedly encoding already valid JPEG uploads.
        if original.format == "JPEG" and is_jpeg_name(name):
            source.seek(0)
            return None
        oriented = ImageOps.exif_transpose(original)
        rgba = oriented.convert("RGBA")
        flattened = Image.new("RGB", rgba.size, "white")
        flattened.paste(rgba, mask=rgba.getchannel("A"))
        output = BytesIO()
        flattened.save(output, "JPEG", quality=90, optimize=True)
    return ContentFile(
        output.getvalue(), name=str(PurePosixPath(name).with_suffix(".jpg"))
    )


@receiver(pre_save, dispatch_uid="charsheet.convert_image_uploads")
def convert_image_uploads(sender, instance, raw=False, update_fields=None,
                          **kwargs):
    """Cover model/admin uploads, including explicit FieldFile.save calls."""
    if raw or sender._meta.app_label != "charsheet":
        return
    for field in convertible_image_fields(sender):
        if update_fields is not None and field.name not in update_fields:
            continue
        picture = getattr(instance, field.name)
        if not picture:
            continue
        if picture._committed:
            if is_jpeg_name(picture.name):
                continue
            with picture.storage.open(picture.name, "rb") as source:
                converted = jpeg_content(source, picture.name)
            if converted is not None:
                name = picture.storage.save(converted.name, converted)
                setattr(instance, field.name, name)
        else:
            converted = jpeg_content(picture.file, picture.name)
            if converted is not None:
                setattr(instance, field.name, converted)
