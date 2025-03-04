from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from .models import User

admin.site.site_header = "前端开发网站管理"
admin.site.site_index = "前端开发网站管理"
admin.site.site_title = "前端开发网站管理"

admin.site.unregister(Group)


@admin.register(User)
class AdminAccount(UserAdmin):
    fieldsets = ((None, {"fields": ("username", "password", "role", "is_active")}),)
    add_fieldsets = (
        (
            None,
            {"fields": ("username", "password1", "password2", "role")},
        ),
    )
    list_display = ("username", "role", "is_active")
    list_filter = ("role", "is_active")
    search_fields = ("username",)
