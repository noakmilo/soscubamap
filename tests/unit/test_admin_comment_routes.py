from app.extensions import db
from app.models.category import Category
from app.models.comment import Comment
from app.models.discussion_comment import DiscussionComment
from app.models.discussion_post import DiscussionPost
from app.models.post import Post
from app.models.role import Role
from app.models.user import User


def _login_admin(client, user_id: int) -> None:
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def _seed_admin(app) -> int:
    with app.app_context():
        admin_role = Role(name="administrador")
        admin_user = User(email="admin-comments@example.com")
        admin_user.set_password("test")
        admin_user.roles.append(admin_role)
        db.session.add_all([admin_role, admin_user])
        db.session.commit()
        return admin_user.id


def test_admin_report_comments_table_lists_rows(app, client):
    admin_id = _seed_admin(app)
    with app.app_context():
        category = Category(name="Categoria prueba", slug="categoria-prueba")
        author = User(email="autor-report@example.com")
        author.set_password("test")
        author.ensure_anon_code()
        post = Post(
            title="Reporte de prueba",
            description="Descripcion del reporte",
            latitude=23.1,
            longitude=-82.3,
            province="La Habana",
            municipality="Plaza",
            author=author,
            category=category,
            status="approved",
            is_anonymous=True,
        )
        comment = Comment(
            post=post,
            author=author,
            body="Comentario admin sobre reporte",
        )
        db.session.add_all([category, author, post, comment])
        db.session.commit()

    _login_admin(client, admin_id)
    response = client.get("/admin/reportes/comentarios")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Comentarios de reportes" in html
    assert "Reporte de prueba" in html
    assert "Comentario admin sobre reporte" in html


def test_admin_delete_report_comment(app, client):
    admin_id = _seed_admin(app)
    with app.app_context():
        category = Category(name="Categoria delete", slug="categoria-delete")
        author = User(email="autor-delete-report@example.com")
        author.set_password("test")
        post = Post(
            title="Reporte para borrar comentario",
            description="Detalle",
            latitude=22.2,
            longitude=-80.8,
            province="Cienfuegos",
            municipality="Cienfuegos",
            author=author,
            category=category,
            status="approved",
            is_anonymous=True,
        )
        comment = Comment(
            post=post,
            author=author,
            body="Comentario a eliminar en reporte",
        )
        db.session.add_all([category, author, post, comment])
        db.session.commit()
        comment_id = comment.id

    _login_admin(client, admin_id)
    response = client.post(
        f"/admin/reportes/comentarios/{comment_id}/eliminar",
        data={"next": "/admin/reportes/comentarios"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(Comment, comment_id) is None


def test_admin_discussion_comments_table_lists_rows(app, client):
    admin_id = _seed_admin(app)
    with app.app_context():
        post = DiscussionPost(
            title="Discusion de prueba",
            body="Contenido",
            body_html="<p>Contenido</p>",
            author_label="Anon-AAA111",
        )
        comment = DiscussionComment(
            post=post,
            body="Comentario en discusion",
            body_html="<p>Comentario en discusion</p>",
            author_label="Anon-BBB222",
        )
        db.session.add_all([post, comment])
        db.session.commit()

    _login_admin(client, admin_id)
    response = client.get("/admin/discusiones/comentarios")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Comentarios de discusiones" in html
    assert "Discusion de prueba" in html
    assert "Comentario en discusion" in html


def test_admin_delete_discussion_comment(app, client):
    admin_id = _seed_admin(app)
    with app.app_context():
        post = DiscussionPost(
            title="Discusion borrar comentario",
            body="Contenido",
            body_html="<p>Contenido</p>",
            author_label="Anon-CCC333",
        )
        comment = DiscussionComment(
            post=post,
            body="Comentario a eliminar en discusion",
            body_html="<p>Comentario a eliminar en discusion</p>",
            author_label="Anon-DDD444",
        )
        db.session.add_all([post, comment])
        db.session.commit()
        comment_id = comment.id

    _login_admin(client, admin_id)
    response = client.post(
        f"/admin/discusiones/comentarios/{comment_id}/eliminar",
        data={"next": "/admin/discusiones/comentarios"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(DiscussionComment, comment_id) is None
