import re
from django.conf import settings
from openai import AsyncOpenAI


client = AsyncOpenAI(
    api_key=settings.LLM_API_KEY,
    base_url=settings.LLM_BASE_URL,
)

SYSTEM_PROMPT = """你是一个网页生成助手。根据用户的需求描述，生成 HTML、CSS 和 JavaScript 代码。

规则：
1. 始终使用三个独立的代码块返回代码，分别用 ```html、```css、```js 标记
2. HTML 代码只需要 body 内的内容，不需要完整的 HTML 文档结构
3. CSS 和 JS 可以为空，但仍然需要返回空的代码块
4. 用中文回复，先简要说明你做了什么，然后给出代码
5. 在已有代码基础上修改时，返回完整的修改后代码，不要只返回片段"""


def build_messages(task_content: str, history: list[dict]) -> list[dict]:
    """Build the message list for the LLM API call."""
    system = SYSTEM_PROMPT + f"\n\n当前挑战任务要求：\n{task_content}"
    messages = [{"role": "system", "content": system}]
    messages.extend(history)
    return messages


async def stream_chat(task_content: str, history: list[dict]):
    """Stream chat completion from the LLM. Yields content chunks."""
    messages = build_messages(task_content, history)
    stream = await client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=messages,
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta
        if delta.content:
            yield delta.content


def extract_code(text: str) -> dict:
    """Extract HTML, CSS, JS code blocks from AI response text."""
    result = {"html": None, "css": None, "js": None}
    pattern = r"```(html|css|js|javascript)\s*\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    for lang, code in matches:
        lang = lang.lower()
        if lang == "javascript":
            lang = "js"
        if lang in result:
            result[lang] = code.strip()
    return result
