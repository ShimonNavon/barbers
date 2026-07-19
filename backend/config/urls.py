from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("catalog.urls")),
]

admin.site.site_header = "קטלוג המספרות של ישראל — ניהול"
admin.site.site_title = "קטלוג המספרות"
admin.site.index_title = "לוח בקרה"
