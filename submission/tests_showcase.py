from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

from submission.models import Award, Submission, SubmissionAward
from task.models import Task

User = get_user_model()


def _make_user(username="student1", role="normal"):
    return User.objects.create_user(username=username, password="pw", role=role)


def _make_task(display=1):
    return Task.objects.create(
        title=f"Task {display}", task_type="challenge", display=display, content=""
    )


def _make_submission(user, task, score=0.0):
    return Submission.objects.create(
        user=user, task=task, html="<p>hi</p>", css="", js="", score=score
    )


def _make_award(name="最佳设计", sort_order=0, is_active=True, item_ordering="manual"):
    return Award.objects.create(
        name=name,
        sort_order=sort_order,
        is_active=is_active,
        item_ordering=item_ordering,
    )


class AwardModelTest(TestCase):
    def test_unique_submission_award(self):
        user = _make_user()
        task = _make_task()
        sub = _make_submission(user, task)
        award = _make_award()
        SubmissionAward.objects.create(submission=sub, award=award)

        with self.assertRaises(IntegrityError):
            SubmissionAward.objects.create(submission=sub, award=award)

    def test_submission_can_have_multiple_awards(self):
        user = _make_user()
        task = _make_task()
        sub = _make_submission(user, task)
        a1 = _make_award("奖1", sort_order=0)
        a2 = _make_award("奖2", sort_order=1)
        SubmissionAward.objects.create(submission=sub, award=a1)
        SubmissionAward.objects.create(submission=sub, award=a2)

        self.assertEqual(sub.awards.count(), 2)

    def test_award_can_have_multiple_submissions(self):
        user = _make_user()
        task = _make_task()
        sub1 = _make_submission(user, task, score=3.0)
        task2 = _make_task(display=2)
        sub2 = _make_submission(user, task2, score=4.0)
        award = _make_award()
        SubmissionAward.objects.create(submission=sub1, award=award)
        SubmissionAward.objects.create(submission=sub2, award=award)

        self.assertEqual(award.submission_awards.count(), 2)


class ShowcaseListTest(TestCase):
    def setUp(self):
        self.user = _make_user("student1")
        self.task = _make_task()

    def test_unauthenticated_returns_401(self):
        resp = self.client.get("/api/submission/showcase/")
        self.assertEqual(resp.status_code, 401)

    def test_authenticated_returns_200(self):
        self.client.force_login(self.user)
        resp = self.client.get("/api/submission/showcase/")
        self.assertEqual(resp.status_code, 200)

    def test_inactive_award_not_returned(self):
        award = _make_award("停用奖", is_active=False)
        sub = _make_submission(self.user, self.task)
        SubmissionAward.objects.create(submission=sub, award=award)
        self.client.force_login(self.user)
        resp = self.client.get("/api/submission/showcase/")
        data = resp.json()
        self.assertEqual(len(data), 0)

    def test_award_with_no_items_not_returned(self):
        _make_award("空奖项")
        self.client.force_login(self.user)
        resp = self.client.get("/api/submission/showcase/")
        data = resp.json()
        self.assertEqual(len(data), 0)

    def test_active_award_with_items_returned(self):
        award = _make_award("最佳设计")
        sub = _make_submission(self.user, self.task)
        SubmissionAward.objects.create(submission=sub, award=award)
        self.client.force_login(self.user)
        resp = self.client.get("/api/submission/showcase/")
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "最佳设计")
        self.assertEqual(len(data[0]["items"]), 1)
        item = data[0]["items"][0]
        self.assertEqual(item["username"], "student1")
        self.assertEqual(item["has_prompt_chain"], False)

    def test_manual_ordering_uses_sort_order(self):
        award = _make_award("奖", item_ordering="manual")
        sub1 = _make_submission(self.user, self.task)
        task2 = _make_task(display=2)
        sub2 = _make_submission(self.user, task2)
        SubmissionAward.objects.create(submission=sub1, award=award, sort_order=2)
        SubmissionAward.objects.create(submission=sub2, award=award, sort_order=1)
        self.client.force_login(self.user)
        resp = self.client.get("/api/submission/showcase/")
        items = resp.json()[0]["items"]
        self.assertEqual(items[0]["task_display"], task2.display)
        self.assertEqual(items[1]["task_display"], self.task.display)

    def test_score_ordering(self):
        award = _make_award("奖", item_ordering="score")
        sub1 = _make_submission(self.user, self.task, score=2.0)
        task2 = _make_task(display=2)
        sub2 = _make_submission(self.user, task2, score=4.0)
        SubmissionAward.objects.create(submission=sub1, award=award)
        SubmissionAward.objects.create(submission=sub2, award=award)
        self.client.force_login(self.user)
        resp = self.client.get("/api/submission/showcase/")
        items = resp.json()[0]["items"]
        self.assertGreater(items[0]["score"], items[1]["score"])

    def test_view_count_ordering(self):
        award = _make_award("奖", item_ordering="view_count")
        sub1 = _make_submission(self.user, self.task)
        sub1.view_count = 5
        sub1.save(update_fields=["view_count"])
        task2 = _make_task(display=2)
        sub2 = _make_submission(self.user, task2)
        sub2.view_count = 20
        sub2.save(update_fields=["view_count"])
        SubmissionAward.objects.create(submission=sub1, award=award)
        SubmissionAward.objects.create(submission=sub2, award=award)
        self.client.force_login(self.user)
        resp = self.client.get("/api/submission/showcase/")
        items = resp.json()[0]["items"]
        self.assertGreater(items[0]["view_count"], items[1]["view_count"])

    def test_has_prompt_chain_true_when_source_message_exists(self):
        from prompt.models import Conversation, Message

        award = _make_award("奖")
        sub = _make_submission(self.user, self.task)
        conv = Conversation.objects.create(user=self.user, task=self.task)
        Message.objects.create(conversation=conv, role="user", content="做个按钮")
        Message.objects.create(
            conversation=conv,
            role="assistant",
            content="好的",
            code_html="<button>OK</button>",
            code_css="",
            code_js="",
            submission=sub,
        )
        SubmissionAward.objects.create(submission=sub, award=award)
        self.client.force_login(self.user)
        resp = self.client.get("/api/submission/showcase/")
        item = resp.json()[0]["items"][0]
        self.assertTrue(item["has_prompt_chain"])


class ShowcaseDetailTest(TestCase):
    def setUp(self):
        self.user = _make_user("student1")
        self.task = _make_task()
        self.award = _make_award("最佳设计")
        self.sub = _make_submission(self.user, self.task, score=4.5)
        self.sub.view_count = 10
        self.sub.save(update_fields=["view_count"])
        SubmissionAward.objects.create(submission=self.sub, award=self.award)

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(f"/api/submission/showcase/{self.sub.id}/")
        self.assertEqual(resp.status_code, 401)

    def test_awarded_submission_accessible(self):
        self.client.force_login(self.user)
        resp = self.client.get(f"/api/submission/showcase/{self.sub.id}/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["username"], "student1")
        self.assertEqual(data["score"], 4.5)
        self.assertEqual(data["view_count"], 10)
        self.assertIn("最佳设计", data["awards"])
        self.assertFalse(data["has_prompt_chain"])

    def test_non_awarded_submission_returns_404(self):
        other_sub = _make_submission(self.user, self.task)
        self.client.force_login(self.user)
        resp = self.client.get(f"/api/submission/showcase/{other_sub.id}/")
        self.assertEqual(resp.status_code, 404)

    def test_submission_shows_all_its_awards(self):
        award2 = _make_award("最佳游戏", sort_order=1)
        SubmissionAward.objects.create(submission=self.sub, award=award2)
        self.client.force_login(self.user)
        resp = self.client.get(f"/api/submission/showcase/{self.sub.id}/")
        data = resp.json()
        self.assertIn("最佳设计", data["awards"])
        self.assertIn("最佳游戏", data["awards"])


class ShowcasePromptChainTest(TestCase):
    def setUp(self):
        from prompt.models import Conversation, Message as Msg

        self.user = _make_user("student1")
        self.task = _make_task()
        self.award = _make_award("最佳设计")
        self.sub = _make_submission(self.user, self.task)
        SubmissionAward.objects.create(submission=self.sub, award=self.award)

        self.conv = Conversation.objects.create(user=self.user, task=self.task)
        Msg.objects.create(
            conversation=self.conv,
            role="user",
            content="做个按钮",
            source="conversation",
            prompt_level=3,
        )
        Msg.objects.create(
            conversation=self.conv,
            role="assistant",
            content="好的",
            code_html="<button>OK</button>",
            code_css="button{color:red}",
            code_js="console.log(1)",
            submission=self.sub,
        )

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(
            f"/api/submission/showcase/{self.sub.id}/prompt-chain/"
        )
        self.assertEqual(resp.status_code, 401)

    def test_no_source_message_returns_404(self):
        other_sub = _make_submission(self.user, self.task)
        SubmissionAward.objects.create(submission=other_sub, award=self.award)
        self.client.force_login(self.user)
        resp = self.client.get(
            f"/api/submission/showcase/{other_sub.id}/prompt-chain/"
        )
        self.assertEqual(resp.status_code, 404)

    def test_non_awarded_submission_returns_404(self):
        from prompt.models import Conversation, Message as Msg

        other_sub = _make_submission(self.user, self.task)
        conv = Conversation.objects.create(user=self.user, task=self.task)
        Msg.objects.create(
            conversation=conv,
            role="assistant",
            content="x",
            submission=other_sub,
        )
        self.client.force_login(self.user)
        resp = self.client.get(
            f"/api/submission/showcase/{other_sub.id}/prompt-chain/"
        )
        self.assertEqual(resp.status_code, 404)

    def test_returns_prompt_rounds(self):
        self.client.force_login(self.user)
        resp = self.client.get(f"/api/submission/showcase/{self.sub.id}/prompt-chain/")
        self.assertEqual(resp.status_code, 200)
        rounds = resp.json()
        self.assertEqual(len(rounds), 1)
        r = rounds[0]
        self.assertEqual(r["question"], "做个按钮")
        self.assertEqual(r["source"], "conversation")
        self.assertEqual(r["prompt_level"], 3)
        self.assertEqual(r["html"], "<button>OK</button>")
        self.assertEqual(r["css"], "button{color:red}")
        self.assertEqual(r["js"], "console.log(1)")

    def test_multiple_rounds(self):
        from prompt.models import Message as Msg

        Msg.objects.create(
            conversation=self.conv,
            role="user",
            content="再加个标题",
            source="manual",
        )
        Msg.objects.create(
            conversation=self.conv,
            role="assistant",
            content="好",
            code_html="<h1>标题</h1>",
            code_css="",
            code_js="",
        )
        self.client.force_login(self.user)
        resp = self.client.get(f"/api/submission/showcase/{self.sub.id}/prompt-chain/")
        rounds = resp.json()
        self.assertEqual(len(rounds), 2)
        self.assertEqual(rounds[1]["question"], "再加个标题")
        self.assertEqual(rounds[1]["source"], "manual")
