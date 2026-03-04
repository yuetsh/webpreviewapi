from typing import List
from uuid import UUID
from ninja import Router
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required

from .models import Conversation, Message
from .schemas import ConversationOut, MessageOut

router = Router()


@router.get("/conversations/", response=List[ConversationOut])
@login_required
def list_conversations(request, task_id: int = None, user_id: int = None):
    convs = Conversation.objects.select_related("user", "task")
    # Normal users can only see their own
    if request.user.role == "normal":
        convs = convs.filter(user=request.user)
    elif user_id:
        convs = convs.filter(user_id=user_id)
    if task_id:
        convs = convs.filter(task_id=task_id)
    return [ConversationOut.from_conv(c) for c in convs]


@router.get("/conversations/{conversation_id}/messages/", response=List[MessageOut])
@login_required
def list_messages(request, conversation_id: UUID):
    conv = get_object_or_404(Conversation, id=conversation_id)
    # Normal users can only see their own
    if request.user.role == "normal" and conv.user != request.user:
        return []
    messages = conv.messages.all()
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "code_html": m.code_html,
            "code_css": m.code_css,
            "code_js": m.code_js,
            "created": m.created.isoformat(),
        }
        for m in messages
    ]
