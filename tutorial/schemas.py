from ninja import Schema, ModelSchema
from typing import List, Optional
from .models import Tutorial


class TutorialSlim(Schema):
    display: str
    title: str
    is_public: bool


class TutorialAll(ModelSchema):
    class Meta:
        model = Tutorial
        fields = "__all__"


class TutorialReturn(Schema):
    total: int
    list: List[TutorialSlim]
    first: Optional[TutorialAll]


class TutorialIn(Schema):
    display: str
    title: str
    content: str
    is_public: bool = False
