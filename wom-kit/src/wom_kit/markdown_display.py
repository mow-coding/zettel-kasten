"""Pure WOM-safe Markdown projection for human zet viewing.

The projection is deliberately display-only.  It never reads or writes the
filesystem and never changes the canonical zet source supplied by the caller.
It inserts CommonMark backslash escapes only where GFM could otherwise turn a
literal tilde into strikethrough or an unpaired ``**`` run into emphasis.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
import unicodedata
from typing import Any, Iterator


WOM_SAFE_MARKDOWN_DISPLAY_SCHEMA = "wom-kit/wom-safe-markdown-display/v0.1"

_FENCE_OPEN_RE = re.compile(r"^(?P<indent> {0,3})(?P<fence>`{3,}|~{3,})(?P<info>[^\r\n]*)$")
_BLOCK_QUOTE_PREFIX_RE = re.compile(r"^ {0,3}>[ \t]?")
_LIST_PREFIX_RE = re.compile(
    r"^ {0,3}(?P<marker>[*+-]|\d{1,9}[.)])(?P<spacing>[ \t]+)"
)
_ATX_HEADING_RE = re.compile(r"^ {0,3}#{1,6}(?:[ \t]+|$)")
_SETEXT_UNDERLINE_RE = re.compile(r"^ {0,3}(?:=+|-+)[ \t]*$")
_THEMATIC_BREAK_RE = re.compile(
    r"^ {0,3}(?:(?:\*[ \t]*){3,}|(?:_[ \t]*){3,}|(?:-[ \t]*){3,})$"
)
_AUTOLINK_RE = re.compile(
    r"<(?:[A-Za-z][A-Za-z0-9+.-]{1,31}:[^<>\x00-\x20\x7f]*|"
    r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*"
    r")>"
)
_HTML_TAG_NAME = r"[A-Za-z][A-Za-z0-9-]*"
_HTML_ATTRIBUTE_NAME = r"[A-Za-z_:][A-Za-z0-9_.:-]*"
_HTML_ATTRIBUTE_VALUE = r'(?:[^ \t\r\n"\'=<>`]+|\'[^\']*\'|"[^"]*")'
_HTML_ATTRIBUTE = (
    rf"(?:[ \t\r\n]+{_HTML_ATTRIBUTE_NAME}"
    rf"(?:[ \t\r\n]*=[ \t\r\n]*{_HTML_ATTRIBUTE_VALUE})?)"
)
_HTML_TAG_RE = re.compile(
    rf"(?:<{_HTML_TAG_NAME}{_HTML_ATTRIBUTE}*[ \t\r\n]*/?>|"
    rf"</{_HTML_TAG_NAME}[ \t\r\n]*>|<![A-Z][^<>]*>)",
    re.DOTALL,
)
_BARE_URI_RE = re.compile(
    r"(?im)(?:^|(?<=[ \t\r\n\v\f*_(~]))"
    r"https?://"
    r"(?:[A-Za-z0-9_-]+\.)*[A-Za-z0-9-]+\.[A-Za-z0-9-]+"
    r"[^ \t\r\n\v\f<]*"
)
_RAW_HTML_BLOCK_TAGS = frozenset(
    {
        "address", "article", "aside", "base", "basefont", "blockquote",
        "body", "caption", "center", "col", "colgroup", "dd", "details",
        "dialog", "dir", "div", "dl", "dt", "fieldset", "figcaption",
        "figure", "footer", "form", "frame", "frameset", "h1", "h2",
        "h3", "h4", "h5", "h6", "head", "header", "hr", "html",
        "iframe", "legend", "li", "link", "main", "menu", "menuitem",
        "nav", "noframes", "ol", "optgroup", "option", "p", "param",
        "search", "section", "summary", "table", "tbody", "td", "tfoot",
        "th", "thead", "title", "tr", "track", "ul",
    }
)


@dataclass(frozen=True)
class _DelimiterRun:
    start: int
    end: int
    marker: str
    can_open: bool
    can_close: bool


@dataclass(frozen=True)
class _ContainerToken:
    kind: str
    continuation_width: int = 0
    list_marker: str | None = None
    item_has_content: bool = False
    interrupts_paragraph: bool = False


@dataclass(frozen=True)
class _FenceState:
    marker: str
    minimum_length: int
    container: tuple[_ContainerToken, ...]


@dataclass(frozen=True)
class _RawHtmlBlockState:
    terminator: str | None
    until_blank: bool = False
    container: tuple[_ContainerToken, ...] = ()


@dataclass(frozen=True)
class _InlineBracketState:
    is_image: bool
    link_generation_at_open: int


class _InlineLinkTracker:
    """Track nested inline-link labels with constant-time invalidation.

    A completed non-image link invalidates every bracket label that was open
    around it. Storing the current generation on each opener lets a later
    close detect that fact with one comparison, instead of rewriting the
    complete open-bracket stack for every nested link.
    """

    __slots__ = ("_link_generation", "_stack", "operation_count")

    def __init__(self) -> None:
        self._link_generation = 0
        self._stack: list[_InlineBracketState] = []
        self.operation_count = 0

    def __bool__(self) -> bool:
        return bool(self._stack)

    def open(self, *, is_image: bool) -> None:
        self._stack.append(
            _InlineBracketState(
                is_image=is_image,
                link_generation_at_open=self._link_generation,
            )
        )
        self.operation_count += 1

    def close(self) -> tuple[bool, bool]:
        opener = self._stack.pop()
        self.operation_count += 1
        return (
            opener.is_image,
            (
                not opener.is_image
                and opener.link_generation_at_open != self._link_generation
            ),
        )

    def record_non_image_link(self) -> None:
        self._link_generation += 1
        self.operation_count += 1


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _line_content(line: str) -> str:
    return line.rstrip("\r\n")


def _physical_lines_keepends(source: str) -> Iterator[str]:
    """Yield only CommonMark physical lines (LF, CR, or CRLF terminated).

    ``str.splitlines`` also splits at Unicode Zl/Zp characters such as U+2028
    and U+2029. CommonMark does not define those characters as line endings.
    """

    start = 0
    while start < len(source):
        cursor = start
        while cursor < len(source) and source[cursor] not in "\r\n":
            cursor += 1
        if cursor == len(source):
            yield source[start:]
            return
        end = cursor + 1
        if source[cursor] == "\r" and end < len(source) and source[end] == "\n":
            end += 1
        yield source[start:end]
        start = end


def _is_blank_payload(value: str) -> bool:
    """Return CommonMark blank-line truth without Python Unicode widening."""

    return all(character in " \t" for character in value)


def _display_width(value: str) -> int:
    width = 0
    for character in value:
        width = (width + 4) - (width % 4) if character == "\t" else width + 1
    return width


def _container_open_payload(
    line: str,
) -> tuple[str, tuple[_ContainerToken, ...]]:
    """Return the payload and exact quote/list container needed to continue it."""

    payload = _line_content(line)
    tokens: list[_ContainerToken] = []
    while True:
        quote = _BLOCK_QUOTE_PREFIX_RE.match(payload)
        if quote is not None:
            tokens.append(_ContainerToken("quote"))
            payload = payload[quote.end() :]
            continue
        list_item = _LIST_PREFIX_RE.match(payload)
        if list_item is not None:
            marker = list_item.group("marker")
            remaining = payload[list_item.end() :]
            ordered_start = (
                int(marker[:-1])
                if marker[:-1].isdigit()
                else None
            )
            item_has_content = not _is_blank_payload(remaining)
            tokens.append(
                _ContainerToken(
                    "list",
                    continuation_width=_display_width(list_item.group(0)),
                    list_marker=marker,
                    item_has_content=item_has_content,
                    interrupts_paragraph=(
                        item_has_content
                        and (ordered_start is None or ordered_start == 1)
                    ),
                )
            )
            payload = remaining
            continue
        return payload, tuple(tokens)


def _consume_indentation(value: str, required_width: int) -> str | None:
    width = 0
    cursor = 0
    while cursor < len(value) and value[cursor] in " \t" and width < required_width:
        character = value[cursor]
        width = (width + 4) - (width % 4) if character == "\t" else width + 1
        cursor += 1
    if width < required_width:
        return "" if _is_blank_payload(value) else None
    return value[cursor:]


def _container_continuation_payload(
    line: str,
    tokens: tuple[_ContainerToken, ...],
) -> str | None:
    payload = _line_content(line)
    for token in tokens:
        if token.kind == "quote":
            quote = _BLOCK_QUOTE_PREFIX_RE.match(payload)
            if quote is None:
                return "" if _is_blank_payload(payload) else None
            payload = payload[quote.end() :]
            continue
        payload = _consume_indentation(payload, token.continuation_width)
        if payload is None:
            return None
    return payload


def _fence_open(line: str) -> _FenceState | None:
    payload, container = _container_open_payload(line)
    match = _FENCE_OPEN_RE.fullmatch(payload)
    if match is None:
        return None
    fence = match.group("fence")
    info = match.group("info")
    # CommonMark does not allow a backtick-fence info string to contain a
    # backtick.  A tilde fence has no corresponding restriction.
    if fence[0] == "`" and "`" in info:
        return None
    return _FenceState(fence[0], len(fence), container)


def _fence_close(content: str, marker: str, minimum_length: int) -> bool:
    match = re.fullmatch(r" {0,3}(?P<fence>" + re.escape(marker) + r"{3,})[ \t]*", content)
    return bool(match and len(match.group("fence")) >= minimum_length)


def _is_indented_code_line(line: str) -> bool:
    content = _line_content(line)
    while True:
        quote = _BLOCK_QUOTE_PREFIX_RE.match(content)
        if quote is None:
            break
        content = content[quote.end() :]
    return bool(content) and (content.startswith("\t") or content.startswith("    "))


def _is_blank_line(line: str) -> bool:
    return _is_blank_payload(_line_content(line))


def _backslash_escape_mask(text: str) -> list[bool]:
    """Compute CommonMark backslash parity once in linear time."""

    escaped = [False] * len(text)
    slash_run = 0
    for index, character in enumerate(text):
        if character == "\\":
            slash_run += 1
            continue
        escaped[index] = slash_run % 2 == 1
        slash_run = 0
    return escaped


def _run_length(text: str, start: int, marker: str) -> int:
    cursor = start
    while cursor < len(text) and text[cursor] == marker:
        cursor += 1
    return cursor - start


def _inline_code_mask(
    text: str,
    escaped: list[bool],
) -> tuple[list[bool], int]:
    """Return matched CommonMark code-span positions and their pair count."""

    protected = [False] * len(text)
    span_count = 0
    cursor = 0
    while cursor < len(text):
        if text[cursor] != "`" or escaped[cursor]:
            cursor += 1
            continue
        opener_length = _run_length(text, cursor, "`")
        search = cursor + opener_length
        closing_start: int | None = None
        while search < len(text):
            found = text.find("`", search)
            if found < 0:
                break
            found_length = _run_length(text, found, "`")
            if found_length == opener_length:
                closing_start = found
                break
            search = found + found_length
        if closing_start is None:
            cursor += opener_length
            continue
        closing_end = closing_start + opener_length
        for position in range(cursor, closing_end):
            protected[position] = True
        span_count += 1
        cursor = closing_end
    return protected, span_count


def _mark(protected: list[bool], start: int, end: int) -> None:
    for position in range(max(0, start), min(len(protected), end)):
        protected[position] = True


def _generic_angle_close_indexes(text: str) -> tuple[dict[int, int], int]:
    """Return each ``<`` opener's first unquoted ``>`` in linear time.

    Quote state is a three-state finite automaton. Computing its suffix result
    backwards avoids rescanning the remainder of the paragraph for every
    possible angle opener.
    """

    closes: dict[int, int] = {}
    next_without_quote: int | None = None
    next_in_single_quote: int | None = None
    next_in_double_quote: int | None = None
    operations = 0
    for index in range(len(text) - 1, -1, -1):
        character = text[index]
        suffix_without_quote = next_without_quote
        suffix_in_single_quote = next_in_single_quote
        suffix_in_double_quote = next_in_double_quote
        if character == "'":
            next_without_quote = suffix_in_single_quote
            next_in_single_quote = suffix_without_quote
            next_in_double_quote = suffix_in_double_quote
        elif character == '"':
            next_without_quote = suffix_in_double_quote
            next_in_single_quote = suffix_in_single_quote
            next_in_double_quote = suffix_without_quote
        elif character == ">":
            next_without_quote = index
            next_in_single_quote = suffix_in_single_quote
            next_in_double_quote = suffix_in_double_quote
        else:
            next_without_quote = suffix_without_quote
            next_in_single_quote = suffix_in_single_quote
            next_in_double_quote = suffix_in_double_quote
        if character == "<" and next_without_quote is not None:
            closes[index] = next_without_quote
        operations += 1
    return closes, operations


def _terminated_angle_construct_ends(
    text: str,
    *,
    prefix: str,
    terminator: str,
) -> tuple[dict[int, int], int]:
    """Bind every special opener to its next terminator in linear shape."""

    operations = 0
    prefix_start = text.find(prefix)
    operations += len(text) if prefix_start < 0 else prefix_start + 1
    if prefix_start < 0:
        return {}, operations

    terminators: list[int] = []
    search = prefix_start + len(prefix)
    while search < len(text):
        found = text.find(terminator, search)
        operations += len(text) - search if found < 0 else found - search + 1
        if found < 0:
            break
        terminators.append(found)
        search = found + 1
    if not terminators:
        return {}, operations

    ends: dict[int, int] = {}
    terminator_index = 0
    start = prefix_start
    while start >= 0:
        minimum_terminator = start + len(prefix)
        while (
            terminator_index < len(terminators)
            and terminators[terminator_index] < minimum_terminator
        ):
            terminator_index += 1
            operations += 1
        if terminator_index == len(terminators):
            break
        ends[start] = terminators[terminator_index] + len(terminator)
        search = start + 1
        found = text.find(prefix, search)
        operations += len(text) - search if found < 0 else found - search + 1
        start = found
    return ends, operations


def _special_angle_end_indexes(text: str) -> tuple[dict[int, int], int]:
    ends: dict[int, int] = {}
    operations = 0
    for prefix, terminator in (
        ("<!--", "-->"),
        ("<![CDATA[", "]]>"),
        ("<?", "?>"),
    ):
        construct_ends, construct_operations = _terminated_angle_construct_ends(
            text,
            prefix=prefix,
            terminator=terminator,
        )
        ends.update(construct_ends)
        operations += construct_operations
    return ends, operations


def _angle_syntax_end(
    text: str,
    start: int,
    *,
    generic_close: int | None,
    special_end: int | None,
) -> int | None:
    if text.startswith("<!--", start):
        return special_end
    if text.startswith("<![CDATA[", start):
        return special_end
    if text.startswith("<?", start):
        return special_end

    if generic_close is None:
        return None
    end = generic_close + 1
    if (
        _AUTOLINK_RE.fullmatch(text, start, end)
        or _HTML_TAG_RE.fullmatch(text, start, end)
    ):
        return end
    return None


class _InlineLinkSyntaxIndex:
    """Answer every inline destination/title query in constant time.

    A paragraph can contain many link-shaped failures whose candidate
    destinations overlap.  Rescanning each suffix is quadratic.  These
    next-token tables and the next-lower parenthesis-prefix table are built
    once, then preserve the former parser's decisions with bounded queries.
    """

    __slots__ = (
        "text",
        "escaped",
        "length",
        "next_non_spacing",
        "next_raw_boundary",
        "next_pointy_close",
        "next_pointy_invalid",
        "next_title_double",
        "next_title_single",
        "next_title_paren",
        "next_blank_line",
        "parenthesis_prefix",
        "next_lower_prefix",
        "operation_count",
    )

    def __init__(self, text: str, escaped: list[bool]) -> None:
        self.text = text
        self.escaped = escaped
        self.length = len(text)
        size = self.length + 1
        sentinel = self.length
        self.next_non_spacing = [sentinel] * size
        self.next_raw_boundary = [sentinel] * size
        self.next_pointy_close = [sentinel] * size
        self.next_pointy_invalid = [sentinel] * size
        self.next_title_double = [sentinel] * size
        self.next_title_single = [sentinel] * size
        self.next_title_paren = [sentinel] * size
        self.next_blank_line = [sentinel] * size
        self.operation_count = 0

        non_spacing = raw_boundary = pointy_close = pointy_invalid = sentinel
        title_double = title_single = title_paren = sentinel
        for index in range(self.length - 1, -1, -1):
            character = text[index]
            is_escaped = escaped[index]
            if character not in " \t\r\n":
                non_spacing = index
            if not is_escaped and (
                character in " \t\r\n"
                or ord(character) < 0x20
                or character == "<"
            ):
                raw_boundary = index
            if not is_escaped and character == ">":
                pointy_close = index
            if character in "\r\n" or (
                not is_escaped and character == "<"
            ):
                pointy_invalid = index
            if not is_escaped and character == '"':
                title_double = index
            if not is_escaped and character == "'":
                title_single = index
            if not is_escaped and character == ")":
                title_paren = index
            self.next_non_spacing[index] = non_spacing
            self.next_raw_boundary[index] = raw_boundary
            self.next_pointy_close[index] = pointy_close
            self.next_pointy_invalid[index] = pointy_invalid
            self.next_title_double[index] = title_double
            self.next_title_single[index] = title_single
            self.next_title_paren[index] = title_paren
            self.operation_count += 1

        prefix = [0] * size
        for index, character in enumerate(text):
            delta = 0
            if not escaped[index]:
                if character == "(":
                    delta = 1
                elif character == ")":
                    delta = -1
            prefix[index + 1] = prefix[index] + delta
            self.operation_count += 1
        self.parenthesis_prefix = prefix

        next_lower = [sentinel + 1] * size
        monotonic: list[int] = []
        for index in range(self.length, -1, -1):
            while monotonic and prefix[monotonic[-1]] >= prefix[index]:
                monotonic.pop()
                self.operation_count += 1
            if monotonic:
                next_lower[index] = monotonic[-1]
            monotonic.append(index)
            self.operation_count += 1
        self.next_lower_prefix = next_lower

        blank_second = [False] * self.length
        after_line_ending = False
        cursor = 0
        while cursor < self.length:
            character = text[cursor]
            if character in "\r\n":
                if after_line_ending:
                    blank_second[cursor] = True
                after_line_ending = True
                if (
                    character == "\r"
                    and cursor + 1 < self.length
                    and text[cursor + 1] == "\n"
                ):
                    cursor += 1
            elif after_line_ending and character not in " \t":
                after_line_ending = False
            cursor += 1
            self.operation_count += 1
        next_blank = sentinel
        for index in range(self.length - 1, -1, -1):
            if blank_second[index]:
                next_blank = index
            self.next_blank_line[index] = next_blank
            self.operation_count += 1

    def end(self, start: int) -> int | None:
        self.operation_count += 1
        if start >= self.length:
            return None
        cursor = self.next_non_spacing[start]
        if cursor >= self.length:
            return None
        if self.text[cursor] == ")" and not self.escaped[cursor]:
            return cursor + 1

        if self.text[cursor] == "<" and not self.escaped[cursor]:
            destination_cursor = cursor + 1
            close = self.next_pointy_close[destination_cursor]
            invalid = self.next_pointy_invalid[destination_cursor]
            if close >= self.length or invalid < close:
                return None
            cursor = close + 1
        else:
            lower_prefix = self.next_lower_prefix[cursor]
            close = (
                lower_prefix - 1
                if lower_prefix <= self.length
                else self.length
            )
            boundary = self.next_raw_boundary[cursor]
            if close < boundary:
                return close + 1
            if (
                boundary >= self.length
                or self.text[boundary] not in " \t\r\n"
                or self.parenthesis_prefix[boundary]
                != self.parenthesis_prefix[cursor]
            ):
                return None
            cursor = boundary

        separator_start = cursor
        cursor = self.next_non_spacing[cursor]
        if cursor < self.length and self.text[cursor] == ")" and not self.escaped[cursor]:
            return cursor + 1
        if (
            cursor >= self.length
            or self.text[cursor] not in {'"', "'", "("}
            or cursor == separator_start
        ):
            return None

        opener = self.text[cursor]
        content_start = cursor + 1
        if opener == '"':
            closer = self.next_title_double[content_start]
        elif opener == "'":
            closer = self.next_title_single[content_start]
        else:
            closer = self.next_title_paren[content_start]
        if (
            closer >= self.length
            or self.next_blank_line[content_start] < closer
        ):
            return None
        cursor = self.next_non_spacing[closer + 1]
        if cursor < self.length and self.text[cursor] == ")" and not self.escaped[cursor]:
            return cursor + 1
        return None


def _inline_link_syntax_end(
    text: str,
    start: int,
    escaped: list[bool],
    *,
    syntax_index: _InlineLinkSyntaxIndex | None = None,
) -> int | None:
    """Return the outer ``)`` end for one CommonMark-shaped inline link."""

    index = syntax_index or _InlineLinkSyntaxIndex(text, escaped)
    return index.end(start)


def _consume_optional_reference_spacing(
    text: str,
    cursor: int,
) -> tuple[int, int | None]:
    """Consume spaces/tabs and at most one physical line ending.

    The second result records the start of that ending so a destination-only
    definition can end without swallowing the following physical line.
    """

    while cursor < len(text) and text[cursor] in " \t":
        cursor += 1
    line_start: int | None = None
    if cursor < len(text) and text[cursor] in "\r\n":
        line_start = cursor
        if text[cursor] == "\r" and cursor + 1 < len(text) and text[cursor + 1] == "\n":
            cursor += 2
        else:
            cursor += 1
        while cursor < len(text) and text[cursor] in " \t":
            cursor += 1
    return cursor, line_start


def _reference_definition_syntax_end(
    text: str,
    start: int,
    escaped: list[bool],
) -> int | None:
    """Return the end of one CommonMark-shaped reference definition."""

    cursor, before_destination_line = _consume_optional_reference_spacing(
        text,
        start,
    )
    if cursor >= len(text) or (
        before_destination_line is not None
        and cursor == len(text)
    ):
        return None

    if text[cursor] == "<" and not escaped[cursor]:
        cursor += 1
        while cursor < len(text):
            character = text[cursor]
            if character in "\r\n" or (
                character == "<" and not escaped[cursor]
            ):
                return None
            if character == ">" and not escaped[cursor]:
                cursor += 1
                break
            cursor += 1
        else:
            return None
    else:
        destination_start = cursor
        depth = 0
        while cursor < len(text):
            character = text[cursor]
            if escaped[cursor]:
                cursor += 1
                continue
            if character == "(":
                depth += 1
            elif character == ")":
                if depth == 0:
                    break
                depth -= 1
            elif character in " \t\r\n":
                break
            elif ord(character) < 0x20 or character == "<":
                return None
            cursor += 1
        if cursor == destination_start or depth:
            return None

    destination_end = cursor
    separator_start = cursor
    cursor, separator_line_start = _consume_optional_reference_spacing(text, cursor)
    if cursor >= len(text):
        return destination_end
    if text[cursor] not in {'"', "'", "("}:
        if separator_line_start is not None:
            return destination_end
        if text[cursor] in "\r\n":
            return destination_end
        return None
    if cursor == separator_start:
        return None

    opener = text[cursor]
    closer = ")" if opener == "(" else opener
    cursor += 1
    after_line_ending = False
    while cursor < len(text):
        character = text[cursor]
        if character == closer and not escaped[cursor]:
            cursor += 1
            break
        if character in "\r\n":
            if after_line_ending:
                return None
            after_line_ending = True
            if (
                character == "\r"
                and cursor + 1 < len(text)
                and text[cursor + 1] == "\n"
            ):
                cursor += 1
        elif after_line_ending and character not in " \t":
            after_line_ending = False
        cursor += 1
    else:
        return None

    while cursor < len(text) and text[cursor] in " \t":
        cursor += 1
    if cursor == len(text):
        return cursor
    if text[cursor] in "\r\n":
        return cursor
    return None


def _protect_inline_links(
    text: str,
    protected: list[bool],
    escaped: list[bool],
) -> int:
    """Protect inline destinations and return deterministic scan operations.

    The returned count covers cursor visits and bracket-state transitions. It
    is intentionally private test evidence that the nested-label state machine
    performs a bounded number of operations per input character.
    """

    # Inline link/image destinations and optional titles are syntax, not text.
    # A bare ``](`` is ordinary text: require an actual unescaped bracket
    # opener, and do not accept an outer link that already contains a link.
    tracker = _InlineLinkTracker()
    syntax_index = _InlineLinkSyntaxIndex(text, escaped)
    scan_operations = 0
    cursor = 0
    while cursor < len(text):
        scan_operations += 1
        if protected[cursor] or escaped[cursor]:
            cursor += 1
            continue
        if text[cursor] == "[":
            is_image = (
                cursor > 0
                and text[cursor - 1] == "!"
                and not escaped[cursor - 1]
                and not protected[cursor - 1]
            )
            tracker.open(is_image=is_image)
            cursor += 1
            continue
        if text[cursor] != "]" or not tracker:
            cursor += 1
            continue
        is_image, contains_link = tracker.close()
        if (
            contains_link
            or cursor + 1 >= len(text)
            or text[cursor + 1] != "("
            or escaped[cursor + 1]
            or protected[cursor + 1]
        ):
            cursor += 1
            continue
        end = _inline_link_syntax_end(
            text,
            cursor + 2,
            escaped,
            syntax_index=syntax_index,
        )
        if end is None:
            cursor += 1
            continue
        _mark(protected, cursor + 1, end)
        scan_operations += end - (cursor + 1)
        if not is_image:
            tracker.record_non_image_link()
        cursor = end
    return (
        scan_operations
        + tracker.operation_count
        + syntax_index.operation_count
    )


def _protect_inline_syntax(
    text: str,
    protected: list[bool],
    escaped: list[bool],
) -> None:
    """Protect syntax regions where Markdown emphasis is not interpreted."""

    _protect_angle_syntax(text, protected, escaped)

    _protect_inline_links(text, protected, escaped)

    # Reference definitions keep both a same-line or multiline destination and
    # a valid same-line, next-line, or multiline title opaque.
    definition_re = re.compile(
        r"(?:(?: {0,3}>[ \t]?)+)?"
        r"(?: {0,3}(?:[*+-]|\d{1,9}[.)])[ \t]+)?"
        r" {0,3}(?P<label>\[(?:\\.|[^\[\]\r\n]){1,999}\]):"
    )
    definition_cursor = 0
    while definition_cursor < len(text):
        match = definition_re.match(text, definition_cursor)
        if match is None:
            break
        label_start = match.start("label")
        if escaped[label_start]:
            break
        end = _reference_definition_syntax_end(text, match.end(), escaped)
        if end is None:
            break
        _mark(protected, match.end(), end)
        line_cursor = end
        while line_cursor < len(text) and text[line_cursor] not in "\r\n":
            line_cursor += 1
        if line_cursor == len(text):
            break
        if (
            text[line_cursor] == "\r"
            and line_cursor + 1 < len(text)
            and text[line_cursor + 1] == "\n"
        ):
            definition_cursor = line_cursor + 2
        else:
            definition_cursor = line_cursor + 1

    # GFM bare URI autolinks also keep literal tildes in their destination.
    for match in _BARE_URI_RE.finditer(text):
        end = match.end()
        while end > match.start() and text[end - 1] in "?!.,:*_~":
            end -= 1
        _mark(protected, match.start(), end)


def _protect_angle_syntax(
    text: str,
    protected: list[bool],
    escaped: list[bool],
) -> int:
    """Protect autolink/HTML regions with a bounded linear angle scan."""

    if "<" not in text:
        return len(text)

    generic_closes, operations = _generic_angle_close_indexes(text)
    special_ends, special_operations = _special_angle_end_indexes(text)
    operations += special_operations
    cursor = 0
    while cursor < len(text):
        operations += 1
        if protected[cursor]:
            cursor += 1
            continue
        if text[cursor] == "<" and not escaped[cursor]:
            end = _angle_syntax_end(
                text,
                cursor,
                generic_close=generic_closes.get(cursor),
                special_end=special_ends.get(cursor),
            )
            if end is not None:
                _mark(protected, cursor, end)
                operations += end - cursor
                cursor = end
                continue
        cursor += 1
    return operations


def _is_unicode_punctuation(character: str | None) -> bool:
    if character is None:
        return False
    category = unicodedata.category(character)
    return category.startswith("P") or category.startswith("S")


def _is_commonmark_whitespace(character: str | None) -> bool:
    if character is None:
        return True
    return character in "\t\n\f\r" or unicodedata.category(character) == "Zs"


def _flanking(text: str, start: int, end: int) -> tuple[bool, bool]:
    before = text[start - 1] if start > 0 else None
    after = text[end] if end < len(text) else None
    before_whitespace = _is_commonmark_whitespace(before)
    after_whitespace = _is_commonmark_whitespace(after)
    before_punctuation = _is_unicode_punctuation(before)
    after_punctuation = _is_unicode_punctuation(after)
    left_flanking = (not after_whitespace) and (
        (not after_punctuation) or before_whitespace or before_punctuation
    )
    right_flanking = (not before_whitespace) and (
        (not before_punctuation) or after_whitespace or after_punctuation
    )
    return left_flanking, right_flanking


def _matching_delimiters(runs: list[_DelimiterRun]) -> set[int]:
    """Pair same-marker runs using their CommonMark-style flanking roles."""

    matched: set[int] = set()
    openers: list[int] = []
    for index, run in enumerate(runs):
        if run.can_close and openers:
            opener_index = openers.pop()
            matched.add(opener_index)
            matched.add(index)
            continue
        if run.can_open:
            openers.append(index)
    return matched


def _project_paragraph(text: str) -> tuple[str, dict[str, int]]:
    escaped = _backslash_escape_mask(text)
    protected, inline_code_spans = _inline_code_mask(text, escaped)
    _protect_inline_syntax(text, protected, escaped)
    escape_positions: set[int] = set()
    tilde_runs: list[_DelimiterRun] = []
    strong_runs: list[_DelimiterRun] = []
    existing_escapes = 0

    for index, character in enumerate(text):
        if protected[index]:
            continue
        if character.isascii() and not character.isalnum() and not character.isspace():
            if escaped[index]:
                existing_escapes += 1

    cursor = 0
    while cursor < len(text):
        if protected[cursor]:
            cursor += 1
            continue
        marker = text[cursor]
        if marker not in {"~", "*"} or escaped[cursor]:
            cursor += 1
            continue
        run_end = cursor + 1
        while (
            run_end < len(text)
            and text[run_end] == marker
            and not protected[run_end]
            and not escaped[run_end]
        ):
            run_end += 1
        length = run_end - cursor
        if marker == "~" and length == 1:
            escape_positions.add(cursor)
        elif length == 2 or (marker == "*" and length > 2):
            can_open, can_close = _flanking(text, cursor, run_end)
            run = _DelimiterRun(cursor, run_end, marker, can_open, can_close)
            if marker == "~":
                tilde_runs.append(run)
            else:
                strong_runs.append(run)
        cursor = run_end

    matched_tildes = _matching_delimiters(tilde_runs)
    matched_strong = _matching_delimiters(strong_runs)
    unmatched_tilde_runs = 0
    unmatched_strong_runs = 0
    for index, run in enumerate(tilde_runs):
        if index not in matched_tildes:
            unmatched_tilde_runs += 1
            escape_positions.update(range(run.start, run.end))
    for index, run in enumerate(strong_runs):
        if index not in matched_strong:
            # Escape only the exact unmatched ``**`` form the projection was
            # introduced to repair. Longer CommonMark emphasis runs can carry
            # a valid strong pair plus a remaining marker; preserving them is
            # safer than destructively guessing at rule-of-three semantics.
            if run.end - run.start == 2:
                unmatched_strong_runs += 1
                escape_positions.update(range(run.start, run.end))

    projected_parts: list[str] = []
    for index, character in enumerate(text):
        if index in escape_positions:
            projected_parts.append("\\")
        projected_parts.append(character)

    return "".join(projected_parts), {
        "single_tilde_count": sum(1 for position in escape_positions if text[position] == "~")
        - (2 * unmatched_tilde_runs),
        "unpaired_double_tilde_run_count": unmatched_tilde_runs,
        "unpaired_strong_run_count": unmatched_strong_runs,
        "intentional_strikethrough_pair_count": len(matched_tildes) // 2,
        "intentional_strong_pair_count": len(matched_strong) // 2,
        "inline_code_span_count": inline_code_spans,
        "existing_backslash_escape_count": existing_escapes,
        "inserted_backslash_count": len(escape_positions),
    }


def _empty_counts() -> dict[str, int]:
    return {
        "single_tilde_count": 0,
        "unpaired_double_tilde_run_count": 0,
        "unpaired_strong_run_count": 0,
        "intentional_strikethrough_pair_count": 0,
        "intentional_strong_pair_count": 0,
        "inline_code_span_count": 0,
        "fenced_code_block_count": 0,
        "indented_code_line_count": 0,
        "existing_backslash_escape_count": 0,
        "inserted_backslash_count": 0,
    }


def _add_counts(target: dict[str, int], additions: dict[str, int]) -> None:
    for key, value in additions.items():
        target[key] += value


def _raw_html_block_open(line: str, *, paragraph_open: bool) -> _RawHtmlBlockState | None:
    """Recognize CommonMark raw HTML block starts without parsing their bytes."""

    payload, container = _container_open_payload(line)
    lowered = payload.casefold()
    for tag in ("script", "pre", "style", "textarea"):
        if re.match(rf"<{tag}(?:[ \t>]|$)", lowered):
            terminator = f"</{tag}>"
            return _RawHtmlBlockState(
                terminator=None if terminator in lowered else terminator,
                container=container,
            )
    for prefix, terminator in (
        ("<!--", "-->"),
        ("<?", "?>"),
    ):
        if lowered.startswith(prefix):
            return _RawHtmlBlockState(
                terminator=None if terminator in lowered else terminator,
                container=container,
            )
    if payload.startswith("<![CDATA["):
        return _RawHtmlBlockState(
            terminator=None if "]]>" in payload else "]]>",
            container=container,
        )
    if re.match(r"<![A-Z]", payload):
        return _RawHtmlBlockState(
            terminator=None if ">" in payload else ">",
            container=container,
        )

    tag_match = re.match(r"</?([A-Za-z][A-Za-z0-9-]*)(?:[ \t/>]|$)", payload)
    if tag_match and tag_match.group(1).casefold() in _RAW_HTML_BLOCK_TAGS:
        return _RawHtmlBlockState(
            terminator=None,
            until_blank=True,
            container=container,
        )

    # CommonMark type 7 may not interrupt a paragraph and requires a complete
    # standalone tag line.
    if not paragraph_open and _HTML_TAG_RE.fullmatch(payload.strip(" \t")):
        return _RawHtmlBlockState(
            terminator=None,
            until_blank=True,
            container=container,
        )
    return None


def project_wom_safe_markdown(source: str) -> dict[str, Any]:
    """Return a read-only GFM-safe display projection and content-free metadata.

    ``source`` remains the canonical value.  The returned ``text`` is a derived
    human-view projection only.  SHA-256 values bind both strings without
    exposing source excerpts, filenames, paths, or other private fields.
    """

    if not isinstance(source, str):
        raise TypeError("source must be str")

    counts = _empty_counts()
    output: list[str] = []
    paragraph: list[str] = []
    paragraph_container: tuple[_ContainerToken, ...] | None = None
    fence_state: _FenceState | None = None
    raw_html_state: _RawHtmlBlockState | None = None

    def flush_paragraph() -> None:
        nonlocal paragraph_container
        if not paragraph:
            return
        projected, paragraph_counts = _project_paragraph("".join(paragraph))
        output.append(projected)
        _add_counts(counts, paragraph_counts)
        paragraph.clear()
        paragraph_container = None

    def append_standalone_inline_block(line: str) -> None:
        projected, block_counts = _project_paragraph(line)
        output.append(projected)
        _add_counts(counts, block_counts)

    for line in _physical_lines_keepends(source):
        while True:
            if raw_html_state is not None:
                payload = _container_continuation_payload(
                    line,
                    raw_html_state.container,
                )
                if payload is None:
                    raw_html_state = None
                    continue
                output.append(line)
                lowered = payload.casefold()
                if (
                    raw_html_state.until_blank and _is_blank_payload(payload)
                ) or (
                    raw_html_state.terminator is not None
                    and raw_html_state.terminator in lowered
                ):
                    raw_html_state = None
                break

            if fence_state is not None:
                payload = _container_continuation_payload(
                    line,
                    fence_state.container,
                )
                if payload is None:
                    # A quote/list container ending also ends its unclosed
                    # fenced block. Reprocess this line in the outer context.
                    fence_state = None
                    continue
                output.append(line)
                if _fence_close(
                    payload,
                    fence_state.marker,
                    fence_state.minimum_length,
                ):
                    fence_state = None
                break

            raw_html = _raw_html_block_open(
                line,
                paragraph_open=bool(paragraph),
            )
            if raw_html is not None:
                flush_paragraph()
                output.append(line)
                if raw_html.terminator is not None or raw_html.until_blank:
                    raw_html_state = raw_html
                break

            fence = _fence_open(line)
            if fence is not None:
                flush_paragraph()
                output.append(line)
                fence_state = fence
                counts["fenced_code_block_count"] += 1
                break

            if _is_indented_code_line(line) and not paragraph:
                output.append(line)
                counts["indented_code_line_count"] += 1
                break

            if _is_blank_line(line):
                flush_paragraph()
                output.append(line)
                break

            payload, current_container = _container_open_payload(line)
            atx_heading = _ATX_HEADING_RE.match(payload) is not None
            thematic_break = _THEMATIC_BREAK_RE.fullmatch(payload) is not None
            if paragraph:
                current_list_tokens = [
                    token
                    for token in current_container
                    if token.kind == "list"
                ]
                paragraph_list_tokens = [
                    token
                    for token in (paragraph_container or ())
                    if token.kind == "list"
                ]
                same_ordered_list_family = bool(
                    current_list_tokens
                    and paragraph_list_tokens
                    and current_list_tokens[-1].list_marker
                    and paragraph_list_tokens[-1].list_marker
                    and current_list_tokens[-1].list_marker[:-1].isdigit()
                    and paragraph_list_tokens[-1].list_marker[:-1].isdigit()
                    and current_list_tokens[-1].list_marker[-1]
                    == paragraph_list_tokens[-1].list_marker[-1]
                )
                starts_new_list_item = bool(current_list_tokens) and (
                    same_ordered_list_family
                    or any(
                        token.interrupts_paragraph
                        for token in current_list_tokens
                    )
                )
                non_interrupting_list_marker = bool(
                    current_list_tokens
                ) and not starts_new_list_item
                if atx_heading or starts_new_list_item:
                    flush_paragraph()
                elif current_container:
                    container_lazy_prefix = bool(
                        paragraph_container
                        and len(current_container) < len(paragraph_container)
                        and paragraph_container[: len(current_container)]
                        == current_container
                        and all(
                            token.kind in {"quote", "list"}
                            for token in paragraph_container[
                                len(current_container) :
                            ]
                        )
                    )
                    if (
                        not non_interrupting_list_marker
                        and current_container != paragraph_container
                        and not container_lazy_prefix
                    ):
                        flush_paragraph()
                elif paragraph_container:
                    continuation = _container_continuation_payload(
                        line,
                        paragraph_container,
                    )
                    container_lazy_continuation = all(
                        token.kind in {"quote", "list"}
                        for token in paragraph_container
                    )
                    if continuation is None and not container_lazy_continuation:
                        flush_paragraph()

            if atx_heading:
                flush_paragraph()
                append_standalone_inline_block(line)
                break

            if (
                paragraph
                and _SETEXT_UNDERLINE_RE.fullmatch(payload)
                and (
                    not paragraph_container
                    or current_container == paragraph_container
                )
            ):
                paragraph.append(line)
                flush_paragraph()
                break

            if thematic_break:
                flush_paragraph()
                output.append(line)
                break

            if not paragraph:
                paragraph_container = current_container
            paragraph.append(line)
            break

    flush_paragraph()
    projected_text = "".join(output)
    metadata: dict[str, Any] = {
        "schema": WOM_SAFE_MARKDOWN_DISPLAY_SCHEMA,
        "profile": "wom_safe_markdown",
        "display_only": True,
        "canonical_source_unchanged": True,
        "changed": projected_text != source,
        "source_sha256": _sha256_text(source),
        "projected_sha256": _sha256_text(projected_text),
        "counts": counts,
    }
    return {"text": projected_text, "metadata": metadata}


__all__ = ["WOM_SAFE_MARKDOWN_DISPLAY_SCHEMA", "project_wom_safe_markdown"]
