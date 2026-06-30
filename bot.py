import os
from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def generate_reply(comment, context, style="medium"):

    prompt = f"""
You are a YouTube creator.

RULES:
- no hallucination
- no fake facts
- no marketing tone
- 1–2 sentences max

VIDEO CONTEXT:
{context}

COMMENT:
{comment}

STYLE:
{style}

Reply:
"""

    res = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )

    return res.choices[0].message.content.strip()
