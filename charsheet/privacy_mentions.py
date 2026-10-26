"""Ephemeral username matching; snapshots contain only match flags."""

import html
import re
import unicodedata
from html.parser import HTMLParser
from urllib.parse import unquote

TRANSFER_MODELS = frozenset(
    {
        "charsheet.ItemTransfer",
        "charsheet.ItemOwnershipEvent",
        "charsheet.ItemTransferNotification",
        "charsheet.ItemPermissionGrant",
    }
)
USERNAME_CHECK_VERSION = 1
INVITATION_MODEL = "charsheet.GameGroupInvitation"
INVITATION_CHECK_VERSION = 1
ITEM_CONTENT_MODELS = frozenset({
    "charsheet.CharacterItem", "charsheet.ItemRune",
    "charsheet.CharacterItemRuneSpec", "charsheet.CharacterItemDisclosure",
    "charsheet.CharacterItemSemanticEffect",
    "charsheet.CharacterItemIdentificationState",
    "charsheet.CharacterItemEffectIdentification",
    "charsheet.CharacterCreatureItem",
})
WORDS = re.compile(r"[^\W_]+", re.UNICODE)
EXPLICIT_USERNAME = re.compile(
    r"\b(?:username|benutzername)\s*[:=]\s*(?P<value>\S+)", re.I
)


def normalized_text(value):
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(
        character
        for character in normalized
        if unicodedata.category(character) != "Cf"
    )


def words(value):
    return WORDS.findall(normalized_text(value))


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, value):
        self.parts.append(value)

    def handle_starttag(self, tag, attrs):
        if tag in {"br", "p", "div", "li", "tr", "td", "h1", "h2", "h3"}:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        self.handle_starttag(tag, [])


class UsernameMatcher:
    def __init__(self, usernames):
        self.trie = {}
        for username in usernames:
            tokens = words(str(username))
            if not tokens:
                continue
            node = self.trie
            for token in tokens:
                node = node.setdefault(token, {})
            node[None] = True

    def token_match(self, tokens):
        for start in range(len(tokens)):
            node = self.trie
            for index in range(start, len(tokens)):
                token = tokens[index]
                # German possessive endings must not hide an account name.
                if token.endswith("s") and None in node.get(token[:-1], {}):
                    return True
                node = node.get(token)
                if node is None:
                    break
                if None in node:
                    return True
        return False

    def text_match(self, value):
        decoded = html.unescape(unquote(value))
        if any(self.explicit_name(match.group("value"))
               for match in EXPLICIT_USERNAME.finditer(decoded)):
            return True
        if self.token_match(words(decoded)):
            return True
        if "<" in decoded:
            parser = VisibleText()
            try:
                parser.feed(decoded)
            except (ValueError, AssertionError):
                return True
            visible = "".join(parser.parts)
            if self.token_match(words(visible)) or any(
                self.explicit_name(match.group("value"))
                for match in EXPLICIT_USERNAME.finditer(visible)
            ):
                return True
        return False

    def explicit_name(self, value):
        return bool(value.strip())

    def contains(self, value):
        if isinstance(value, str):
            return self.text_match(value)
        if isinstance(value, dict):
            for key, item in value.items():
                key_words = words(str(key))
                if (
                    key_words
                    and (
                        key_words[-1] in {"username", "benutzername"}
                        or key_words[-2:] == ["user", "name"]
                    )
                    and isinstance(item, str)
                    and self.explicit_name(item)
                ):
                    return True
                if self.text_match(str(key)) or self.contains(item):
                    return True
        elif isinstance(value, list):
            return any(self.contains(item) for item in value)
        return False


class ForeignAccountMatcher(UsernameMatcher):
    IDS = re.compile(
        r"(?<![\w-])(?:(?P<kind>user|benutzer|account|charakter|character|"
        r"gruppe|group|einladung|invitation)[\s_-]*)?"
        r"(?:id|kennung)\s*[:=#]?\s*(?P<id>\d+)\b", re.I,
    )

    def __init__(self, accounts, own_id, own_username):
        accounts = [(pk, name) for pk, name in accounts
                    if str(pk) != str(own_id)]
        super().__init__(name for _, name in accounts)
        self.own_id = str(own_id)
        self.own_name = tuple(words(own_username))
        self.ambiguous_name = any(tuple(words(name)) == self.own_name
                                  for _, name in accounts)

    def explicit_name(self, value):
        return bool(value.strip()) and (
            tuple(words(value)) != self.own_name or self.ambiguous_name)

    def foreign_id(self, value):
        if value is None or value == "":
            return False
        text = str(value).strip()
        if text.isdecimal():
            text = str(int(text))
        return text != self.own_id

    def text_match(self, value):
        if super().text_match(value):
            return True
        decoded = html.unescape(unquote(value))
        texts = [decoded]
        if "<" in decoded:
            parser = VisibleText()
            try:
                parser.feed(decoded)
            except (ValueError, AssertionError):
                return True
            texts.append("".join(parser.parts))
        return any(
            match.group("kind") not in {
                "charakter", "character", "gruppe", "group",
                "einladung", "invitation",
            } and self.foreign_id(match.group("id"))
            for text in texts
            for match in self.IDS.finditer(normalized_text(text))
        )

    def contains(self, value):
        if isinstance(value, dict):
            for key, item in value.items():
                key_words = tuple(words(str(key)))
                if (
                    key_words[-2:] in {
                        ("user", "id"), ("account", "id"), ("benutzer", "id"),
                    } and self.foreign_id(item)
                ):
                    return True
                if key_words in {("user",), ("account",), ("benutzer",)}:
                    if (isinstance(item, dict)
                            and self.foreign_id(item.get("id"))):
                        return True
        return super().contains(value)


def needs_username_check(source):
    invitations = source.get("review_context", {}).get(
        "invitation_accounts", {})
    invitation_check = (
        invitations.get("version") != INVITATION_CHECK_VERSION
        and bool(source["categories"].get(
            INVITATION_MODEL, {}).get("records"))
    )
    return invitation_check
