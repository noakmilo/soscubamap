from app.extensions import db
from app.models.news_comment import NewsComment
from app.models.news_post import NewsPost
from app.models.role import Role
from app.models.user import User


def _login_admin(client, user_id: int) -> None:
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def _seed_admin(app) -> int:
    with app.app_context():
        admin_role = Role(name="administrador")
        admin_user = User(email="admin-news@example.com")
        admin_user.set_password("test")
        admin_user.roles.append(admin_role)
        db.session.add_all([admin_role, admin_user])
        db.session.commit()
        return admin_user.id


def test_news_index_lists_posts(app, client):
    with app.app_context():
        post = NewsPost(
            title="Noticia de prueba",
            slug="noticia-de-prueba",
            author_name="Equipo SOSCuba",
            summary="Resumen de prueba",
            body="Contenido",
            body_html="<p>Contenido</p>",
        )
        db.session.add(post)
        db.session.commit()

    response = client.get("/noticias")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Noticia de prueba" in html
    assert "Resumen de prueba" in html


def test_news_new_requires_admin(client):
    response = client.get("/noticias/new")
    assert response.status_code in (302, 401)


def test_admin_can_create_news_post(app, client):
    admin_id = _seed_admin(app)
    _login_admin(client, admin_id)

    response = client.post(
        "/noticias/new",
        data={
            "title": "Título con acentos",
            "author_name": "Autora",
            "summary": "Resumen manual",
            "body": "## Entrada\n\nContenido **importante**.",
        },
        follow_redirects=True,
    )

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Título con acentos" in html
    assert "Resumen manual" in html
    with app.app_context():
        post = NewsPost.query.filter_by(slug="titulo-con-acentos").first()
        assert post is not None
        assert "<strong>importante</strong>" in post.body_html


def test_news_detail_accepts_comment(app, client):
    with app.app_context():
        post = NewsPost(
            title="Noticia con comentarios",
            slug="noticia-con-comentarios",
            author_name="Equipo",
            summary="Resumen",
            body="Contenido",
            body_html="<p>Contenido</p>",
        )
        db.session.add(post)
        db.session.commit()
        post_id = post.id

    response = client.post(
        "/noticias/noticia-con-comentarios",
        data={
            "comment_nickname": "Lector",
            "comment_body": "Comentario **útil**",
        },
        follow_redirects=True,
    )

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Comentario agregado" in html
    with app.app_context():
        comment = NewsComment.query.filter_by(post_id=post_id).first()
        assert comment is not None
        assert "<strong>útil</strong>" in comment.body_html


def test_admin_news_panel_lists_post(app, client):
    admin_id = _seed_admin(app)
    with app.app_context():
        post = NewsPost(
            title="Noticia admin",
            slug="noticia-admin",
            author_name="Equipo",
            summary="Resumen",
            body="Contenido",
            body_html="<p>Contenido</p>",
        )
        db.session.add(post)
        db.session.commit()

    _login_admin(client, admin_id)
    response = client.get("/admin/noticias")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Noticia admin" in html
    assert "Editar" in html
