import anthropic

client = anthropic.Anthropic()


def classify(ticket: str) -> str:
    message = client.messages.create(
        model="claude-haiku-5-5",
        max_tokens=16,
        messages=[{"role": "user", "content": f"Classify as bug/billing/other: {ticket}"}],
    )
    return message.content[0].text


if __name__ == "__main__":
    print(classify("I was charged twice."))
