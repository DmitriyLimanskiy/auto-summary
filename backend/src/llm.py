from pathlib import Path

from openai import AsyncOpenAI, OpenAIError

from .config import LLM_API_KEY, LLM_SERVER_URL

ai_client = AsyncOpenAI(api_key=LLM_API_KEY, base_url=LLM_SERVER_URL)

SYSTEM_PROMPT = Path("src/prompts/sys_prompt_2.txt").read_text(encoding="utf-8")


async def generate_summary(transcript: str, model_id: str) -> str:
    """
    Отправляет транскрипт в LM Studio и возвращает сгенерированный Markdown.
    """
    try:
        response = await ai_client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Вот транскрипт встречи:\n\n{transcript}"},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content
    except OpenAIError as e:
        raise RuntimeError(f"Ошибка при обращении к LLM SERVER: {str(e)}")
