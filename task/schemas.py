from ninja import Schema, ModelSchema
from .models import Tutorial


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
