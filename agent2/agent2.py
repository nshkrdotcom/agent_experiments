import datetime
from zoneinfo import ZoneInfo
from google.adk.agents import Agent

def get_news(city: str) -> dict:
    """Retrieves the newws  a specified city.

    Args:
        city (str): The name of the city for which to retrieve the newxs report.

    Returns:
        dict: status and result or error msg.
    """
    if city.lower() == "new york":
        return {
            "status": "success",
            "report": (
                "The news in New York is sunny with a temperature of 25 degrees"
                " Celsius (77 degrees Fahrenheit)."
            ),
        }
    else:
        return {
            "status": "error",
            "error_message": f"Weather information for '{city}' is not available.",
        }


 

root_agent = Agent(
    name="weather_news_agent",
    model="gemini-2.0-flash",
    description=(
        "Agent to answer questions about the news in a city."
    ),
    instruction=(
        "You are a helpful agent who can answer user questions about the news in a city."
    ),
    tools=[get_news],
)
