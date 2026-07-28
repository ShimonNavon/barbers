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
        return _staff_serve(request, path)
    return _member_serve(request, path)
