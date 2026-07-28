from django.conf import settings
from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("catalog.urls")),
    # Uploaded certificates — staff-only (they contain personal documents),
    # viewed from the admin; tiny traffic, so serving via Django is fine
    # (whitenoise only covers static, not media).
    re_path(
        r"^media/(?P<path>.*)$",
        staff_member_required(serve),
        {"document_root": settings.MEDIA_ROOT},
    ),
]

admin.site.site_header = "קטלוג המספרות של ישראל — ניהול"
admin.site.site_title = "קטלוג המספרות"
admin.site.index_title = "לוח בקרה"
