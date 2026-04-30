from django.contrib.auth import get_user_model
from django.test import TestCase

from prompt.models import Conversation, Message
from task.models import Task

from .models import Submission

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
