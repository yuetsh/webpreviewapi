from django.contrib.auth import get_user_model
from django.test import TestCase

from account.models import RoleChoices
from prompt.models import Conversation, Message
from task.models import Task

from .models import Award, Submission, SubmissionAward

User = get_user_model()


def _make_user(username):
    return User.objects.create_user(username=username, password="pw")


def _make_task():
    return Task.objects.create(
        title="Test Challenge",
        task_type="challenge",
        display=1,
        content="",
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
