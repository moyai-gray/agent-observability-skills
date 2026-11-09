from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent


@tool
def get_weather(city: str) -> str:
    """Get the weather for a city."""
    return f"It is sunny in {city}."


agent = create_react_agent(ChatOpenAI(model="gpt-4.1-mini"), tools=[get_weather])

if __name__ == "__main__":
    result = agent.invoke({"messages": [{"role": "user", "content": "Weather in Paris?"}]})
    print(result["messages"][-1].content)
