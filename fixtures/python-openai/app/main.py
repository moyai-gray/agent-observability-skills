from fastapi import FastAPI
from openai import OpenAI
from pydantic import BaseModel

app = FastAPI()
client = OpenAI()


class Ask(BaseModel):
    question: str


@app.post("/ask")
def ask(body: Ask) -> dict:
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": body.question}],
    )
    return {"answer": response.choices[0].message.content}
