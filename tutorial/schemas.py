from ninja import Schema, ModelSchema
from typing import List, Optional
from .models import Tutorial


class TutorialSlim(Schema):
    display: int
    title: str
    is_public: bool


class TutorialAll(ModelSchema):
    class Meta:
        model = Tutorial
        fields = "__all__"


class TutorialReturn(Schema):
    list: List[TutorialSlim]
    first: Optional[TutorialAll]


class TutorialIn(Schema):
    display: int
    title: str
    content: str
    is_public: bool = False
