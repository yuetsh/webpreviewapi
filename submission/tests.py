import csv
import io
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from account.models import RoleChoices
from prompt.models import Conversation, Message
from task.models import Task

from .models import Award, Submission, SubmissionAward

User = get_user_model()


def _make_user(username, role=RoleChoices.NORMAL, classname=""):
    user = User.objects.create_user(username=username, password="pw")
    user.role = role
    user.classname = classname
    user.save(update_fields=["role", "classname"])
    return user


def _make_task(
    title="Test Challenge",
    task_type="challenge",
    display=1,
    is_public=True,
):
    return Task.objects.create(
        title=title,
        task_type=task_type,
        display=display,
        content="",
        is_public=is_public,
    )


class SubmissionPromptChainTest(TestCase):
    def setUp(self):
        self.viewer = _make_user("viewer")
        self.author = _make_user("author")
        self.task = _make_task()

        viewer_conv = Conversation.objects.create(user=self.viewer, task=self.task)
        Message.objects.create(
            conversation=viewer_conv,
            role="user",
            content="viewer prompt",
        )
        Message.objects.create(
            conversation=viewer_conv,
            role="assistant",
            content="viewer answer",
            code_html="<p>viewer</p>",
        )

        author_conv = Conversation.objects.create(user=self.author, task=self.task)
        Message.objects.create(
            conversation=author_conv,
            role="user",
            content="author prompt",
        )
        self.submission = Submission.objects.create(
            user=self.author,
            task=self.task,
            html="<button>author</button>",
            css="button { color: red; }",
            js="",
        )
        Message.objects.create(
            conversation=author_conv,
            role="assistant",
            content="author answer",
            code_html="<button>author</button>",
            code_css="button { color: red; }",
            code_js="",
            submission=self.submission,
        )

    def test_normal_user_can_view_prompt_chain_for_another_users_submission(self):
        self.client.force_login(self.viewer)

        resp = self.client.get(f"/api/submission/{self.submission.id}/prompt-chain")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["question"], "author prompt")
        self.assertEqual(data[0]["html"], "<button>author</button>")


class ShowcaseManagementApiTest(TestCase):
    def setUp(self):
        self.admin = _make_user("admin")
        self.admin.role = RoleChoices.ADMIN
        self.admin.save(update_fields=["role"])
        self.student = _make_user("student")
        self.task = _make_task()
        self.award = Award.objects.create(name="最佳视觉", sort_order=10)
        self.submission = Submission.objects.create(
            user=self.student,
            task=self.task,
            html="<main>work</main>",
            css="main { color: red; }",
            js="",
            score=4.5,
            view_count=8,
        )

    def test_normal_user_cannot_access_management_api(self):
        self.client.force_login(self.student)

        resp = self.client.get("/api/submission/showcase/manage/awards")
        lookup_resp = self.client.get(
            f"/api/submission/showcase/manage/submissions/{self.submission.id}"
        )

        self.assertIn(resp.status_code, (302, 403))
        self.assertIn(lookup_resp.status_code, (302, 403))

    def test_admin_can_find_submission_by_id_for_showcase_management(self):
        self.client.force_login(self.admin)

        resp = self.client.get(
            f"/api/submission/showcase/manage/submissions/{self.submission.id}"
        )

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["submission_id"], str(self.submission.id))
        self.assertEqual(data["username"], "student")
        self.assertEqual(data["task_title"], "Test Challenge")
        self.assertEqual(data["task_display"], 1)
        self.assertEqual(data["score"], 4.5)
        self.assertEqual(data["view_count"], 8)
        self.assertFalse(data["has_prompt_chain"])
        self.assertNotIn("html", data)

    def test_admin_can_create_and_update_award(self):
        self.client.force_login(self.admin)

        create_resp = self.client.post(
            "/api/submission/showcase/manage/awards",
            data={
                "name": "最佳互动",
                "description": "交互完整",
                "sort_order": 3,
                "is_active": True,
                "item_ordering": "score",
            },
            content_type="application/json",
        )
        self.assertEqual(create_resp.status_code, 200)
        created = create_resp.json()
        self.assertEqual(created["name"], "最佳互动")
        self.assertEqual(created["item_count"], 0)

        update_resp = self.client.put(
            f"/api/submission/showcase/manage/awards/{created['id']}",
            data={
                "name": "最佳交互",
                "description": "操作体验完整",
                "sort_order": 1,
                "is_active": False,
                "item_ordering": "view_count",
            },
            content_type="application/json",
        )
        self.assertEqual(update_resp.status_code, 200)
        updated = update_resp.json()
        self.assertEqual(updated["name"], "最佳交互")
        self.assertEqual(updated["description"], "操作体验完整")
        self.assertEqual(updated["sort_order"], 1)
        self.assertFalse(updated["is_active"])
        self.assertEqual(updated["item_ordering"], "view_count")

    def test_admin_cannot_add_same_submission_twice(self):
        self.client.force_login(self.admin)
        payload = {"submission_id": str(self.submission.id), "sort_order": 2}

        first_resp = self.client.post(
            f"/api/submission/showcase/manage/awards/{self.award.id}/items",
            data=payload,
            content_type="application/json",
        )
        self.assertEqual(first_resp.status_code, 200)
        self.assertEqual(first_resp.json()["submission_id"], str(self.submission.id))

        duplicate_resp = self.client.post(
            f"/api/submission/showcase/manage/awards/{self.award.id}/items",
            data=payload,
            content_type="application/json",
        )

        self.assertEqual(duplicate_resp.status_code, 400)
        self.assertEqual(
            SubmissionAward.objects.filter(
                award=self.award,
                submission=self.submission,
            ).count(),
            1,
        )

    def test_public_showcase_hides_removed_or_inactive_items(self):
        self.client.force_login(self.admin)
        add_resp = self.client.post(
            f"/api/submission/showcase/manage/awards/{self.award.id}/items",
            data={"submission_id": str(self.submission.id), "sort_order": 0},
            content_type="application/json",
        )
        item_id = add_resp.json()["id"]

        self.client.force_login(self.student)
        visible_resp = self.client.get("/api/submission/showcase/")
        self.assertEqual(visible_resp.status_code, 200)
        self.assertEqual(len(visible_resp.json()), 1)
        detail_resp = self.client.get(
            f"/api/submission/showcase/{self.submission.id}/"
        )
        self.assertEqual(detail_resp.status_code, 200)

        self.client.force_login(self.admin)
        delete_resp = self.client.delete(
            f"/api/submission/showcase/manage/items/{item_id}"
        )
        self.assertEqual(delete_resp.status_code, 200)

        self.client.force_login(self.student)
        removed_resp = self.client.get("/api/submission/showcase/")
        self.assertEqual(removed_resp.status_code, 200)
        self.assertEqual(removed_resp.json(), [])
        removed_detail_resp = self.client.get(
            f"/api/submission/showcase/{self.submission.id}/"
        )
        self.assertEqual(removed_detail_resp.status_code, 404)

        self.client.force_login(self.admin)
        self.client.post(
            f"/api/submission/showcase/manage/awards/{self.award.id}/items",
            data={"submission_id": str(self.submission.id), "sort_order": 0},
            content_type="application/json",
        )
        deactivate_resp = self.client.put(
            f"/api/submission/showcase/manage/awards/{self.award.id}",
            data={
                "name": self.award.name,
                "description": self.award.description,
                "sort_order": self.award.sort_order,
                "is_active": False,
                "item_ordering": self.award.item_ordering,
            },
            content_type="application/json",
        )
        self.assertEqual(deactivate_resp.status_code, 200)

        self.client.force_login(self.student)
        inactive_resp = self.client.get("/api/submission/showcase/")
        self.assertEqual(inactive_resp.status_code, 200)
        self.assertEqual(inactive_resp.json(), [])
        inactive_detail_resp = self.client.get(
            f"/api/submission/showcase/{self.submission.id}/"
        )
        self.assertEqual(inactive_detail_resp.status_code, 404)


class GradebookApiTest(TestCase):
    def setUp(self):
        self.admin = _make_user("grade-admin", role=RoleChoices.ADMIN)
        self.normal = _make_user("grade-normal", classname="blocked")

    def _student(self, username, classname="10A"):
        return _make_user(username, classname=classname)

    def _submit(self, user, task, score, created=None):
        submission = Submission.objects.create(
            user=user,
            task=task,
            score=score,
            html="",
            css="",
            js="",
        )
        if created is not None:
            Submission.objects.filter(pk=submission.pk).update(created=created)
            submission.refresh_from_db()
        return submission

    def test_gradebook_requires_classname(self):
        self.client.force_login(self.admin)

        resp = self.client.get("/api/submission/gradebook/")

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["detail"], "请选择班级")

    def test_normal_user_cannot_access_gradebook(self):
        self.client.force_login(self.normal)

        resp = self.client.get("/api/submission/gradebook/?classname=10A")
        export_resp = self.client.get(
            "/api/submission/gradebook/export/?classname=10A"
        )

        self.assertIn(resp.status_code, (302, 403))
        self.assertIn(export_resp.status_code, (302, 403))

    def test_coverage_includes_tutorial_and_challenge_without_public_requirement(self):
        students = [
            self._student("alice"),
            self._student("bob"),
            self._student("carol"),
            self._student("dave"),
        ]
        tutorial = _make_task(
            title="Intro",
            task_type="tutorial",
            display=1,
            is_public=False,
        )
        challenge = _make_task(
            title="Challenge One",
            task_type="challenge",
            display=1,
            is_public=True,
        )
        low_coverage = _make_task(
            title="Optional",
            task_type="challenge",
            display=2,
            is_public=True,
        )
        self._submit(students[0], tutorial, 4.0)
        self._submit(students[1], tutorial, 5.0)
        self._submit(students[0], challenge, 3.0)
        self._submit(students[1], challenge, 4.0)
        self._submit(students[0], low_coverage, 5.0)
        self.client.force_login(self.admin)

        resp = self.client.get("/api/submission/gradebook/?classname=10A")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["student_count"], 4)
        self.assertEqual(data["coverage_threshold_count"], 2)
        self.assertEqual(data["included_task_count"], 2)
        self.assertEqual(
            [task["id"] for task in data["tasks"]],
            [tutorial.id, challenge.id],
        )
        self.assertTrue(all(task["included"] for task in data["tasks"]))

        alice = next(row for row in data["rows"] if row["username"] == "alice")
        carol = next(row for row in data["rows"] if row["username"] == "carol")
        self.assertEqual(alice["tutorial_total"], 4.0)
        self.assertEqual(alice["challenge_total"], 3.0)
        self.assertEqual(alice["total_score"], 7.0)
        self.assertEqual(alice["average_score"], 3.5)
        self.assertEqual(alice["submitted_task_count"], 2)
        self.assertEqual(alice["missing_task_count"], 0)
        self.assertEqual(carol["total_score"], 0.0)
        self.assertEqual(carol["submitted_task_count"], 0)
        self.assertEqual(carol["missing_task_count"], 2)

        include_all_resp = self.client.get(
            "/api/submission/gradebook/?classname=10A&include_all_tasks=true"
        )
        include_all = include_all_resp.json()
        optional = next(
            task for task in include_all["tasks"] if task["id"] == low_coverage.id
        )
        alice_all = next(
            row for row in include_all["rows"] if row["username"] == "alice"
        )
        self.assertFalse(optional["included"])
        self.assertTrue(alice_all["scores"][str(low_coverage.id)]["submitted"])
        self.assertEqual(alice_all["scores"][str(low_coverage.id)]["score"], 5.0)
        self.assertEqual(alice_all["total_score"], 7.0)
        self.assertEqual(alice_all["submitted_task_count"], 2)

    def test_best_submission_uses_highest_score_and_latest_equal_score_link(self):
        alice = self._student("alice")
        bob = self._student("bob")
        task = _make_task(title="Best Score", task_type="tutorial", display=3)
        older = timezone.now() - timedelta(days=2)
        newer = timezone.now() - timedelta(days=1)
        self._submit(alice, task, 2.0)
        old_best = self._submit(alice, task, 4.5, created=older)
        new_best = self._submit(alice, task, 4.5, created=newer)
        self._submit(bob, task, 3.0)
        self.client.force_login(self.admin)

        resp = self.client.get("/api/submission/gradebook/?classname=10A")

        self.assertEqual(resp.status_code, 200)
        alice_row = next(
            row for row in resp.json()["rows"] if row["username"] == "alice"
        )
        cell = alice_row["scores"][str(task.id)]
        self.assertEqual(cell["score"], 4.5)
        self.assertEqual(cell["submission_id"], str(new_best.id))
        self.assertNotEqual(cell["submission_id"], str(old_best.id))

    def test_task_type_and_username_filters_keep_full_class_rank(self):
        alice = self._student("alice")
        bob = self._student("bob")
        tutorial = _make_task(title="Tutorial", task_type="tutorial", display=1)
        challenge = _make_task(title="Challenge", task_type="challenge", display=1)
        self._submit(alice, tutorial, 1.0)
        self._submit(bob, tutorial, 5.0)
        self._submit(alice, challenge, 5.0)
        self._submit(bob, challenge, 1.0)
        self.client.force_login(self.admin)

        resp = self.client.get(
            "/api/submission/gradebook/?classname=10A&task_type=tutorial&username=alice"
        )

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual([task["task_type"] for task in data["tasks"]], ["tutorial"])
        self.assertEqual(len(data["rows"]), 1)
        self.assertEqual(data["rows"][0]["username"], "alice")
        self.assertEqual(data["rows"][0]["rank"], 2)

    def test_missing_class_returns_empty_table_with_class_options(self):
        self._student("alice")
        self.client.force_login(self.admin)

        resp = self.client.get("/api/submission/gradebook/?classname=missing")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("10A", data["classes"])
        self.assertEqual(data["student_count"], 0)
        self.assertEqual(data["coverage_threshold_count"], 0)
        self.assertEqual(data["tasks"], [])
        self.assertEqual(data["rows"], [])

    def test_no_included_tasks_still_returns_student_rows(self):
        students = [
            self._student("alice"),
            self._student("bob"),
            self._student("carol"),
        ]
        optional = _make_task(title="Low Coverage", task_type="challenge", display=8)
        self._submit(students[0], optional, 5.0)
        self.client.force_login(self.admin)

        resp = self.client.get("/api/submission/gradebook/?classname=10A")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["student_count"], 3)
        self.assertEqual(data["coverage_threshold_count"], 2)
        self.assertEqual(data["tasks"], [])
        self.assertEqual(data["included_task_count"], 0)
        self.assertEqual(len(data["rows"]), 3)
        alice = next(row for row in data["rows"] if row["username"] == "alice")
        self.assertEqual(alice["total_score"], 0.0)
        self.assertIsNone(alice["average_score"])
        self.assertEqual(alice["submitted_task_count"], 0)
        self.assertEqual(alice["missing_task_count"], 0)

        include_all_resp = self.client.get(
            "/api/submission/gradebook/?classname=10A&include_all_tasks=true"
        )
        include_all = include_all_resp.json()
        self.assertEqual(include_all["task_count"], 1)
        self.assertFalse(include_all["tasks"][0]["included"])
        alice_all = next(
            row for row in include_all["rows"] if row["username"] == "alice"
        )
        self.assertTrue(alice_all["scores"][str(optional.id)]["submitted"])
        self.assertEqual(alice_all["total_score"], 0.0)

    def test_grade_boundaries_use_ceil_thresholds(self):
        task = _make_task(title="Boundary", task_type="challenge", display=7)
        for i in range(1, 21):
            student = self._student(f"s{i:02d}", classname="10B")
            self._submit(student, task, float(21 - i))
        self.client.force_login(self.admin)

        resp = self.client.get("/api/submission/gradebook/?classname=10B")

        self.assertEqual(resp.status_code, 200)
        rows_by_name = {row["username"]: row for row in resp.json()["rows"]}
        self.assertEqual(rows_by_name["s01"]["grade"], "A")
        self.assertEqual(rows_by_name["s06"]["grade"], "A")
        self.assertEqual(rows_by_name["s07"]["grade"], "B")
        self.assertEqual(rows_by_name["s14"]["grade"], "B")
        self.assertEqual(rows_by_name["s15"]["grade"], "C")
        self.assertEqual(rows_by_name["s18"]["grade"], "C")
        self.assertEqual(rows_by_name["s19"]["grade"], "D")
        self.assertEqual(rows_by_name["s20"]["grade"], "E")

    def test_export_csv_matches_current_filters(self):
        alice = self._student("alice")
        bob = self._student("bob")
        tutorial = _make_task(title="Intro", task_type="tutorial", display=1)
        challenge = _make_task(title="Challenge", task_type="challenge", display=1)
        self._submit(alice, tutorial, 4.0)
        self._submit(bob, tutorial, 2.0)
        self._submit(alice, challenge, 5.0)
        self.client.force_login(self.admin)

        resp = self.client.get(
            "/api/submission/gradebook/export/?classname=10A&task_type=tutorial"
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("attachment;", resp["Content-Disposition"])
        rows = list(csv.reader(io.StringIO(resp.content.decode("utf-8-sig"))))
        self.assertEqual(
            rows[0],
            [
                "排名",
                "等级",
                "用户名",
                "班级",
                "教程1-Intro",
                "教程合计",
                "挑战合计",
                "总分",
                "平均分",
                "已提交任务数",
                "未提交任务数",
            ],
        )
        self.assertEqual(rows[1][2], "alice")
        self.assertEqual(rows[1][4], "4")
        self.assertEqual(rows[1][7], "4")
