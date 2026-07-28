from django.contrib import admin
from django.urls import include, path, re_path

from accounts.media import media_serve

urlpatterns = [
    path("", include("accounts.urls")),
    path("admin/", admin.site.urls),
    path("api/", include("catalog.urls")),
    path("", include("community.urls")),
    # Closed community: certificates staff-only, all other media members-only
    re_path(r"^media/(?P<path>.*)$", media_serve),
]

admin.site.site_header = "קטלוג המספרות של ישראל — ניהול"
admin.site.site_title = "קטלוג המספרות"
admin.site.index_title = "לוח בקרה"
