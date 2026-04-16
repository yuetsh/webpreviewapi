from typing import Optional
from uuid import UUID
from ninja import Schema


class MessageOut(Schema):
    id: int
    role: str
    source: str
    content: str
    code_html: Optional[str] = None
    code_css: Optional[str] = None
    code_js: Optional[str] = None
    prompt_level: Optional[int] = None
    created: str


class ConversationOut(Schema):
    id: UUID
    user_id: int
    username: str
    task_id: int
    task_title: str
    is_active: bool
    message_count: int
    created: str

    @staticmethod
    def from_conv(conv):
        return {
            "id": conv.id,
            "user_id": conv.user_id,
            "username": conv.user.username,
            "task_id": conv.task_id,
            "task_title": conv.task.title,
            "is_active": conv.is_active,
            "message_count": conv.messages.count(),
            "created": conv.created.isoformat(),
        }
