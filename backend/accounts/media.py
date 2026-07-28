import posixpath

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.views.static import serve


@staff_member_required
def _staff_serve(request, path):
    return serve(request, path, document_root=settings.MEDIA_ROOT)


@login_required
def _member_serve(request, path):
    return serve(request, path, document_root=settings.MEDIA_ROOT)


def media_serve(request, path):
    """Closed community: no public media. Certificates carry personal
    documents — staff only. Everything else needs a logged-in member."""
    # Decide on the SAME path django.views.static.serve will resolve, or
    # './certificates/x' and 'avatars/../certificates/x' slip past the gate.
    resolved = posixpath.normpath(path.replace("\\", "/")).lstrip("/")
    if resolved.startswith("certificates/") or resolved == "certificates":
        response = _staff_serve(request, path)
    else:
        response = _member_serve(request, path)
    # Cloudflare edge-caches image extensions by default; no-store keeps
    # authenticated media out of shared caches (else: auth bypass via cache)
    response["Cache-Control"] = "private, no-store"
    # Never let an uploaded file render as a document on our own origin.
    if resolved.startswith("certificates/"):
        response["Content-Disposition"] = "attachment"
    return response
