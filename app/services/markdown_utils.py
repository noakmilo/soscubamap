import markdown as md
import bleach


ALLOWED_TAGS = [
    "p",
    "br",
    "strong",
    "em",
    "u",
    "a",
    "ul",
    "ol",
    "li",
    "blockquote",
    "code",
    "pre",
]
ALLOWED_ATTRS = {
    "a": ["href", "title", "rel", "target"],
}


def render_markdown(text: str, allow_images: bool = False) -> str:
    raw = md.markdown(text or "", extensions=["extra", "sane_lists", "nl2br"])
    tags = list(ALLOWED_TAGS)
    attrs = dict(ALLOWED_ATTRS)
    if allow_images:
        tags.append("img")
        attrs["img"] = ["src", "alt", "title"]
    clean = bleach.clean(raw, tags=tags, attributes=attrs, strip=True)
    return clean
