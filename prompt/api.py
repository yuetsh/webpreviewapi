import threading
from typing import List, Optional
from uuid import UUID
from ninja import Router
from ninja.errors import HttpError
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required

from django.db.models import Count
from .models import Conversation, Message
from .schemas import ConversationOut, MessageOut, PromptHistoryItemOut
from account.models import RoleChoices

router = Router()


@router.get("/conversations/", response=List[ConversationOut])
@login_required
def list_conversations(request, task_id: int = None, user_id: int = None):
    convs = Conversation.objects.select_related("user", "task").annotate(
        msg_count=Count("messages")
    )
    # Normal users can only see their own
    if request.user.role == "normal":
        convs = convs.filter(user=request.user)
    elif user_id:
        convs = convs.filter(user_id=user_id)
    if task_id:
        convs = convs.filter(task_id=task_id)
    convs = convs.order_by("-msg_count", "-created")
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
            "source": m.source,
            "content": m.content,
            "code_html": m.code_html,
            "code_css": m.code_css,
            "code_js": m.code_js,
            "prompt_level": m.prompt_level,
            "created": m.created.isoformat(),
        }
        for m in messages
    ]


@router.get("/history/{task_id}", response=List[PromptHistoryItemOut])
@login_required
def list_prompt_history(request, task_id: int):
    """
    获取当前用户在某任务下的历史对话轮次。

    只返回用户提示词和后一条 assistant 消息中的页面代码，用于前端渲染缩略图。
    """
    conversations = Conversation.objects.filter(
        user=request.user,
        task_id=task_id,
    ).prefetch_related("messages")

    items = []
    for conv in conversations:
        messages = list(conv.messages.all().order_by("created", "id"))
        for idx, user_msg in enumerate(messages):
            if user_msg.role != "user":
                continue

            assistant_msg = None
            for reply in messages[idx + 1:]:
                if reply.role == "user":
                    break
                if reply.role == "assistant":
                    assistant_msg = reply
                    break

            if not assistant_msg:
                continue

            items.append(
                (
                    user_msg.created,
                    {
                        "user_message_id": user_msg.id,
                        "assistant_message_id": assistant_msg.id,
                        "submission_id": assistant_msg.submission_id,
                        "source": user_msg.source,
                        "prompt": user_msg.content,
                        "prompt_level": user_msg.prompt_level,
                        "code_html": assistant_msg.code_html,
                        "code_css": assistant_msg.code_css,
                        "code_js": assistant_msg.code_js,
                        "created": user_msg.created.isoformat(),
                    },
                )
            )

    return [item for _, item in sorted(items, key=lambda row: row[0], reverse=True)]


@router.post("/conversations/{conversation_id}/classify")
@login_required
def classify_conversation(request, conversation_id: UUID, force: bool = False):
    """
    对对话中所有用户消息进行层级分类（仅管理员和超级管理员可操作，异步执行）
    """
    if request.user.role not in (RoleChoices.SUPER, RoleChoices.ADMIN):
        raise HttpError(403, "没有权限")

    get_object_or_404(Conversation, id=conversation_id)

    from submission.classifier import classify_conversation_messages
    threading.Thread(
        target=classify_conversation_messages,
        args=(conversation_id,),
        kwargs={"force": force},
        daemon=True,
    ).start()

    return {"message": "开始分类"}


@router.post("/classify-batch")
@login_required
def classify_batch(request, task_id: Optional[int] = None, force: bool = False):
    """
    批量分类所有（或指定任务）对话的用户消息层级（仅管理员和超级管理员，异步执行）
    """
    if request.user.role not in (RoleChoices.SUPER, RoleChoices.ADMIN):
        raise HttpError(403, "没有权限")

    qs = Message.objects.filter(role="user")
    if task_id:
        qs = qs.filter(conversation__task_id=task_id)
    if not force:
        qs = qs.filter(prompt_level__isnull=True)

    ids = list(qs.values_list("id", flat=True))

    from submission.classifier import classify_messages_batch
    threading.Thread(target=classify_messages_batch, args=(ids,), daemon=True).start()

    return {"message": f"开始分类 {len(ids)} 条消息", "count": len(ids)}


@router.delete("/messages/{message_id}/pair")
@login_required
def delete_message_pair(request, message_id: int):
    """
    Delete a message pair (assistant message + preceding user message) and
    any linked submission. Only the conversation owner can do this.
    """
    asst_msg = get_object_or_404(Message, id=message_id, role="assistant")

    if asst_msg.conversation.user != request.user and request.user.role != RoleChoices.SUPER:
        raise HttpError(403, "只能删除自己的消息")

    # Find the preceding user message
    user_msg = (
        Message.objects.filter(
            conversation=asst_msg.conversation,
            created__lt=asst_msg.created,
            role="user",
        )
        .order_by("-created")
        .first()
    )

    # Delete messages first, then submission
    submission_id = asst_msg.submission_id  # capture before deletion nulls it

    if user_msg:
        user_msg.delete()
    asst_msg.delete()

    submission_deleted = False
    if submission_id:
        from submission.models import Submission as SubmissionModel
        try:
            SubmissionModel.objects.filter(id=submission_id).delete()
            submission_deleted = True
        except Exception:
            pass

    return {"deleted": True, "submission_deleted": submission_deleted}
