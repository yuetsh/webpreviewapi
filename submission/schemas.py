from typing import Optional, Literal
from ninja import Schema
from uuid import UUID


class SubmissionIn(Schema):
    task_id: int
    html: Optional[str] = None
    css: Optional[str] = None
    js: Optional[str] = None


class SubmissionOut(Schema):
    id: UUID
    userid: int
    username: str
    task_id: int
    task_title: str
    task_type: Literal["tutorial", "challenge"]
    score: int
    html: Optional[str] = None
    css: Optional[str] = None
    js: Optional[str] = None
    created: str
    modified: str

    @staticmethod
    def list(submission):
        return {
            "id": submission.id,
            "userid": submission.user.id,
            "username": submission.user.username,
            "task_id": submission.task.id,
            "task_title": submission.task.title,
            "task_type": submission.task.task_type,
            "score": submission.score,
            "created": submission.created.isoformat(),
            "modified": submission.modified.isoformat(),
        }

    @staticmethod
    def get(submission):
        return {
            "id": submission.id,
            "userid": submission.user.id,
            "username": submission.user.username,
            "task_id": submission.task.id,
            "task_title": submission.task.title,
            "task_type": submission.task.task_type,
            "score": submission.score,
            "html": submission.html,
            "css": submission.css,
            "js": submission.js,
            "created": submission.created.isoformat(),
            "modified": submission.modified.isoformat(),
        }


class SubmissionScoreIn(Schema):
    score: int


class SubmissionScoreOut(Schema):
    id: UUID
    score: int


class SubmissionFilter(Schema):
    task_id: Optional[int] = None
    task_type: Optional[Literal["tutorial", "challenge"]] = None
    username: Optional[str] = None
