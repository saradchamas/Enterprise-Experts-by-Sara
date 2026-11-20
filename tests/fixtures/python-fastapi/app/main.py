from fastapi import FastAPI
from openai import OpenAI
from sqlalchemy import create_engine, text

app = FastAPI()
client = OpenAI()
engine = create_engine("sqlite:///questions.db")


def answer(question: str) -> str:
    return question.strip()


@app.post("/ask")
def ask(question: str) -> dict:
    reply = client.chat.completions.create(model="example-model", messages=[{"role": "user", "content": question}])
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO questions (body) VALUES (:q)"), {"q": question})
    return {"answer": reply.choices[0].message.content}
