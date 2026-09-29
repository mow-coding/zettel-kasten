"""Lossless literal masking and conservative Notion container normalization.

Only balanced, recognized containers with actual content are converted. Masked
literal spans are restored byte-for-byte (including their line endings); no
placeholder is treated as recovered source content.
"""
import hashlib
from html.parser import HTMLParser
import re

_CONTAINERS = {"callout", "column_list", "column", "unknown:callout", "unknown:column_list", "unknown:column"}
_TAG = re.compile(r"<\s*(?P<close>/?)\s*(?P<name>[a-zA-Z_][a-zA-Z0-9_:.-]*)(?P<attrs>(?:\s+(?:[^<>\"']|\"[^\"]*\"|'[^']*')*)?)\s*(?P<self>/?)>")


def protected_spans(body):
    spans, offset, opened, fence_char, fence_length, fence_prefix = [], 0, None, None, 0, ""
    for line in body.splitlines(keepends=True):
        payload = re.sub(r"^\s*(?:(?:>\s*)+|(?:[-+*]|\d+[.)])\s+)", "", line)
        fence = re.match(r"^[ \t]*(`{3,}|~{3,})([^\r\n]*)", payload)
        prefix = line[:len(line) - len(payload) + fence.start(1)].strip() if fence else ""
        if opened is not None:
            if (fence and prefix == fence_prefix and fence.group(1)[0] == fence_char
                    and len(fence.group(1)) >= fence_length and not fence.group(2).strip()):
                spans.append((opened, offset + len(line)))
                opened = None
        elif fence:
            opened, fence_char, fence_length = offset, fence.group(1)[0], len(fence.group(1))
            fence_prefix = prefix
        offset += len(line)
    if opened is not None:
        spans.append((opened, len(body)))
    patterns = (
        r"(?s)<!--.*?(?:-->|\Z)", r"(?s)<\?.*?(?:\?>|\Z)", r"(?s)<!\[CDATA\[.*?(?:\]\]>|\Z)",
        r"(?is)<\s*(code|pre|script|style|textarea|xmp)\b[^>]*>.*?(?:</\s*\1\s*>|\Z)",
        # Reference destinations and their optional multiline titles are one
        # literal unit. Mask through its terminating blank line, not just the
        # definition's first line (which could expose a title to normalization).
        r"(?m)^[ \t]*\[[^\]\r\n]+\]:[^\r\n]*(?:(?:\r\n|\n)(?![ \t]*(?:\r?\n|\Z))[^\r\n]*)*(?:\r\n|\n|\Z)",
        r"(?m)^ {0,3}>[^\r\n]*(?:\r\n|\n|\Z)",
    )
    for pattern in patterns:
        spans.extend((match.start(), match.end()) for match in re.finditer(pattern, body))
    for match in re.finditer(r"(?s)(?<!`)(`+)(?!`)(.*?)\1(?!`)", body):
        spans.append((match.start(), match.end()))
    # A tag-looking string inside a quoted HTML attribute is data, not markup.
    for match in _TAG.finditer(body):
        if re.search(r"[\"'][^\"']*<[^\"']*[\"']", match.group("attrs")):
            spans.append((match.start(), match.end()))
    merged = []
    tables = [(match.start(), match.end()) for match in re.finditer(r"(?is)<table\b[^>]*>.*?</table\s*>", body)]
    # Keep unsafe table-cell constructs visible to the existing lossless table
    # validator; replacing a script/comment with an innocent token would make
    # that validator incorrectly approve moving it into a Markdown cell.
    spans = [(start, end) for start, end in spans if not any(left <= start and end <= right for left, right in tables)]
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


class _Attributes(HTMLParser):
    def handle_starttag(self, tag, attrs):
        self.values = attrs


def _attributes(token):
    parser = _Attributes(convert_charrefs=False)
    parser.values = None
    try:
        parser.feed(token)
        attrs = parser.values
        if attrs is None or len({name for name, _ in attrs}) != len(attrs):
            return None
        if any(name not in {"icon", "color"} or value is None or len(value) > 128 or
               any(char in value for char in "<>\r\n`") for name, value in attrs):
            return None
        return dict(attrs)
    except (ValueError, AssertionError):
        return None


def _containers(body, mask_tokens):
    """Transform outermost balanced trees, retaining malformed trees verbatim."""
    stack, candidates, malformed = [], [], set()
    for token in _TAG.finditer(body):
        name = token.group("name")
        if name not in _CONTAINERS:
            continue
        if token.group("self") or token.group(0).rstrip().endswith("/>"):
            malformed.add(name)
            continue
        if not token.group("close"):
            stack.append((token, []))
            continue
        if not stack or stack[-1][0].group("name") != name:
            malformed.add(name)
            continue
        opening, children = stack.pop()
        attrs = _attributes(opening.group(0))
        inner = body[opening.end():token.start()]
        valid = bool(inner.strip()) and attrs is not None and not any(marker in inner for marker in mask_tokens)
        if children:
            for start, end, replacement in reversed(children):
                inner = inner[:start - opening.end()] + replacement + inner[end - opening.end():]
        if valid and not any(match.group("name") in _CONTAINERS for match in _TAG.finditer(inner)):
            ending = "\r\n" if "\r\n" in inner else "\n"
            if name.endswith("callout"):
                visible = ((attrs.get("icon", "") + ending) if attrs.get("icon") else "") + inner.strip("\r\n")
                replacement = ending + "".join("> " + line for line in visible.splitlines(keepends=True)) + ending
            else:
                replacement = "\n" + inner.strip("\r\n") + "\n"
            change = (opening.start(), token.end(), replacement)
            if stack:
                stack[-1][1].append(change)
            else:
                candidates.append(change)
        else:
            malformed.add(name)
    malformed.update(token.group("name") for token, _children in stack)
    # Any unmatched opener may own later siblings. Never convert through it.
    if stack:
        earliest = min(token.start() for token, _children in stack)
        candidates = [row for row in candidates if row[1] <= earliest]
    normalized = body
    for start, end, replacement in reversed(candidates):
        normalized = normalized[:start] + replacement + normalized[end:]
    return normalized, len(candidates), sorted(malformed)


def normalize(body, *, bindings, legacy):
    spans = protected_spans(body)
    masked, replacements = body, {}
    for number, (start, end) in reversed(list(enumerate(spans))):
        seed = hashlib.sha256((body + str(number)).encode("utf-8")).hexdigest()
        marker = "WOMLITERAL" + seed + "END"
        while marker in body:
            marker += "X"
        replacements[marker] = body[start:end]
        masked = masked[:start] + marker + masked[end:]
    converted, container_count, unresolved = _containers(masked, replacements)
    result = legacy(converted, bindings=bindings)
    normalized = result["normalized_body"]
    for marker, literal in replacements.items():
        if normalized.count(marker) != 1:
            raise ValueError("markup_literal_mask_changed")
        normalized = normalized.replace(marker, literal)
    # Legacy errors restore its input. Restore all original bytes on a blocker;
    # no writer may claim complete normalization for an unresolved container.
    if result["blocker_codes"] or unresolved:
        normalized = body
    result.update(normalized_body=normalized, changed=normalized != body)
    result["counts"]["structural_container"] += container_count
    result["protected_span_count"] = len(spans)
    result["protected_spans_byte_preserved"] = True
    result["unresolved_container_names"] = unresolved
    if unresolved and "markup_container_source_or_structure_required" not in result["blocker_codes"]:
        result["blocker_codes"].append("markup_container_source_or_structure_required")
    if result["blocker_codes"]:
        result["applied_reference_bindings"] = []
    elif not result["changed"] and any(_TAG.search(literal) for literal in replacements.values()):
        # Preserve the existing explicit literal-only diagnostic. Mixed
        # documents can now normalize live siblings without editing literals.
        result["blocker_codes"].append("markup_protected_context_unsupported")
    return result
