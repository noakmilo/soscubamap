import json
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request
from flask_login import current_user, login_required

from app.extensions import db
from app.models.post import Post
from app.models.category import Category
from app.models.post_revision import PostRevision
from app.models.post_edit_request import PostEditRequest
from app.models.media import Media
from app.models.repressor import Repressor, RepressorEditRequest, RepressorSubmission
from app.services.media_upload import media_json_from_post, parse_media_json
from app.services.repressor_submissions import materialize_repressor_submission
from app.services.repressor_edits import apply_repressor_edit_request, snapshot_repressor
from app.services.location_names import canonicalize_location_names
from app.services.authz import role_required
from . import moderation_bp


@moderation_bp.route("/")
@login_required
@role_required("moderador", "administrador")
def dashboard():
    pending = Post.query.filter_by(status="pending").order_by(Post.created_at.desc()).all()
    pending_edits = PostEditRequest.query.filter_by(status="pending").order_by(PostEditRequest.created_at.desc()).all()
    pending_repressor_submissions = (
        RepressorSubmission.query.filter_by(status="pending")
        .order_by(RepressorSubmission.created_at.desc())
        .all()
    )
    pending_repressor_edits = (
        RepressorEditRequest.query.filter_by(status="pending")
        .order_by(RepressorEditRequest.created_at.desc())
        .all()
    )
    return render_template(
        "moderation/dashboard.html",
        pending=pending,
        pending_edits=pending_edits,
        pending_repressor_submissions=pending_repressor_submissions,
        pending_repressor_edits=pending_repressor_edits,
    )


def _has_repressor_changes(repressor: Repressor, edit: RepressorEditRequest) -> bool:
    current_province, current_municipality = canonicalize_location_names(
        repressor.province_name,
        repressor.municipality_name,
    )
    candidate_province, candidate_municipality = canonicalize_location_names(
        edit.province_name,
        edit.municipality_name,
    )
    if (repressor.name or "") != (edit.name or ""):
        return True
    if (repressor.lastname or "") != (edit.lastname or ""):
        return True
    if (repressor.nickname or "") != (edit.nickname or ""):
        return True
    if (repressor.institution_name or "") != (edit.institution_name or ""):
        return True
    if (repressor.campus_name or "") != (edit.campus_name or ""):
        return True
    if (current_province or "") != (candidate_province or ""):
        return True
    if (current_municipality or "") != (candidate_municipality or ""):
        return True
    if (repressor.testimony or "") != (edit.testimony or ""):
        return True
    if (repressor.image_url or "") != (edit.image_url or ""):
        return True
    if sorted([item.name for item in repressor.crimes if item.name]) != sorted(edit.crimes_list):
        return True
    if sorted([item.name for item in repressor.types if item.name]) != sorted(edit.types_list):
        return True
    return False


@moderation_bp.route("/aprobar/<int:post_id>", methods=["POST"])
@login_required
@role_required("moderador", "administrador")
def approve(post_id):
    post = Post.query.get_or_404(post_id)
    post.status = "approved"
    db.session.commit()
    flash("Reporte aprobado.", "success")
    if request.args.get("modal") == "1":
        return render_template("map/edit_success.html", payload={"status": "approved"})
    return redirect(url_for("moderation.dashboard"))


@moderation_bp.route("/rechazar/<int:post_id>", methods=["POST"])
@login_required
@role_required("moderador", "administrador")
def reject(post_id):
    post = Post.query.get_or_404(post_id)
    post.status = "rejected"
    db.session.commit()
    flash("Reporte rechazado.", "success")
    if request.args.get("modal") == "1":
        return render_template("map/edit_success.html", payload={"status": "rejected"})
    return redirect(url_for("moderation.dashboard"))


@moderation_bp.route("/ediciones/<int:edit_id>/aprobar", methods=["POST"])
@login_required
@role_required("moderador", "administrador")
def approve_edit(edit_id):
    edit = PostEditRequest.query.get_or_404(edit_id)
    post = Post.query.get_or_404(edit.post_id)

    revision = PostRevision(
        post_id=post.id,
        editor_id=edit.editor_id,
        editor_label=edit.editor_label,
        reason=edit.reason,
        title=post.title,
        description=post.description,
        latitude=post.latitude,
        longitude=post.longitude,
        address=post.address,
        province=post.province,
        municipality=post.municipality,
        movement_at=post.movement_at,
        repressor_name=post.repressor_name,
        other_type=post.other_type,
        category_id=post.category_id,
        polygon_geojson=post.polygon_geojson,
        links_json=post.links_json,
        media_json=media_json_from_post(post),
    )
    db.session.add(revision)

    post.title = edit.title
    post.description = edit.description
    post.latitude = edit.latitude
    post.longitude = edit.longitude
    post.address = edit.address
    post.province = edit.province
    post.municipality = edit.municipality
    post.movement_at = edit.movement_at
    post.repressor_name = edit.repressor_name
    post.other_type = edit.other_type
    if edit.category_id:
        post.category_id = edit.category_id
    post.polygon_geojson = edit.polygon_geojson
    post.links_json = edit.links_json
    if edit.media_json:
        media_items = parse_media_json(edit.media_json)
        Media.query.filter_by(post_id=post.id).delete()
        for item in media_items:
            db.session.add(
                Media(
                    post_id=post.id,
                    file_url=item.get("url"),
                    caption=(item.get("caption") or None),
                )
            )

    edit.status = "approved"
    db.session.commit()
    flash("Edición aprobada.", "success")
    if request.args.get("modal") == "1":
        return render_template("map/edit_success.html", payload={"status": "approved"})
    return redirect(url_for("moderation.dashboard"))


@moderation_bp.route("/ediciones/<int:edit_id>/rechazar", methods=["POST"])
@login_required
@role_required("moderador", "administrador")
def reject_edit(edit_id):
    edit = PostEditRequest.query.get_or_404(edit_id)
    rejection_reason = request.form.get("rejection_reason", "").strip()
    if not rejection_reason:
        flash("Debes indicar un motivo de rechazo.", "error")
        if request.args.get("modal") == "1":
            return redirect(url_for("moderation.edit_detail", edit_id=edit.id, modal=1))
        return redirect(url_for("moderation.edit_detail", edit_id=edit.id))
    edit.rejection_reason = rejection_reason
    edit.status = "rejected"
    db.session.commit()
    flash("Edición rechazada.", "success")
    if request.args.get("modal") == "1":
        return render_template("map/edit_success.html", payload={"status": "rejected"})
    return redirect(url_for("moderation.dashboard"))


@moderation_bp.route("/ediciones/<int:edit_id>")
@login_required
@role_required("moderador", "administrador")
def edit_detail(edit_id):
    edit = PostEditRequest.query.get_or_404(edit_id)
    post = Post.query.get_or_404(edit.post_id)
    edit_category = None
    if edit.category_id:
        edit_category = Category.query.get(edit.category_id)
    links = []
    if edit.links_json:
        try:
            links = json.loads(edit.links_json)
        except Exception:
            links = []
    media_items = []
    if edit.media_json:
        media_items = parse_media_json(edit.media_json)
    return render_template(
        "moderation/edit_detail.html",
        edit=edit,
        post=post,
        edit_category=edit_category,
        links=links,
        media_items=media_items,
    )


@moderation_bp.route("/represores/<int:submission_id>/aprobar", methods=["POST"])
@login_required
@role_required("moderador", "administrador")
def approve_repressor_submission(submission_id):
    submission = RepressorSubmission.query.get_or_404(submission_id)
    if submission.status == "approved":
        flash("La propuesta ya estaba aprobada.", "warning")
        return redirect(url_for("moderation.dashboard"))
    try:
        reviewer_id = current_user.id if current_user.is_authenticated else None
        repressor = materialize_repressor_submission(
            submission,
            reviewer_id=reviewer_id,
        )
        db.session.commit()
        flash(f"Represor aprobado y agregado al catálogo: {repressor.full_name}.", "success")
    except Exception:
        db.session.rollback()
        flash("No se pudo aprobar la propuesta de represor.", "error")
    return redirect(url_for("moderation.dashboard"))


@moderation_bp.route("/represores/<int:submission_id>/rechazar", methods=["POST"])
@login_required
@role_required("moderador", "administrador")
def reject_repressor_submission(submission_id):
    submission = RepressorSubmission.query.get_or_404(submission_id)
    if submission.status == "rejected":
        flash("La propuesta ya estaba rechazada.", "warning")
        return redirect(url_for("moderation.dashboard"))

    submission.status = "rejected"
    submission.reviewed_at = datetime.utcnow()
    submission.reviewer_id = current_user.id if current_user.is_authenticated else None
    submission.rejection_reason = request.form.get("reason", "").strip() or None
    db.session.commit()
    flash("Propuesta de represor rechazada.", "success")
    return redirect(url_for("moderation.dashboard"))


@moderation_bp.route("/represores/ediciones/<int:edit_id>")
@login_required
@role_required("moderador", "administrador")
def repressor_edit_detail(edit_id):
    edit = RepressorEditRequest.query.get_or_404(edit_id)
    repressor = Repressor.query.get_or_404(edit.repressor_id)
    return render_template(
        "moderation/repressor_edit_detail.html",
        edit=edit,
        repressor=repressor,
    )


@moderation_bp.route("/represores/ediciones/<int:edit_id>/aprobar", methods=["POST"])
@login_required
@role_required("moderador", "administrador")
def approve_repressor_edit(edit_id):
    edit = RepressorEditRequest.query.get_or_404(edit_id)
    repressor = Repressor.query.get_or_404(edit.repressor_id)
    if edit.status == "approved":
        flash("La edición de represor ya estaba aprobada.", "warning")
        return redirect(url_for("moderation.dashboard"))

    try:
        has_changes = _has_repressor_changes(repressor, edit)
        if has_changes:
            snapshot_repressor(
                repressor,
                reason=edit.reason or "Aprobación de edición",
                editor_id=edit.editor_id,
                editor_label=edit.editor_label,
                payload={
                    "edit_request_id": edit.id,
                    "edit_kind": edit.edit_kind,
                    "source": "moderation_approved",
                },
            )
            apply_repressor_edit_request(repressor, edit)

        edit.status = "approved"
        edit.reviewed_at = datetime.utcnow()
        edit.reviewer_id = current_user.id if current_user.is_authenticated else None
        edit.rejection_reason = None
        db.session.commit()
        flash("Edición de represor aprobada.", "success")
    except Exception:
        db.session.rollback()
        flash("No se pudo aprobar la edición de represor.", "error")
    return redirect(url_for("moderation.dashboard"))


@moderation_bp.route("/represores/ediciones/<int:edit_id>/rechazar", methods=["POST"])
@login_required
@role_required("moderador", "administrador")
def reject_repressor_edit(edit_id):
    edit = RepressorEditRequest.query.get_or_404(edit_id)
    rejection_reason = request.form.get("rejection_reason", "").strip()
    if not rejection_reason:
        flash("Debes indicar un motivo de rechazo.", "error")
        return redirect(url_for("moderation.repressor_edit_detail", edit_id=edit.id))

    edit.status = "rejected"
    edit.reviewed_at = datetime.utcnow()
    edit.reviewer_id = current_user.id if current_user.is_authenticated else None
    edit.rejection_reason = rejection_reason
    db.session.commit()
    flash("Edición de represor rechazada.", "success")
    return redirect(url_for("moderation.dashboard"))
