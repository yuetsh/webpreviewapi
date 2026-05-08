from datetime import timedelta
from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from task.models import Task
from submission.models import Submission
from prompt.models import Conversation, Message

User = get_user_model()


def _make_user(username="student1"):
    return User.objects.create_user(username=username, password="pw")


def _make_task():
    return Task.objects.create(
        title="Test Task", task_type="challenge", display=1, content=""
    )


class SubmissionMessageLinkTest(TestCase):
    def setUp(self):
        self.user = _make_user("student1")
        self.task = _make_task()
        self.conv = Conversation.objects.create(user=self.user, task=self.task)
        self.user_msg = Message.objects.create(
            conversation=self.conv, role="user", content="帮我做个按钮"
        )
        self.asst_msg = Message.objects.create(
            conversation=self.conv, role="assistant", content="好的",
            code_html="<button>OK</button>", code_css="", code_js=""
        )

    def test_create_submission_links_message(self):
        """POST /api/submission/ with message_id links the assistant message"""
        self.client.force_login(self.user)
        resp = self.client.post(
            "/api/submission/",
            data={
                "task_id": self.task.id,
                "html": "<button>OK</button>",
                "css": "",
                "js": "",
                "message_id": self.asst_msg.id,
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.asst_msg.refresh_from_db()
        sub = Submission.objects.filter(user=self.user, task=self.task).first()
        self.assertIsNotNone(sub)
        self.assertEqual(self.asst_msg.submission, sub)

    def test_create_submission_without_message_id(self):
        """POST /api/submission/ without message_id still works"""
        self.client.force_login(self.user)
        resp = self.client.post(
            "/api/submission/",
            data={"task_id": self.task.id, "html": "<p>hi</p>", "css": "", "js": ""},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)

    def test_cannot_link_message_from_different_task(self):
        """message_id from a different task is silently ignored"""
        other_task = Task.objects.create(
            title="Other Task", task_type="challenge", display=2, content=""
        )
        other_conv = Conversation.objects.create(user=self.user, task=other_task)
        other_msg = Message.objects.create(
            conversation=other_conv, role="assistant", content="other"
        )
        self.client.force_login(self.user)
        resp = self.client.post(
            "/api/submission/",
            data={
                "task_id": self.task.id,
                "html": "<p>x</p>",
                "css": "",
                "js": "",
                "message_id": other_msg.id,
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        # Submission created, but message NOT linked (wrong task)
        other_msg.refresh_from_db()
        self.assertIsNone(other_msg.submission)


class DeleteSubmissionCascadeTest(TestCase):
    def setUp(self):
        self.user = _make_user("student2")
        self.task = _make_task()
        self.conv = Conversation.objects.create(user=self.user, task=self.task)
        self.user_msg = Message.objects.create(
            conversation=self.conv, role="user", content="问题"
        )
        self.asst_msg = Message.objects.create(
            conversation=self.conv, role="assistant", content="回答",
            code_html="<p>hi</p>", code_css="", code_js=""
        )
        self.sub = Submission.objects.create(
            user=self.user, task=self.task, html="<p>hi</p>", css="", js=""
        )
        self.asst_msg.submission = self.sub
        self.asst_msg.save(update_fields=["submission"])

    def test_delete_submission_also_deletes_message_pair(self):
        """DELETE /api/submission/{id} deletes linked user+assistant messages"""
        self.client.force_login(self.user)
        resp = self.client.delete(f"/api/submission/{self.sub.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Submission.objects.filter(id=self.sub.id).exists())
        self.assertFalse(Message.objects.filter(id=self.asst_msg.id).exists())
        self.assertFalse(Message.objects.filter(id=self.user_msg.id).exists())

    def test_delete_submission_without_linked_message(self):
        """DELETE /api/submission/{id} works even with no linked message"""
        sub2 = Submission.objects.create(
            user=self.user, task=self.task, html="", css="", js=""
        )
        self.client.force_login(self.user)
        resp = self.client.delete(f"/api/submission/{sub2.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Submission.objects.filter(id=sub2.id).exists())


class DeleteMessagePairTest(TestCase):
    def setUp(self):
        self.user = _make_user("student3")
        self.task = _make_task()
        self.conv = Conversation.objects.create(user=self.user, task=self.task)
        self.user_msg = Message.objects.create(
            conversation=self.conv, role="user", content="问题"
        )
        self.asst_msg = Message.objects.create(
            conversation=self.conv, role="assistant", content="回答",
            code_html="<p>ok</p>", code_css="", code_js=""
        )
        self.sub = Submission.objects.create(
            user=self.user, task=self.task, html="<p>ok</p>", css="", js=""
        )
        self.asst_msg.submission = self.sub
        self.asst_msg.save(update_fields=["submission"])

    def test_delete_message_pair_also_deletes_submission(self):
        self.client.force_login(self.user)
        resp = self.client.delete(f"/api/prompt/messages/{self.asst_msg.id}/pair")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Message.objects.filter(id=self.asst_msg.id).exists())
        self.assertFalse(Message.objects.filter(id=self.user_msg.id).exists())
        self.assertFalse(Submission.objects.filter(id=self.sub.id).exists())
        data = resp.json()
        self.assertTrue(data["deleted"])
        self.assertTrue(data["submission_deleted"])

    def test_delete_message_pair_without_submission(self):
        # Create a second pair without a submission link
        user2 = Message.objects.create(
            conversation=self.conv, role="user", content="另一问"
        )
        asst2 = Message.objects.create(
            conversation=self.conv, role="assistant", content="另一条"
        )
        self.client.force_login(self.user)
        resp = self.client.delete(f"/api/prompt/messages/{asst2.id}/pair")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["submission_deleted"])
        self.assertFalse(Message.objects.filter(id=asst2.id).exists())
        self.assertFalse(Message.objects.filter(id=user2.id).exists())

    def test_delete_message_pair_forbidden_for_other_user(self):
        other = _make_user("other")
        self.client.force_login(other)
        resp = self.client.delete(f"/api/prompt/messages/{self.asst_msg.id}/pair")
        self.assertEqual(resp.status_code, 403)


class PromptHistoryTest(TestCase):
    def setUp(self):
        self.user = _make_user("history-user")
        self.other = _make_user("history-other")
        self.task = _make_task()
        self.other_task = Task.objects.create(
            title="Other Task", task_type="challenge", display=2, content=""
        )

    def _pair(
        self,
        user,
        task,
        prompt,
        source="conversation",
        html="<main>page</main>",
        css="main { color: red; }",
        js="",
    ):
        conv = Conversation.objects.create(user=user, task=task)
        user_msg = Message.objects.create(
            conversation=conv,
            role="user",
            source=source,
            content=prompt,
        )
        asst_msg = Message.objects.create(
            conversation=conv,
            role="assistant",
            source=source,
            content="" if source == "manual" else "answer",
            code_html=html,
            code_css=css,
            code_js=js,
        )
        return user_msg, asst_msg

    def test_history_returns_ai_and_manual_prompt_rounds_with_page_code(self):
        ai_user, ai_asst = self._pair(self.user, self.task, "做一个登录页")
        manual_user, manual_asst = self._pair(
            self.user,
            self.task,
            "我让外部 AI 做一个卡片",
            source="manual",
            html="<section>card</section>",
        )

        self.client.force_login(self.user)
        resp = self.client.get(f"/api/prompt/history/{self.task.id}")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        ids = {item["user_message_id"] for item in data}
        self.assertEqual(ids, {ai_user.id, manual_user.id})
        by_source = {item["source"]: item for item in data}
        self.assertEqual(by_source["conversation"]["assistant_message_id"], ai_asst.id)
        self.assertEqual(by_source["conversation"]["prompt"], "做一个登录页")
        self.assertEqual(by_source["manual"]["assistant_message_id"], manual_asst.id)
        self.assertEqual(by_source["manual"]["code_html"], "<section>card</section>")
        self.assertNotIn("content", by_source["conversation"])

    def test_history_is_ordered_old_to_new(self):
        newest_user, newest_asst = self._pair(self.user, self.task, "第三条")
        oldest_user, oldest_asst = self._pair(self.user, self.task, "第一条")
        middle_user, middle_asst = self._pair(self.user, self.task, "第二条")
        base = timezone.now()
        for offset, user_msg, asst_msg in [
            (0, oldest_user, oldest_asst),
            (1, middle_user, middle_asst),
            (2, newest_user, newest_asst),
        ]:
            user_created = base + timedelta(minutes=offset)
            Message.objects.filter(id=user_msg.id).update(created=user_created)
            Message.objects.filter(id=asst_msg.id).update(
                created=user_created + timedelta(seconds=1)
            )

        self.client.force_login(self.user)
        resp = self.client.get(f"/api/prompt/history/{self.task.id}")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            [item["prompt"] for item in resp.json()],
            ["第一条", "第二条", "第三条"],
        )

    def test_history_is_scoped_to_current_user_and_task(self):
        own_user, _ = self._pair(self.user, self.task, "自己的提示词")
        self._pair(self.other, self.task, "别人的提示词")
        self._pair(self.user, self.other_task, "其他任务提示词")

        self.client.force_login(self.user)
        resp = self.client.get(f"/api/prompt/history/{self.task.id}")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["user_message_id"], own_user.id)
        self.assertEqual(data[0]["prompt"], "自己的提示词")

    def test_history_keeps_rounds_without_page_code(self):
        conv = Conversation.objects.create(user=self.user, task=self.task)
        user_msg = Message.objects.create(conversation=conv, role="user", content="只聊天")
        asst_msg = Message.objects.create(conversation=conv, role="assistant", content="没有代码")

        self.client.force_login(self.user)
        resp = self.client.get(f"/api/prompt/history/{self.task.id}")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["user_message_id"], user_msg.id)
        self.assertEqual(data[0]["assistant_message_id"], asst_msg.id)
        self.assertIsNone(data[0]["code_html"])
        self.assertIsNone(data[0]["code_css"])
        self.assertIsNone(data[0]["code_js"])


from prompt.llm import (
    DEFAULT_MODEL,
    GUIDANCE_SYSTEM_PROMPT,
    parse_guidance_response,
    stream_chat,
    stream_guidance,
)


class _FakeDelta:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.delta = _FakeDelta(content)


class _FakeChunk:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeStream:
    def __init__(self, chunks):
        self._chunks = iter(chunks)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return _FakeChunk(next(self._chunks))
        except StopIteration:
            raise StopAsyncIteration


class _FakeCompletions:
    def __init__(self):
        self.kwargs = None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return _FakeStream(["ok"])


class _FakeChat:
    def __init__(self, completions):
        self.completions = completions


class _FakeClient:
    def __init__(self):
        self.completions = _FakeCompletions()
        self.chat = _FakeChat(self.completions)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None


async def _collect_stream(stream):
    return [chunk async for chunk in stream]


class DeepSeekThinkingModeTest(TestCase):
    def test_stream_chat_disables_thinking_for_deepseek_flash(self):
        client = _FakeClient()

        with patch("prompt.llm._get_client", return_value=(client, DEFAULT_MODEL)):
            chunks = async_to_sync(_collect_stream)(
                stream_chat([{"role": "user", "content": "做一个按钮"}])
            )

        self.assertEqual(chunks, ["ok"])
        self.assertEqual(
            client.completions.kwargs["extra_body"],
            {"thinking": {"type": "disabled"}},
        )

    def test_stream_guidance_disables_thinking_for_deepseek_flash(self):
        client = _FakeClient()

        with patch("prompt.llm._get_client", return_value=(client, DEFAULT_MODEL)):
            chunks = async_to_sync(_collect_stream)(
                stream_guidance([{"role": "user", "content": "做一个页面"}])
            )

        self.assertEqual(chunks, ["ok"])
        self.assertEqual(
            client.completions.kwargs["extra_body"],
            {"thinking": {"type": "disabled"}},
        )

    def test_stream_chat_thinking_option_uses_deepseek_flash_without_disabling_thinking(self):
        client = _FakeClient()

        with patch("prompt.llm.AsyncOpenAI", return_value=client):
            chunks = async_to_sync(_collect_stream)(
                stream_chat(
                    [{"role": "user", "content": "做一个按钮"}],
                    model="deepseek-v4-flash-thinking",
                )
            )

        self.assertEqual(chunks, ["ok"])
        self.assertEqual(client.completions.kwargs["model"], DEFAULT_MODEL)
        self.assertNotIn("extra_body", client.completions.kwargs)


class ParseGuidanceResponseTest(TestCase):
    def test_guidance_prompt_asks_for_bold_keywords(self):
        self.assertIn("Markdown", GUIDANCE_SYSTEM_PROMPT)
        self.assertIn("[READY] 不要加粗", GUIDANCE_SYSTEM_PROMPT)
        for keyword in ("**主题**", "**视觉**", "**交互**", "**内容**", "**可以生成**"):
            self.assertIn(keyword, GUIDANCE_SYSTEM_PROMPT)

    def test_ready_prefix_with_newline_stripped(self):
        content, is_ready = parse_guidance_response("[READY]\n很好，可以生成了！")
        self.assertEqual(content, "很好，可以生成了！")
        self.assertTrue(is_ready)

    def test_ready_prefix_without_newline_stripped(self):
        content, is_ready = parse_guidance_response("[READY]很好，可以生成了！")
        self.assertEqual(content, "很好，可以生成了！")
        self.assertTrue(is_ready)

    def test_no_ready_prefix_unchanged(self):
        content, is_ready = parse_guidance_response("你的提示词不够具体，请问...")
        self.assertEqual(content, "你的提示词不够具体，请问...")
        self.assertFalse(is_ready)

    def test_empty_string(self):
        content, is_ready = parse_guidance_response("")
        self.assertEqual(content, "")
        self.assertFalse(is_ready)
