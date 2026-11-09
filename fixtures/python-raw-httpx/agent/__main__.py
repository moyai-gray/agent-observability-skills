from agent.llm import chat

if __name__ == "__main__":
    print(chat([{"role": "user", "content": "Say hello."}]))
