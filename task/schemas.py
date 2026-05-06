from typing import Optional
from ninja import Schema, ModelSchema
from .models import Tutorial, Challenge


class TutorialSlim(Schema):
    display: int
    title: str
    is_public: bool


class TutorialAll(ModelSchema):
    class Meta:
        model = Tutorial
        fields = "__all__"


class TutorialIn(Schema):
    display: int
    title: str
    content: str
    is_public: bool = False


class ChallengeSlim(Schema):
    display: int
    title: str
    score: int
    pass_score: Optional[float] = None
    is_public: bool
    author_name: Optional[str] = None


class ChallengeDisplay(ChallengeSlim):
    submitted: bool


class ChallengeAll(ModelSchema):
    author_name: Optional[str] = None

    class Meta:
        model = Challenge
        fields = "__all__"


class ChallengeIn(Schema):
    display: int
    title: str
    content: str
    score: int = 0
    is_public: bool = False
