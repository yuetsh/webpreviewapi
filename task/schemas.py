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
    is_public: bool


class ChallengeAll(ModelSchema):
    class Meta:
        model = Challenge
        fields = "__all__"


class ChallengeIn(Schema):
    display: int
    title: str
    content: str
    score: int = 0
    is_public: bool = False
