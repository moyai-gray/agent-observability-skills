from groq import Groq

client = Groq()


def triage(ticket: str) -> str:
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "Reply with one word: bug, billing or other."},
            {"role": "user", "content": ticket},
        ],
    )
    return completion.choices[0].message.content


if __name__ == "__main__":
    print(triage("The invoice total is wrong."))
