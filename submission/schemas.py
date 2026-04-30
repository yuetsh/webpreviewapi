from typing import Optional, Literal
from ninja import Schema
from uuid import UUID


class SubmissionIn(Schema):
    task_id: int
    html: Optional[str] = None
    css: Optional[str] = None
    js: Optional[str] = None
    prompt: Optional[str] = None
    message_id: Optional[int] = None  # 关联的 assistant message pk


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
    flag: Optional[str] = None
    zone: Optional[str] = None
    submit_count: int = 0
    view_count: int = 0
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
    def resolve_submit_count(obj):
        return getattr(obj, "submit_count", None) or 0

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
    user_id: Optional[int] = None
    flag: Optional[Literal["red", "blue", "green", "yellow", "any"]] = None
    zone: Optional[Literal["featured", "low", "pending"]] = None
    score_min: Optional[float] = None
    score_max_exclusive: Optional[float] = None
    score_lt_threshold: Optional[float] = None
    ordering: Optional[str] = None
    grouped: Optional[bool] = True


class FlagIn(Schema):
    flag: Optional[Literal["red", "blue", "green", "yellow"]] = None


class UserTag(Schema):
    username: str
    classname: str


class SubmissionCountBucket(Schema):
    count_1: int       # users with exactly 1 submission
    count_2: int       # users with exactly 2 submissions
    count_3: int       # users with exactly 3 submissions
    count_4_plus: int  # users with 4+ submissions


class TopViewedItem(Schema):
    username: str
    classname: str
    view_count: int
    submission_id: UUID


class FlagStats(Schema):
    red: int
    blue: int
    green: int
    yellow: int


class TaskStatsOut(Schema):
    submitted_count: int
    unsubmitted_count: int
    average_score: Optional[float]
    unrated_count: int
    unsubmitted_users: list[UserTag]
    unrated_users: list[UserTag]
    submission_count_distribution: SubmissionCountBucket
    flag_stats: FlagStats
    classes: list[str]
    top_viewed: list[TopViewedItem]


class ShowcaseItemOut(Schema):
    submission_id: UUID
    username: str
    task_title: str
    task_display: int
    score: float
    view_count: int
    html: Optional[str] = None
    css: Optional[str] = None
    js: Optional[str] = None
    has_prompt_chain: bool


class AwardOut(Schema):
    id: int
    name: str
    description: str
    item_ordering: str
    items: list[ShowcaseItemOut]


class ShowcaseDetailOut(Schema):
    submission_id: UUID
    username: str
    task_title: str
    task_display: int
    score: float
    view_count: int
    html: Optional[str] = None
    css: Optional[str] = None
    js: Optional[str] = None
    awards: list[str]
    has_prompt_chain: bool


class PromptRoundOut(Schema):
    question: str
    source: str
    prompt_level: Optional[int] = None
    html: Optional[str] = None
    css: Optional[str] = None
    js: Optional[str] = None
