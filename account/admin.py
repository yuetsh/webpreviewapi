from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


class AdminUser(UserAdmin):
    fieldsets = ((None, {"fields": ("username", "password", "role", "is_active")}),)
    list_display = ("username", "role", "is_active")
    list_filter = ("role", "is_active")
    search_fields = ("username",)


admin.site.register(User, AdminUser)
