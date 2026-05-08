import re
from django.conf import settings
from openai import AsyncOpenAI


SYSTEM_PROMPT = """你是一个网页生成助手。根据用户的需求描述，生成 HTML、CSS 和 JavaScript 代码。

规则：
1. 始终使用三个独立的代码块返回代码，分别用 ```html、```css、```js 标记
2. HTML 代码只需要 body 内的内容，不需要完整的 HTML 文档结构
3. CSS 和 JS 可以为空，但仍然需要返回空的代码块
4. 用中文回复，先简要说明你做了什么，然后给出代码
5. 在已有代码基础上修改时，返回完整的修改后代码，不要只返回片段
6. 由于任何外部链接都被屏蔽，使用纯 HTML、CSS 和 JS 实现功能，不要依赖外部库

输出格式示例（必须严格遵守，三个代码块缺一不可）：

好的，我为你创建了一个点击按钮变色的示例。

```html
<button id="btn">点击我</button>
```

```css
button { padding: 8px 16px; }
```

```js
document.getElementById('btn').onclick = function() {
  this.style.background = 'red';
};
```"""

GUIDANCE_SYSTEM_PROMPT = """你是一个提示词写作教练，帮助学生写出清晰、具体的网页需求描述。

判断标准——满足以下条件视为"够好"：
- 有明确主题（例如：登录页、计时器、商品卡片列表）
- 至少包含以下一项具体描述：颜色/布局/风格、交互行为（按钮点击、动画等）、页面内容（文字、数量、图标）

判断为"不够好"的典型情况：
- 目标太泛，如"做一个好看的页面"
- 只有主题，完全没有任何视觉、交互或内容描述

规则：
1. 如果提示词不够好，用 1-2 个启发性问题引导学生补充细节，不要直接给出答案
2. 如果提示词已经够好，以 [READY] 开头回复，简短夸奖学生并说明可以生成了
3. 用中文回复，语气鼓励，简洁明了
4. 使用 Markdown 语法高亮关键词，优先突出 **主题**、**视觉**、**交互**、**内容**、**可以生成** 等重点
5. 如果回复以 [READY] 开头，[READY] 不要加粗，必须保持原始文本
6. 不要生成任何代码"""

DEFAULT_MODEL = "deepseek-v4-flash"
DEEPSEEK_THINKING_MODEL = "deepseek-v4-flash-thinking"
MODEL_ALIASES = {
    DEEPSEEK_THINKING_MODEL: DEFAULT_MODEL,
}
NON_THINKING_MODELS = {"deepseek-v4-flash"}
NON_THINKING_EXTRA_BODY = {"thinking": {"type": "disabled"}}

# Models served by the ARK (Volcengine) endpoint
ARK_MODELS = {"doubao-seed-2-0-lite-260215"}


def build_messages(history: list[dict]) -> list[dict]:
    """Build the message list for the LLM API call."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    return messages


def _get_client(model: str) -> tuple[AsyncOpenAI, str]:
    """Return (client, model_id) for the given model name."""
    requested_model = model or DEFAULT_MODEL
    resolved_model = MODEL_ALIASES.get(requested_model, requested_model)
    if resolved_model in ARK_MODELS:
        return (
            AsyncOpenAI(
                api_key=settings.ARK_API_KEY,
                base_url=settings.ARK_BASE_URL,
                timeout=120.0,
            ),
            resolved_model,
        )
    return (
        AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            timeout=120.0,
        ),
        resolved_model,
    )


def _should_disable_thinking(requested_model: str, resolved_model: str) -> bool:
    return (
        resolved_model in NON_THINKING_MODELS
        and requested_model not in MODEL_ALIASES
    )


def _chat_completion_kwargs(
    requested_model: str,
    resolved_model: str,
    messages: list[dict],
    stream: bool,
) -> dict:
    kwargs = {
        "model": resolved_model,
        "messages": messages,
        "stream": stream,
    }
    if _should_disable_thinking(requested_model, resolved_model):
        kwargs["extra_body"] = NON_THINKING_EXTRA_BODY
    return kwargs


async def stream_chat(history: list[dict], model: str = ""):
    """Stream chat completion from the LLM. Yields content chunks."""
    messages = build_messages(history)
    client, resolved_model = _get_client(model)
    requested_model = model or DEFAULT_MODEL
    async with client as c:
        stream = await c.chat.completions.create(
            **_chat_completion_kwargs(
                requested_model,
                resolved_model,
                messages,
                stream=True,
            ),
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content


def extract_code(text: str) -> dict:
    """Extract HTML, CSS, JS code blocks from AI response text."""
    result = {"html": None, "css": None, "js": None}
    pattern = r"```(html|css|js|javascript|typescript|ts|jsx|tsx)\s*\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
    for lang, code in matches:
        lang = lang.lower()
        if lang in ("javascript", "typescript", "ts", "jsx", "tsx"):
            lang = "js"
        if lang in result and result[lang] is None:
            result[lang] = code.strip()

    # Fallback: extract <style> and <script> from HTML block
    if result["html"]:
        if result["css"] is None:
            style_match = re.search(r"<style[^>]*>(.*?)</style>", result["html"], re.DOTALL | re.IGNORECASE)
            if style_match:
                result["css"] = style_match.group(1).strip()

        if result["js"] is None:
            script_match = re.search(r"<script[^>]*>(.*?)</script>", result["html"], re.DOTALL | re.IGNORECASE)
            if script_match:
                result["js"] = script_match.group(1).strip()

    return result


def parse_guidance_response(full_response: str) -> tuple[str, bool]:
    if full_response.startswith("[READY]"):
        return full_response[len("[READY]"):].lstrip("\n"), True
    return full_response, False


async def stream_guidance(history: list[dict]):
    """Stream guidance coaching response. Yields content chunks."""
    messages = [{"role": "system", "content": GUIDANCE_SYSTEM_PROMPT}]
    messages.extend(history)
    client, model = _get_client("")
    requested_model = DEFAULT_MODEL
    async with client as c:
        stream = await c.chat.completions.create(
            **_chat_completion_kwargs(
                requested_model,
                model,
                messages,
                stream=True,
            ),
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content
