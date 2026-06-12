from django.db.models import Count, Q
from .models import Conversation


def get_active_conversation(user, task_id):
    """Return the conversation with the most messages for this user+task, or None."""
    return (
        Conversation.objects.filter(user=user, task_id=task_id)
        .annotate(msg_count=Count("messages"))
        .order_by("-msg_count", "-created")
        .first()
    )


def get_or_create_active_conversation(user, task_id):
    conv = get_active_conversation(user, task_id)
    if not conv:
        conv = Conversation.objects.create(user=user, task_id=task_id)
    return conv


def get_preceding_user_message(asst_msg):
    """Return the user message immediately preceding an assistant message in its conversation."""
    return (
        asst_msg.conversation.messages.filter(role="user")
        .filter(
            Q(created__lt=asst_msg.created)
            | Q(created=asst_msg.created, id__lt=asst_msg.id)
        )
        .order_by("-created", "-id")
        .first()
    )
