from django import template
from django.utils.safestring import mark_safe
from markdown_it import MarkdownIt
from decimal import Decimal, InvalidOperation


register = template.Library()

_markdown = MarkdownIt(
    "default",
    {
        "html": False,
        "linkify": False,
        "typographer": False,
    },
)


def _is_table_separator(line: str) -> bool:
    cells = _split_table_row(line)
    if len(cells) < 2:
        return False
    return all(cell.replace(":", "").replace("-", "").strip() == "" and "-" in cell for cell in cells)


def _split_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped or "|" not in stripped:
        return []
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _render_inline(value: str) -> str:
    return _markdown.renderInline(value.strip()) if value.strip() else "&ndash;"


def _render_compact_table(header: list[str], rows: list[list[str]]) -> str:
    if not header:
        return ""
    normalized_rows = [
        row + [""] * max(0, len(header) - len(row))
        for row in rows
    ]
    html = ['<div class="card-roll-strip" role="group" aria-label="Wurftabelle">']
    html.append('<div class="card-roll-strip__ranges">')
    for cell in header:
        html.append(f'<span class="card-roll-strip__range">{_render_inline(cell)}</span>')
    html.append("</div>")
    for row in normalized_rows:
        html.append('<div class="card-roll-strip__results">')
        for cell in row[:len(header)]:
            html.append(f'<span class="card-roll-strip__result">{_render_inline(cell)}</span>')
        html.append("</div>")
    html.append("</div>")
    return "".join(html)


def _render_vertical_roll(rows: list[tuple[str, list[str]]]) -> str:
    if not rows:
        return ""
    html = ['<div class="card-roll-list" role="group" aria-label="Wurfliste">']
    for label, values in rows:
        html.append('<div class="card-roll-list__row">')
        html.append(f'<span class="card-roll-list__range">{_render_inline(label)}</span>')
        html.append('<span class="card-roll-list__result">')
        rendered_values = [_render_inline(value) for value in values if value.strip()]
        html.append("<br>".join(rendered_values) if rendered_values else "&ndash;")
        html.append("</span></div>")
    html.append("</div>")
    return "".join(html)


def _render_tabstop_rows(rows: list[tuple[str, list[str]]]) -> str:
    if not rows:
        return ""
    html = ['<div class="card-tabstops">']
    for label, values in rows:
        html.append('<div class="card-tabstop">')
        html.append(f'<span class="card-tabstop__label">{_render_inline(label)}</span>')
        html.append('<span class="card-tabstop__value">')
        rendered_values = [_render_inline(value) for value in values if value.strip()]
        html.append("<br>".join(rendered_values) if rendered_values else "&ndash;")
        html.append("</span></div>")
    html.append("</div>")
    return "".join(html)


def _parse_roll_directive(lines: list[str]) -> tuple[list[str], list[list[str]]]:
    pairs: list[tuple[str, str]] = []
    for line in lines:
        for raw_part in line.split("|"):
            part = raw_part.strip()
            if not part:
                continue
            if ":" in part:
                label, result = part.split(":", 1)
            elif "=" in part:
                label, result = part.split("=", 1)
            else:
                label, result = part, ""
            pairs.append((label.strip(), result.strip()))
    return [label for label, _result in pairs], [[result for _label, result in pairs]]


def _parse_vertical_roll_directive(lines: list[str]) -> list[tuple[str, list[str]]]:
    rows: list[tuple[str, list[str]]] = []
    for line in lines:
        if not line.strip():
            continue
        if "::" in line:
            label, value = line.split("::", 1)
            label = label.strip()
            value = value.strip()
            if label:
                rows.append((label, [value]))
            elif rows and value:
                rows[-1][1].append(value)
            continue
        if "\t" in line:
            parts = line.split("\t")
            label = parts[0].strip()
            value = " ".join(part.strip() for part in parts[1:] if part.strip())
            if label:
                rows.append((label, [value]))
            elif rows and value:
                rows[-1][1].append(value)
            continue
        stripped = line.strip()
        if ":" in stripped:
            label, value = stripped.split(":", 1)
        elif "=" in stripped:
            label, value = stripped.split("=", 1)
        else:
            label, value = stripped, ""
        rows.append((label.strip(), [value.strip()]))
    return rows


def _parse_tabstop_lines(lines: list[str]) -> list[tuple[str, list[str]]]:
    rows: list[tuple[str, list[str]]] = []
    for line in lines:
        label, value = line.split("::", 1)
        label = label.strip()
        value = value.strip()
        if label:
            rows.append((label, [value]))
        elif rows and value:
            rows[-1][1].append(value)
    return rows


def _render_card_markdown(value: str) -> str:
    lines = value.splitlines()
    output: list[str] = []
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped.startswith("::roll"):
            directive_lines: list[str] = []
            inline_value = stripped.removeprefix("::roll").strip()
            is_vertical = inline_value in {"vertical", "list"}
            if inline_value and not is_vertical:
                directive_lines.append(inline_value)
            index += 1
            while index < len(lines) and lines[index].strip() != "::":
                directive_lines.append(lines[index])
                index += 1
            if index < len(lines) and lines[index].strip() == "::":
                index += 1
            if is_vertical:
                output.append(_render_vertical_roll(_parse_vertical_roll_directive(directive_lines)))
            elif len(directive_lines) >= 2 and _is_table_separator(directive_lines[1]):
                header = _split_table_row(directive_lines[0])
                rows = [
                    row
                    for row in (_split_table_row(line) for line in directive_lines[2:])
                    if row
                ]
                output.append(_render_compact_table(header, rows))
            else:
                header, rows = _parse_roll_directive(directive_lines)
                output.append(_render_compact_table(header, rows))
            continue

        if "::" in lines[index] and stripped != "::" and not stripped.startswith("::"):
            tabstop_lines: list[str] = []
            while index < len(lines):
                current = lines[index]
                current_stripped = current.strip()
                if "::" not in current or current_stripped == "::" or current_stripped.startswith("::roll"):
                    break
                tabstop_lines.append(current)
                index += 1
            output.append(_render_tabstop_rows(_parse_tabstop_lines(tabstop_lines)))
            continue

        if index + 1 < len(lines):
            header = _split_table_row(lines[index])
            separator = lines[index + 1]
            if header and _is_table_separator(separator):
                rows: list[list[str]] = []
                index += 2
                while index < len(lines):
                    row = _split_table_row(lines[index])
                    if not row:
                        break
                    rows.append(row)
                    index += 1
                output.append(_render_compact_table(header, rows))
                continue
        output.append(_markdown.render(lines[index] + "\n") if lines[index].strip() else "")
        index += 1
    return "\n".join(output)


@register.filter(name="card_markdown")
def card_markdown(value):
    if not value:
        return ""
    return mark_safe(_render_card_markdown(str(value)))


@register.filter(name="standard_markdown")
def standard_markdown(value):
    """Render safe, standard Markdown without allowing embedded HTML."""
    if not value:
        return ""
    return mark_safe(_markdown.render(str(value)))


@register.filter(name="compact_number_de")
def compact_number_de(value):
    """Format a decimal with a comma and without insignificant zeroes."""
    if value is None or value == "":
        return ""
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return str(value)
    rendered = format(number, "f").rstrip("0").rstrip(".")
    if rendered in {"", "-0"}:
        rendered = "0"
    return rendered.replace(".", ",")


@register.filter(name="compact_number_integer_de")
def compact_number_integer_de(value):
    rendered = compact_number_de(value)
    return rendered.partition(",")[0]


@register.filter(name="compact_number_fraction_de")
def compact_number_fraction_de(value):
    rendered = compact_number_de(value)
    return rendered.partition(",")[2]


def _render_fluff_lines(value: str) -> str:
    return "<br>".join(_markdown.renderInline(line) for line in value.splitlines())


@register.filter(name="card_fluff")
def card_fluff(value):
    """Render card fluff, with content after a standalone --- outside the quote."""
    if not value:
        return ""
    lines = str(value).splitlines()
    separator_index = next((index for index, line in enumerate(lines) if line.strip() == "---"), None)
    if separator_index is None:
        quote_text = "\n".join(lines).strip()
        outside_text = ""
    else:
        quote_text = "\n".join(lines[:separator_index]).strip()
        outside_text = "\n".join(lines[separator_index + 1:]).strip()

    html: list[str] = ['<div class="card-vow-group">']
    if quote_text:
        html.append(f'<blockquote class="card-vow">&bdquo;{_render_fluff_lines(quote_text)}&ldquo;</blockquote>')
    if outside_text:
        html.append(f'<div class="card-vow-outside">{_render_fluff_lines(outside_text)}</div>')
    html.append("</div>")
    return mark_safe("".join(html))


def _render_fluff_lines(value: str) -> str:
    return "<br>".join(_markdown.renderInline(line) for line in value.splitlines())


@register.filter(name="card_fluff")
def card_fluff(value):
    """Render card fluff, with content after a standalone --- outside the quote."""
    if not value:
        return ""
    lines = str(value).splitlines()
    separator_index = next((index for index, line in enumerate(lines) if line.strip() == "---"), None)
    if separator_index is None:
        quote_text = "\n".join(lines).strip()
        outside_text = ""
    else:
        quote_text = "\n".join(lines[:separator_index]).strip()
        outside_text = "\n".join(lines[separator_index + 1:]).strip()

    html: list[str] = ['<div class="card-vow-group">']
    if quote_text:
        html.append(f'<blockquote class="card-vow">&bdquo;{_render_fluff_lines(quote_text)}&ldquo;</blockquote>')
    if outside_text:
        html.append(f'<div class="card-vow-outside">{_render_fluff_lines(outside_text)}</div>')
    html.append("</div>")
    return mark_safe("".join(html))
