from app import create_app
from app.extensions import db
from app.models.discussion_tag import DiscussionTag

DEFAULT_TAGS = [
    "anuncio",
    "ayuda",
    "inteligencia",
    "OSINT",
    "militar",
    "marina",
    "aire",
    "terrestre",
    "prisiones",
    "represion",
    "presos politicos",
    "policia",
    "DGI",
    "DSE",
]


def normalize(value: str) -> str:
    return " ".join(value.strip().lower().split())


def main():
    app = create_app()
    with app.app_context():
        created = 0
        for name in DEFAULT_TAGS:
            slug = normalize(name)
            exists = DiscussionTag.query.filter_by(slug=slug).first()
            if exists:
                continue
            db.session.add(DiscussionTag(name=name, slug=slug))
            created += 1
        db.session.commit()
        print(f"Etiquetas creadas: {created}")


if __name__ == "__main__":
    main()
