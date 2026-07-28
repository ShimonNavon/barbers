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
    if path.startswith("certificates/"):
        response = _staff_serve(request, path)
    else:
        response = _member_serve(request, path)
    # Cloudflare edge-caches image extensions by default; no-store keeps
    # authenticated media out of shared caches (else: auth bypass via cache)
    response["Cache-Control"] = "private, no-store"
    return response
