import csv
import threading
from typing import List, Literal, Optional
from urllib.parse import quote
from uuid import UUID
from django.http import HttpResponse
from ninja import Router, Query
from ninja.errors import HttpError
from ninja.pagination import paginate
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import (
    Avg,
    Count,
    Exists,
    F,
    IntegerField,
    Max,
    OuterRef,
    Q,
    Subquery,
)
from account.decorators import admin_required
from prompt.models import Conversation, Message


from .schemas import (
    AwardItemIn,
    AwardItemManageOut,
    AwardItemUpdateIn,
    AwardManageIn,
    AwardManageOut,
    FlagIn,
    FlagStats,
    AwardOut,
    GradebookOut,
    PromptRoundOut,
    ShowcaseDetailOut,
    ShowcaseItemOut,
    ShowcaseSubmissionLookupOut,
    SubmissionCountBucket,
    SubmissionFilter,
    SubmissionIn,
    SubmissionOut,
    RatingScoreIn,
    TaskStatsOut,
    TopViewedItem,
    UserTag,
)


from .models import Award, ItemOrdering, Rating, Submission, SubmissionAward
from .gradebook import GradebookFilters, build_gradebook, gradebook_csv_rows
from task.models import Task
from account.models import RoleChoices, User

router = Router()


def _validate_item_ordering(value: str):
    if value not in ItemOrdering.values:
        raise HttpError(400, "无效的作品排序方式")


def _award_manage_out(award: Award):
    return {
        "id": award.id,
        "name": award.name,
        "description": award.description,
        "sort_order": award.sort_order,
        "is_active": award.is_active,
        "item_ordering": award.item_ordering,
        "item_count": getattr(award, "item_count", None)
        if getattr(award, "item_count", None) is not None
        else award.submission_awards.count(),
    }


def _award_item_ordering(award: Award):
    ordering_map = {
        ItemOrdering.MANUAL: ("sort_order", "id"),
        ItemOrdering.AWARDED_AT: ("-awarded_at", "sort_order", "id"),
        ItemOrdering.SCORE: ("-submission__score", "sort_order", "id"),
        ItemOrdering.VIEW_COUNT: ("-submission__view_count", "sort_order", "id"),
    }
    return ordering_map.get(award.item_ordering, ("sort_order", "id"))


def _award_item_manage_out(item: SubmissionAward):
    has_prompt_chain = getattr(item, "has_prompt_chain", None)
    if has_prompt_chain is None:
        has_prompt_chain = Message.objects.filter(
            submission_id=item.submission_id
        ).exists()
    return {
        "id": item.id,
        "submission_id": item.submission_id,
        "username": item.submission.user.username,
        "task_title": item.submission.task.title,
        "task_display": item.submission.task.display,
        "score": item.submission.score,
        "view_count": item.submission.view_count,
        "sort_order": item.sort_order,
        "awarded_at": item.awarded_at,
        "has_prompt_chain": has_prompt_chain,
    }


def _showcase_submission_lookup_out(submission: Submission):
    return {
        "submission_id": submission.id,
        "username": submission.user.username,
        "task_title": submission.task.title,
        "task_display": submission.task.display,
        "score": submission.score,
        "view_count": submission.view_count,
        "has_prompt_chain": Message.objects.filter(submission=submission).exists(),
    }


@router.post("/")
@login_required
def create_submission(request, payload: SubmissionIn):
    """
    创建一个新的提交
    """
    task = get_object_or_404(Task, id=payload.task_id)

    manual_asst_msg = None
    if payload.prompt:
        conversation = (
            Conversation.objects.filter(user=request.user, task=task)
            .annotate(msg_count=Count("messages"))
            .order_by("-msg_count", "-created")
            .first()
        )
        if not conversation:
            conversation = Conversation.objects.create(
                user=request.user, task=task, is_active=False
            )
        Message.objects.create(
            conversation=conversation, role="user", content=payload.prompt, source="manual"
        )
        manual_asst_msg = Message.objects.create(
            conversation=conversation,
            role="assistant",
            content="",
            code_html=payload.html,
            code_css=payload.css,
            code_js=payload.js,
            source="manual",
        )
        from .classifier import classify_conversation_messages
        threading.Thread(target=classify_conversation_messages, args=(conversation.id,), daemon=True).start()
    else:
        conversation = (
            Conversation.objects.filter(user=request.user, task=task)
            .annotate(msg_count=Count("messages"))
            .order_by("-msg_count", "-created")
            .first()
        )
        if conversation:
            from .classifier import classify_conversation_messages
            threading.Thread(target=classify_conversation_messages, args=(conversation.id,), daemon=True).start()

    submission = Submission.objects.create(
        user=request.user,
        task=task,
        html=payload.html,
        css=payload.css,
        js=payload.js,
    )

    # Link assistant message to submission
    if manual_asst_msg:
        manual_asst_msg.submission = submission
        manual_asst_msg.save(update_fields=["submission"])
    elif payload.message_id:
        try:
            msg = Message.objects.get(
                id=payload.message_id,
                role="assistant",
                conversation__user=request.user,
                conversation__task=task,
            )
            msg.submission = submission
            msg.save(update_fields=["submission"])
        except Message.DoesNotExist:
            pass  # invalid message_id — submission already created, silently skip

    return {"id": str(submission.id)}


@router.get("/", response=List[SubmissionOut])
@paginate
@login_required
def list_submissions(request, filters: SubmissionFilter = Query(...)):
    """
    获取提交列表，支持按任务和用户过滤
    """
    submissions = (
        Submission.objects.select_related("task", "user")
        .defer("html", "css", "js")
    )

    if filters.task_id:
        task = get_object_or_404(Task, id=filters.task_id)
        submissions = submissions.filter(task=task)
    elif filters.task_type:
        submissions = submissions.filter(task__task_type=filters.task_type)
    if filters.username:
        submissions = submissions.filter(user__username__icontains=filters.username)
    if filters.user_id:
        submissions = submissions.filter(user_id=filters.user_id)
    if filters.flag:
        if filters.flag == "any":
            submissions = submissions.filter(flag__isnull=False)
        else:
            submissions = submissions.filter(flag=filters.flag)
    if filters.zone:
        submissions = submissions.filter(zone=filters.zone)

    if filters.score_lt_threshold is not None:
        submissions = submissions.filter(score__lt=filters.score_lt_threshold)
    else:
        if filters.score_min is not None:
            submissions = submissions.filter(score__gte=filters.score_min)
        if filters.score_max_exclusive is not None:
            submissions = submissions.filter(score__lt=filters.score_max_exclusive)
    if filters.ordering in ("-score", "score", "-created"):
        submissions = submissions.order_by(filters.ordering)

    if filters.grouped:
        # 分组模式：每个 (user, task) 只保留最新一条
        latest_per_group = (
            Submission.objects.filter(user=OuterRef("user"), task=OuterRef("task"))
            .order_by("-created")
            .values("pk")[:1]
        )
        submissions = submissions.filter(pk=Subquery(latest_per_group))

    user_rating_subquery = Subquery(
        Rating.objects.filter(user=request.user, submission=OuterRef("pk")).values(
            "score"
        )[:1],
        output_field=IntegerField(),
    )
    submissions = submissions.annotate(my_score=user_rating_subquery)

    # 同一用户同一任务的提交次数
    submit_count_subquery = Subquery(
        Submission.objects.filter(
            user=OuterRef("user"), task=OuterRef("task")
        ).values("user", "task").annotate(c=Count("id")).values("c")[:1],
        output_field=IntegerField(),
    )
    submissions = submissions.annotate(submit_count=submit_count_subquery)

    return submissions



@router.get("/by-user-task", response=List[SubmissionOut])
@login_required
def list_by_user_task(request, user_id: int, task_id: int):
    """
    获取某用户某任务的所有提交（不分页）
    """
    user_rating_subquery = Subquery(
        Rating.objects.filter(user=request.user, submission=OuterRef("pk")).values(
            "score"
        )[:1],
        output_field=IntegerField(),
    )
    return (
        Submission.objects.filter(user_id=user_id, task_id=task_id)
        .select_related("task", "user")
        .defer("html", "css", "js")
        .annotate(my_score=user_rating_subquery)
        .order_by("-created")
    )


@router.delete("/flags")
@login_required
def clear_all_flags(request):
    """
    清除所有提交的标记（仅管理员和超级管理员可操作）
    """
    if request.user.role not in (RoleChoices.SUPER, RoleChoices.ADMIN):
        raise HttpError(403, "没有权限")

    count = Submission.objects.filter(flag__isnull=False).update(flag=None)
    return {"cleared": count}


@router.delete("/{submission_id}")
@login_required
def delete_submission(request, submission_id: UUID):
    submission = get_object_or_404(Submission, id=submission_id)
    if submission.user != request.user and request.user.role != RoleChoices.SUPER:
        raise HttpError(403, "只能删除自己的提交")

    # 找到关联的助手消息，再找前一条用户消息
    asst_msg = Message.objects.filter(submission=submission).first()
    user_msg = None
    if asst_msg:
        user_msg = (
            Message.objects.filter(
                conversation=asst_msg.conversation,
                created__lt=asst_msg.created,
                role="user",
            )
            .order_by("-created")
            .first()
        )

    submission.delete()  # CASCADE 自动删除关联的 asst_msg

    if user_msg:
        user_msg.delete()

    return {"message": "删除成功"}


@router.get("/stats/{task_id}", response=TaskStatsOut)
@login_required
def get_task_stats(request, task_id: int, classname: Optional[str] = None):
    """
    获取某个挑战任务的班级提交统计数据（仅管理员）
    """
    if request.user.role not in (RoleChoices.SUPER, RoleChoices.ADMIN):
        raise HttpError(403, "没有权限")

    task = get_object_or_404(Task, id=task_id)

    # All distinct classnames (unfiltered, for filter buttons in UI)
    all_classes = list(
        User.objects.filter(role=RoleChoices.NORMAL)
        .exclude(classname="")
        .values_list("classname", flat=True)
        .distinct()
        .order_by("classname")
    )

    # Student universe: Normal users, optionally filtered by classname
    students = User.objects.filter(role=RoleChoices.NORMAL)
    if classname:
        students = students.filter(classname=classname)

    student_ids = list(students.values_list("id", flat=True))
    total_students = len(student_ids)

    # Submitted student IDs
    submitted_ids = set(
        Submission.objects.filter(task=task, user_id__in=student_ids)
        .values_list("user_id", flat=True)
        .distinct()
    )
    submitted_count = len(submitted_ids)
    unsubmitted_count = total_students - submitted_count

    # Unsubmitted users
    unsubmitted_users = [
        UserTag(username=u.username, classname=u.classname)
        for u in students.exclude(id__in=submitted_ids).order_by("classname", "username")
    ]

    # Latest submission per submitted user (SQLite-compatible).
    # Find each user's max created timestamp, then resolve all matching IDs
    # in a single query using OR'd Q objects instead of one query per user.
    latest_per_user = list(
        Submission.objects.filter(task=task, user_id__in=submitted_ids)
        .values("user_id")
        .annotate(max_created=Max("created"))
    )
    latest_sub_ids = []
    if latest_per_user:
        user_time_filter = Q()
        for row in latest_per_user:
            user_time_filter |= Q(user_id=row["user_id"], created=row["max_created"])
        # Fetch all matching submissions in one query; deduplicate by user_id
        seen_users: set = set()
        for sub_id, uid in (
            Submission.objects.filter(user_time_filter, task=task)
            .values_list("id", "user_id")
        ):
            if uid not in seen_users:
                seen_users.add(uid)
                latest_sub_ids.append(sub_id)
    latest_subs = list(Submission.objects.filter(id__in=latest_sub_ids))

    # Average score from latest submissions (None if no submissions have score > 0)
    avg_result = (
        Submission.objects.filter(id__in=latest_sub_ids, score__gt=0)
        .aggregate(avg=Avg("score"))["avg"]
    )
    average_score = round(avg_result, 2) if avg_result is not None else None

    # Unrated: submitted but no Rating on any of their submissions for this task
    rated_ids = set(
        Rating.objects.filter(
            submission__task=task, submission__user_id__in=submitted_ids
        )
        .values_list("submission__user_id", flat=True)
        .distinct()
    )
    unrated_ids = submitted_ids - rated_ids
    unrated_count = len(unrated_ids)
    unrated_users = [
        UserTag(username=u.username, classname=u.classname)
        for u in students.filter(id__in=unrated_ids).order_by("classname", "username")
    ]

    # Submission count distribution
    sub_counts = dict(
        Submission.objects.filter(task=task, user_id__in=submitted_ids)
        .values("user_id")
        .annotate(c=Count("id"))
        .values_list("user_id", "c")
    )
    dist = {"count_1": 0, "count_2": 0, "count_3": 0, "count_4_plus": 0}
    for c in sub_counts.values():
        if c == 1:
            dist["count_1"] += 1
        elif c == 2:
            dist["count_2"] += 1
        elif c == 3:
            dist["count_3"] += 1
        else:
            dist["count_4_plus"] += 1

    # Flag stats (all submissions for this task, not grouped by user)
    flag_counts = dict(
        Submission.objects.filter(task=task, flag__isnull=False)
        .values("flag")
        .annotate(c=Count("id"))
        .values_list("flag", "c")
    )
    flag_stats = FlagStats(
        red=flag_counts.get("red", 0),
        blue=flag_counts.get("blue", 0),
        green=flag_counts.get("green", 0),
        yellow=flag_counts.get("yellow", 0),
    )

    # Top 5 submissions by view_count (within filtered student_ids)
    top_viewed_qs = (
        Submission.objects
        .filter(task=task, user_id__in=student_ids)
        .select_related("user")
        .defer("html", "css", "js")
        .order_by("-view_count")[:5]
    )
    top_viewed = [
        TopViewedItem(
            username=s.user.username,
            classname=s.user.classname,
            view_count=s.view_count,
            submission_id=s.id,
        )
        for s in top_viewed_qs
    ]

    return TaskStatsOut(
        submitted_count=submitted_count,
        unsubmitted_count=unsubmitted_count,
        average_score=average_score,
        unrated_count=unrated_count,
        unsubmitted_users=unsubmitted_users,
        unrated_users=unrated_users,
        submission_count_distribution=SubmissionCountBucket(**dist),
        flag_stats=flag_stats,
        classes=all_classes,
        top_viewed=top_viewed,
    )


@router.get("/gradebook/", response=GradebookOut)
@admin_required
def get_gradebook(
    request,
    classname: str = "",
    task_type: Optional[Literal["tutorial", "challenge"]] = None,
    username: Optional[str] = None,
    include_all_tasks: bool = False,
):
    return build_gradebook(
        GradebookFilters(
            classname=classname,
            task_type=task_type,
            username=username,
            include_all_tasks=include_all_tasks,
        )
    )


@router.get("/gradebook/export/")
@admin_required
def export_gradebook(
    request,
    classname: str = "",
    task_type: Optional[Literal["tutorial", "challenge"]] = None,
    username: Optional[str] = None,
    include_all_tasks: bool = False,
):
    gradebook = build_gradebook(
        GradebookFilters(
            classname=classname,
            task_type=task_type,
            username=username,
            include_all_tasks=include_all_tasks,
        )
    )
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    filename = f"gradebook-{gradebook['classname']}.csv"
    response["Content-Disposition"] = (
        f"attachment; filename*=UTF-8''{quote(filename)}"
    )
    response.write("\ufeff")
    writer = csv.writer(response)
    for row in gradebook_csv_rows(gradebook):
        writer.writerow(row)
    return response


@router.get("/showcase/", response=List[AwardOut])
@login_required
def list_showcase(request):
    ordering_map = {
        ItemOrdering.MANUAL: "sort_order",
        ItemOrdering.AWARDED_AT: "-awarded_at",
        ItemOrdering.SCORE: "-submission__score",
        ItemOrdering.VIEW_COUNT: "-submission__view_count",
    }
    awards = Award.objects.filter(is_active=True).order_by("sort_order")
    result = []

    for award in awards:
        order_field = ordering_map.get(award.item_ordering, "sort_order")
        items_qs = (
            SubmissionAward.objects.filter(award=award)
            .select_related("submission", "submission__user", "submission__task")
            .annotate(
                has_prompt_chain=Exists(
                    Message.objects.filter(submission_id=OuterRef("submission_id"))
                )
            )
            .order_by(order_field)
        )
        items = list(items_qs)
        if not items:
            continue
        result.append(
            {
                "id": award.id,
                "name": award.name,
                "description": award.description,
                "item_ordering": award.item_ordering,
                "items": [
                    {
                        "submission_id": sa.submission_id,
                        "username": sa.submission.user.username,
                        "task_title": sa.submission.task.title,
                        "task_display": sa.submission.task.display,
                        "score": sa.submission.score,
                        "view_count": sa.submission.view_count,
                        "html": sa.submission.html,
                        "css": sa.submission.css,
                        "js": sa.submission.js,
                        "has_prompt_chain": sa.has_prompt_chain,
                    }
                    for sa in items
                ],
            }
        )

    return result


@router.get("/showcase/manage/awards", response=List[AwardManageOut])
@admin_required
def list_manage_awards(request):
    awards = Award.objects.annotate(
        item_count=Count("submission_awards")
    ).order_by("sort_order", "id")
    return [_award_manage_out(award) for award in awards]


@router.post("/showcase/manage/awards", response=AwardManageOut)
@admin_required
def create_manage_award(request, payload: AwardManageIn):
    _validate_item_ordering(payload.item_ordering)
    award = Award.objects.create(**payload.dict())
    award.item_count = 0
    return _award_manage_out(award)


@router.put("/showcase/manage/awards/{award_id}", response=AwardManageOut)
@admin_required
def update_manage_award(request, award_id: int, payload: AwardManageIn):
    _validate_item_ordering(payload.item_ordering)
    award = get_object_or_404(Award, id=award_id)
    award.name = payload.name
    award.description = payload.description
    award.sort_order = payload.sort_order
    award.is_active = payload.is_active
    award.item_ordering = payload.item_ordering
    award.save(
        update_fields=[
            "name",
            "description",
            "sort_order",
            "is_active",
            "item_ordering",
        ]
    )
    award.item_count = award.submission_awards.count()
    return _award_manage_out(award)


@router.delete("/showcase/manage/awards/{award_id}")
@admin_required
def delete_manage_award(request, award_id: int):
    award = get_object_or_404(Award, id=award_id)
    award.delete()
    return {"message": "删除成功"}


@router.get(
    "/showcase/manage/submissions/{submission_id}",
    response=ShowcaseSubmissionLookupOut,
)
@admin_required
def get_manage_submission(request, submission_id: UUID):
    submission = get_object_or_404(
        Submission.objects.select_related("user", "task"),
        id=submission_id,
    )
    return _showcase_submission_lookup_out(submission)


@router.get(
    "/showcase/manage/awards/{award_id}/items",
    response=List[AwardItemManageOut],
)
@admin_required
def list_manage_award_items(request, award_id: int):
    award = get_object_or_404(Award, id=award_id)
    items = (
        SubmissionAward.objects.filter(award=award)
        .select_related("submission", "submission__user", "submission__task")
        .annotate(
            has_prompt_chain=Exists(
                Message.objects.filter(submission_id=OuterRef("submission_id"))
            )
        )
        .order_by(*_award_item_ordering(award))
    )
    return [_award_item_manage_out(item) for item in items]


@router.post(
    "/showcase/manage/awards/{award_id}/items",
    response=AwardItemManageOut,
)
@admin_required
def create_manage_award_item(request, award_id: int, payload: AwardItemIn):
    award = get_object_or_404(Award, id=award_id)
    submission = get_object_or_404(
        Submission.objects.select_related("user", "task"),
        id=payload.submission_id,
    )
    item, created = SubmissionAward.objects.get_or_create(
        award=award,
        submission=submission,
        defaults={"sort_order": payload.sort_order},
    )
    if not created:
        raise HttpError(400, "该作品已在奖项中")
    item.submission = submission
    return _award_item_manage_out(item)


@router.put("/showcase/manage/items/{item_id}", response=AwardItemManageOut)
@admin_required
def update_manage_award_item(request, item_id: int, payload: AwardItemUpdateIn):
    item = get_object_or_404(
        SubmissionAward.objects.select_related(
            "submission",
            "submission__user",
            "submission__task",
        ),
        id=item_id,
    )
    item.sort_order = payload.sort_order
    item.save(update_fields=["sort_order"])
    return _award_item_manage_out(item)


@router.delete("/showcase/manage/items/{item_id}")
@admin_required
def delete_manage_award_item(request, item_id: int):
    item = get_object_or_404(SubmissionAward, id=item_id)
    item.delete()
    return {"message": "删除成功"}


@router.get("/showcase/{submission_id}/", response=ShowcaseDetailOut)
@login_required
def get_showcase_detail(request, submission_id: UUID):
    if not SubmissionAward.objects.filter(
        submission_id=submission_id,
        award__is_active=True,
    ).exists():
        raise HttpError(404, "作品不存在或未授奖")

    sub = get_object_or_404(
        Submission.objects.select_related("user", "task"),
        id=submission_id,
    )
    has_chain = Message.objects.filter(submission=sub).exists()
    award_names = list(
        SubmissionAward.objects.filter(submission=sub)
        .filter(award__is_active=True)
        .select_related("award")
        .values_list("award__name", flat=True)
    )

    return {
        "submission_id": sub.id,
        "username": sub.user.username,
        "task_title": sub.task.title,
        "task_display": sub.task.display,
        "score": sub.score,
        "view_count": sub.view_count,
        "html": sub.html,
        "css": sub.css,
        "js": sub.js,
        "awards": award_names,
        "has_prompt_chain": has_chain,
    }


def _build_prompt_rounds(source_msg: Message):
    messages = list(source_msg.conversation.messages.all().order_by("created", "id"))
    try:
        source_index = messages.index(source_msg)
    except ValueError:
        source_index = len(messages) - 1
    messages = messages[: source_index + 1]

    rounds = []
    for i, msg in enumerate(messages):
        if msg.role != "user":
            continue
        html = css = js = None
        assistant_msg_id = None
        for reply in messages[i + 1:]:
            if reply.role == "user":
                break
            if reply.role == "assistant":
                assistant_msg_id = reply.id
                html = reply.code_html
                css = reply.code_css
                js = reply.code_js
                break
        rounds.append(
            {
                "question": msg.content,
                "source": msg.source,
                "prompt_level": msg.prompt_level,
                "assistant_msg_id": assistant_msg_id,
                "html": html,
                "css": css,
                "js": js,
            }
        )
    return rounds


@router.get("/showcase/{submission_id}/prompt-chain/", response=List[PromptRoundOut])
@login_required
def get_showcase_prompt_chain(request, submission_id: UUID):
    if not SubmissionAward.objects.filter(
        submission_id=submission_id,
        award__is_active=True,
    ).exists():
        raise HttpError(404, "作品不存在或未授奖")

    sub = get_object_or_404(Submission, id=submission_id)
    try:
        source_msg = Message.objects.select_related("conversation").get(submission=sub)
    except Message.DoesNotExist:
        raise HttpError(404, "该作品没有关联提示词链")

    return _build_prompt_rounds(source_msg)


@router.get("/{submission_id}/prompt-chain", response=List[PromptRoundOut])
@login_required
def get_submission_prompt_chain(request, submission_id: UUID):
    sub = get_object_or_404(Submission, id=submission_id)
    try:
        source_msg = Message.objects.select_related("conversation").get(submission=sub)
    except Message.DoesNotExist:
        raise HttpError(404, "该提交没有关联提示词链")

    return _build_prompt_rounds(source_msg)


@router.get("/{submission_id}", response=SubmissionOut)
@login_required
def get_submission(request, submission_id: UUID):
    """
    获取单个提交的详细信息
    """
    user_rating_subquery = Subquery(
        Rating.objects.filter(user=request.user, submission=OuterRef("pk")).values(
            "score"
        )[:1],
        output_field=IntegerField(),
    )
    submission = get_object_or_404(
        Submission.objects.select_related("task", "user").annotate(
            my_score=user_rating_subquery
        ),
        id=submission_id,
    )
    return submission


@router.post("/{submission_id}/view")
@login_required
def increment_view(request, submission_id: UUID):
    """
    增加提交的浏览次数（仅在全屏预览时调用）
    """
    updated = Submission.objects.filter(pk=submission_id).update(
        view_count=F("view_count") + 1
    )
    if not updated:
        raise HttpError(404, "提交不存在")
    return {"ok": True}


@router.put("/{submission_id}/score")
@login_required
def update_score(request, submission_id: UUID, payload: RatingScoreIn):
    """
    给提交打分
    """
    if payload.score <= 0:
        raise HttpError(400, "分数不能为零")

    submission = get_object_or_404(Submission, id=submission_id)

    _, created = Rating.objects.get_or_create(
        user=request.user,
        submission=submission,
        defaults={"score": payload.score},
    )

    if created:
        return {"message": "打分成功"}
    else:
        return {"message": "你已经给这个提交打过分了"}


@router.put("/{submission_id}/flag")
@login_required
def update_flag(request, submission_id: UUID, payload: FlagIn):
    """
    设置或清除提交的标记（仅管理员和超级管理员可操作）
    """
    if request.user.role not in (RoleChoices.SUPER, RoleChoices.ADMIN):
        raise HttpError(403, "没有权限")

    submission = get_object_or_404(Submission, id=submission_id)
    submission.flag = payload.flag
    submission.save(update_fields=["flag"])
    return {"flag": submission.flag}
