import re
import time
import logging
from uuid import UUID

from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)

CLASSIFY_SYSTEM_PROMPT = """你是一个教育评估专家。根据布鲁姆认知分类学，分析以下学生在前端学习中发送给AI助手的一条提示词，判断该提示词所体现的认知层级。

层级定义：
- L1 记忆：能背诵HTML标签语法（例："帮我写一个按钮"）
- L2 理解：能解释flex布局原理（例："为什么这里不居中？"）
- L3 应用：能独立搭建页面结构（例："用flex做导航栏，间距16px"）
- L4 分析：能定位跨浏览器兼容性bug（例："Safari中margin失效，原因？"）
- L5 评价：能对比并选择方案（例："对比Grid与Flex方案优劣"）
- L6 创造：能设计并实现原创交互作品（例："设计夜间/日间切换效果"）

只返回一个数字（1-6），不要解释。"""


def _call_llm(content: str) -> int | None:
    """Call LLM to classify a single message content. Returns level 1-6 or None."""
    try:
        client = OpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            timeout=30.0,
        )
        response = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": CLASSIFY_SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            max_tokens=10,
            stream=False,
        )
        text = response.choices[0].message.content or ""
        match = re.search(r"[1-6]", text)
        if not match:
            logger.warning("classify: unexpected LLM response '%s'", text)
            return None
        return int(match.group())
    except Exception as e:
        logger.error("classify LLM call failed: %s", e)
        return None


def classify_message(message_id: int) -> int | None:
    """Classify a single user Message by ID. Returns level or None."""
    from prompt.models import Message

    try:
        msg = Message.objects.get(id=message_id, role="user")
    except Message.DoesNotExist:
        return None

    level = _call_llm(msg.content)
    if level is not None:
        Message.objects.filter(id=message_id).update(prompt_level=level)
    return level


def classify_conversation_messages(conversation_id: UUID, force: bool = False) -> None:
    """Classify all user messages in a conversation."""
    from prompt.models import Message

    qs = Message.objects.filter(conversation_id=conversation_id, role="user")
    if not force:
        qs = qs.filter(prompt_level__isnull=True)

    for msg in qs.order_by("created"):
        level = _call_llm(msg.content)
        if level is not None:
            Message.objects.filter(id=msg.id).update(prompt_level=level)
        time.sleep(0.3)


def classify_messages_batch(message_ids: list) -> None:
    """Classify a list of messages by ID."""
    for mid in message_ids:
        classify_message(mid)
        time.sleep(0.5)
