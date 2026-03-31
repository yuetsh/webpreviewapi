import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.db.models import Count
from .models import Conversation, Message
from .llm import stream_chat, extract_code


class PromptConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if self.user.is_anonymous:
            await self.close()
            return

        self.task_id = int(self.scope["url_route"]["kwargs"]["task_id"])
        self.current_user_message = None
        await self.accept()

        # Load or create conversation, send history
        self.conversation = await self.get_or_create_conversation()
        history = await self.get_history()
        await self.send(text_data=json.dumps({
            "type": "init",
            "conversation_id": str(self.conversation.id),
            "messages": history,
        }))

    async def disconnect(self, close_code):
        if self.current_user_message:
            await self.delete_message(self.current_user_message)
            self.current_user_message = None

    async def receive(self, text_data):
        data = json.loads(text_data)
        msg_type = data.get("type", "message")

        if msg_type == "new_conversation":
            return

        prompt = data.get("content", "").strip()
        model = data.get("model", "")
        if not prompt:
            return

        # Save user message
        self.current_user_message = await self.save_message("user", prompt)

        try:
            # Build history for LLM
            history = await self.get_history_for_llm()

            # Stream AI response
            full_response = ""
            try:
                async for chunk in stream_chat(history, model=model):
                    full_response += chunk
                    await self.send(text_data=json.dumps({
                        "type": "stream",
                        "content": chunk,
                    }))
            except Exception as e:
                await self.send(text_data=json.dumps({
                    "type": "error",
                    "content": f"AI 服务出错：{str(e)}",
                }))
                return

            # Extract code and save assistant message
            code = extract_code(full_response)
            await self.save_message("assistant", full_response, code)
            self.current_user_message = None

            # Send completion with extracted code
            await self.send(text_data=json.dumps({
                "type": "complete",
                "code": code,
            }))

        finally:
            if self.current_user_message:
                await self.delete_message(self.current_user_message)
                self.current_user_message = None

    @database_sync_to_async
    def get_or_create_conversation(self):
        conv = (
            Conversation.objects.filter(user=self.user, task_id=self.task_id)
            .annotate(msg_count=Count("messages"))
            .order_by("-msg_count", "-created")
            .first()
        )
        if not conv:
            conv = Conversation.objects.create(user=self.user, task_id=self.task_id)
        return conv

    @database_sync_to_async
    def delete_message(self, message):
        message.delete()

    @database_sync_to_async
    def save_message(self, role, content, code=None):
        return Message.objects.create(
            conversation=self.conversation,
            role=role,
            content=content,
            code_html=code.get("html") if code else None,
            code_css=code.get("css") if code else None,
            code_js=code.get("js") if code else None,
        )

    @database_sync_to_async
    def get_history(self):
        messages = self.conversation.messages.filter(source="conversation")
        return [
            {
                "role": m.role,
                "content": m.content,
                "code": {
                    "html": m.code_html,
                    "css": m.code_css,
                    "js": m.code_js,
                } if m.role == "assistant" else None,
                "created": m.created.isoformat(),
            }
            for m in messages
        ]

    @database_sync_to_async
    def get_history_for_llm(self):
        messages = self.conversation.messages.filter(source="conversation")
        return [{"role": m.role, "content": m.content} for m in messages]
