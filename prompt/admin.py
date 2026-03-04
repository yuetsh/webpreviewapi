from django.contrib import admin
from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("role", "content", "code_html", "code_css", "code_js", "created")


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("user", "task", "is_active", "created")
    list_filter = ("is_active",)
    inlines = [MessageInline]
