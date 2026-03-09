from typing import Optional, Literal
from ninja import Schema
from uuid import UUID


class SubmissionIn(Schema):
    task_id: int
    html: Optional[str] = None
    css: Optional[str] = None
    js: Optional[str] = None
    conversation_id: Optional[UUID] = None


class SubmissionOut(Schema):
    id: UUID
    userid: int
    username: str
    task_id: int
    task_display: int
    task_title: str
    task_type: Literal["tutorial", "challenge"]
    score: float
    my_score: int = 0
    html: Optional[str] = None
    css: Optional[str] = None
    js: Optional[str] = None
    conversation_id: Optional[UUID] = None
    flag: Optional[str] = None
    created: str
    modified: str

    @staticmethod
    def resolve_userid(obj):
        return obj.user.id

    @staticmethod
    def resolve_username(obj):
        return obj.user.username

    @staticmethod
    def resolve_task_id(obj):
        return obj.task.id

    @staticmethod
    def resolve_task_display(obj):
        return obj.task.display

    @staticmethod
    def resolve_task_title(obj):
        return obj.task.title

    @staticmethod
    def resolve_task_type(obj):
        return obj.task.task_type

    @staticmethod
    def resolve_my_score(obj):
        return getattr(obj, "my_score", None) or 0

    @staticmethod
    def resolve_created(obj):
        return obj.created.isoformat()

    @staticmethod
    def resolve_modified(obj):
        return obj.modified.isoformat()

    @staticmethod
    def get(submission, rating):
        return {
            "id": submission.id,
            "userid": submission.user.id,
            "username": submission.user.username,
            "task_id": submission.task.id,
            "task_display": submission.task.display,
            "task_title": submission.task.title,
            "task_type": submission.task.task_type,
            "score": submission.score,
            "my_score": rating.score if rating else 0,
            "html": submission.html,
            "css": submission.css,
            "js": submission.js,
            "conversation_id": submission.conversation_id,
            "flag": submission.flag,
            "created": submission.created.isoformat(),
            "modified": submission.modified.isoformat(),
        }


class RatingScoreIn(Schema):
    score: int


class SubmissionScoreOut(Schema):
    id: UUID
    score: float


class SubmissionFilter(Schema):
    task_id: Optional[int] = None
    task_type: Optional[Literal["tutorial", "challenge"]] = None
    username: Optional[str] = None
    flag: Optional[Literal["red", "blue", "green", "yellow"]] = None


class FlagIn(Schema):
    flag: Optional[Literal["red", "blue", "green", "yellow"]] = None
