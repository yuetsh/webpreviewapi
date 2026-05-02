from dataclasses import dataclass
from math import ceil
from typing import Literal

from django.db.models import Count
from ninja.errors import HttpError

from account.models import RoleChoices, User
from task.models import Task, TaskTypeChoices

from .models import Submission

GradebookTaskType = Literal["tutorial", "challenge"]


@dataclass(frozen=True)
class GradebookFilters:
    classname: str
    task_type: GradebookTaskType | None = None
    username: str | None = None
    include_all_tasks: bool = False


def _score(value):
    rounded = round(float(value or 0), 2)
    if rounded == 0:
        return 0.0
    return rounded


def _grade_for_rank(rank: int, student_count: int) -> str:
    if rank <= ceil(0.30 * student_count):
        return "A"
    if rank <= ceil(0.70 * student_count):
        return "B"
    if rank <= ceil(0.90 * student_count):
        return "C"
    if rank <= ceil(0.95 * student_count):
        return "D"
    return "E"


def _task_sort_key(task):
    type_order = 0 if task.task_type == TaskTypeChoices.TUTORIAL else 1
    return (type_order, task.display, task.id)


def _task_type_label(task_type: str) -> str:
    return "教程" if task_type == TaskTypeChoices.TUTORIAL else "挑战"


def _csv_number(value):
    if value == "":
        return ""
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.2f}".rstrip("0").rstrip(".")


def _classes():
    return list(
        User.objects.filter(role=RoleChoices.NORMAL)
        .exclude(classname="")
        .values_list("classname", flat=True)
        .distinct()
        .order_by("classname")
    )


def _task_csv_header(task):
    return f"{_task_type_label(task['task_type'])}{task['display']}-{task['title']}"


def build_gradebook(filters: GradebookFilters):
    classname = filters.classname.strip() if filters.classname else ""
    if not classname:
        raise HttpError(400, "请选择班级")
    if filters.task_type not in (None, "tutorial", "challenge"):
        raise HttpError(400, "无效的任务类型")

    classes = _classes()
    class_students = list(
        User.objects.filter(role=RoleChoices.NORMAL, classname=classname)
        .order_by("username", "id")
        .only("id", "username", "classname")
    )
    class_student_ids = [student.id for student in class_students]
    student_count = len(class_student_ids)
    coverage_threshold_count = ceil(student_count * 0.5) if student_count else 0

    task_submission_qs = Submission.objects.filter(user_id__in=class_student_ids)
    if filters.task_type:
        task_submission_qs = task_submission_qs.filter(task__task_type=filters.task_type)

    submitted_counts = {
        row["task_id"]: row["submitted_count"]
        for row in task_submission_qs.values("task_id").annotate(
            submitted_count=Count("user_id", distinct=True)
        )
    }
    task_map = {
        task.id: task
        for task in Task.objects.filter(id__in=submitted_counts.keys()).only(
            "id",
            "display",
            "title",
            "task_type",
        )
    }

    all_tasks = []
    for task in sorted(task_map.values(), key=_task_sort_key):
        submitted_count = submitted_counts[task.id]
        included = student_count > 0 and submitted_count >= coverage_threshold_count
        all_tasks.append(
            {
                "id": task.id,
                "display": task.display,
                "title": task.title,
                "task_type": task.task_type,
                "submitted_count": submitted_count,
                "coverage": _score(submitted_count / student_count)
                if student_count
                else 0.0,
                "included": included,
            }
        )

    tasks = [task for task in all_tasks if filters.include_all_tasks or task["included"]]
    visible_task_ids = [task["id"] for task in tasks]
    included_task_ids = {task["id"] for task in tasks if task["included"]}

    best_by_pair = {}
    if class_student_ids and visible_task_ids:
        submissions = (
            Submission.objects.filter(
                user_id__in=class_student_ids,
                task_id__in=visible_task_ids,
            )
            .select_related("task")
            .only("id", "user_id", "task_id", "score", "created", "task__task_type")
            .order_by("user_id", "task_id", "-score", "-created", "-id")
        )
        for submission in submissions:
            best_by_pair.setdefault((submission.user_id, submission.task_id), submission)

    rows = []
    for student in class_students:
        scores = {}
        tutorial_total = 0.0
        challenge_total = 0.0
        submitted_task_count = 0
        missing_task_count = 0

        for task in tasks:
            submission = best_by_pair.get((student.id, task["id"]))
            if submission:
                cell_score = _score(submission.score)
                scores[task["id"]] = {
                    "score": cell_score,
                    "submitted": True,
                    "submission_id": submission.id,
                }
            else:
                cell_score = 0.0
                scores[task["id"]] = {
                    "score": 0.0,
                    "submitted": False,
                    "submission_id": None,
                }

            if not task["included"]:
                continue
            if submission:
                submitted_task_count += 1
            else:
                missing_task_count += 1
            if task["task_type"] == TaskTypeChoices.TUTORIAL:
                tutorial_total += cell_score
            else:
                challenge_total += cell_score

        tutorial_total = _score(tutorial_total)
        challenge_total = _score(challenge_total)
        total_score = _score(tutorial_total + challenge_total)
        average_score = (
            _score(total_score / len(included_task_ids)) if included_task_ids else None
        )
        rows.append(
            {
                "user_id": student.id,
                "username": student.username,
                "classname": student.classname,
                "rank": 0,
                "grade": "E",
                "scores": scores,
                "tutorial_total": tutorial_total,
                "challenge_total": challenge_total,
                "total_score": total_score,
                "average_score": average_score,
                "submitted_task_count": submitted_task_count,
                "missing_task_count": missing_task_count,
            }
        )

    rows.sort(key=lambda row: (-row["total_score"], row["username"]))
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
        row["grade"] = _grade_for_rank(index, student_count)

    username = filters.username.strip().lower() if filters.username else ""
    if username:
        rows = [row for row in rows if username in row["username"].lower()]

    return {
        "classname": classname,
        "classes": classes,
        "task_count": len(tasks),
        "included_task_count": len(included_task_ids),
        "student_count": student_count,
        "coverage_threshold_count": coverage_threshold_count,
        "tasks": tasks,
        "rows": rows,
    }


def gradebook_csv_rows(gradebook):
    tasks = gradebook["tasks"]
    yield [
        "排名",
        "等级",
        "用户名",
        "班级",
        *[_task_csv_header(task) for task in tasks],
        "教程合计",
        "挑战合计",
        "总分",
        "平均分",
        "已提交任务数",
        "未提交任务数",
    ]

    for row in gradebook["rows"]:
        yield [
            row["rank"],
            row["grade"],
            row["username"],
            row["classname"],
            *[_csv_number(row["scores"][task["id"]]["score"]) for task in tasks],
            _csv_number(row["tutorial_total"]),
            _csv_number(row["challenge_total"]),
            _csv_number(row["total_score"]),
            "" if row["average_score"] is None else _csv_number(row["average_score"]),
            row["submitted_task_count"],
            row["missing_task_count"],
        ]
