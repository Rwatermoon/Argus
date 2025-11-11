import os
import logging
import google.generativeai as genai
import openai
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

try:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
    else:
        logger.warning("GEMINI_API_KEY not set. AI evaluation will not be available.")
except Exception as e:
    logger.error(f"Failed to configure Gemini client: {e}")
    GEMINI_API_KEY = None

# Load keys for OpenAI compatible APIs
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

def format_route_details_for_prompt(route_details):
    """Formats the route details dictionary into a human-readable string for the AI prompt."""
    if not route_details:
        return "No data available."
    
    distance_km = (route_details.get('distance', 0) / 1000)
    duration_min = (route_details.get('duration', 0) / 60)
    instructions = "\n".join([f"- {inst}" for inst in route_details.get('instructions', [])[:5]]) # Limit to first 5 instructions

    return (
        f"Distance: {distance_km:.2f} km\n"
        f"Duration: {duration_min:.1f} minutes\n"
        f"First 5 Instructions:\n{instructions}"
    )

def stream_gemini_evaluation(route_stats, user_prompt):
    """
    Streams an evaluation from the Gemini API based on route statistics and a user prompt.
    """
    if not GEMINI_API_KEY:
        yield "Error: Gemini API key is not configured."
        return

    # Use the latest stable model name
    model = genai.GenerativeModel('gemini-1.0-pro')

    google_details = format_route_details_for_prompt(route_stats.get('google_details'))
    here_details = format_route_details_for_prompt(route_stats.get('here_details'))
    osm_details = format_route_details_for_prompt(route_stats.get('osm_details'))

    system_prompt = f"""You are an expert transportation and logistics analyst. Your task is to compare three route options based on the data provided and the user's request. Be concise and insightful.
Here is the data for the three routes:
--- Google Route ---
{google_details}
--- HERE Route ---
{here_details}
--- OSM Route ---
{osm_details}
---
User's request: "{user_prompt}"

Your analysis:"""

    try:
        # Use the official SDK for a simpler and more reliable implementation
        response = model.generate_content(system_prompt, stream=True)
        for chunk in response:
            yield chunk.text
    except Exception as e:
        logger.error(f"Error during Gemini API call: {e}")
        yield f"An error occurred while contacting the AI: {e}"

def stream_openai_compatible_evaluation(provider, route_stats, user_prompt):
    """
    Streams an evaluation from an OpenAI-compatible API (like OpenAI or DeepSeek).
    """
    api_key = None
    base_url = None
    model = "gpt-3.5-turbo" # Default for OpenAI

    if provider == 'chatgpt':
        api_key = OPENAI_API_KEY
        if not api_key:
            yield "Error: OPENAI_API_KEY not set."
            return
    elif provider == 'deepseek':
        api_key = DEEPSEEK_API_KEY
        base_url = "https://api.deepseek.com/v1"
        model = "deepseek-chat"
        if not api_key:
            yield "Error: DEEPSEEK_API_KEY not set."
            return
    else:
        yield f"Error: Unknown AI provider '{provider}'."
        return

    client = openai.OpenAI(api_key=api_key, base_url=base_url)

    google_details = format_route_details_for_prompt(route_stats.get('google_details'))
    here_details = format_route_details_for_prompt(route_stats.get('here_details'))
    osm_details = format_route_details_for_prompt(route_stats.get('osm_details'))

    system_prompt = f"""You are an expert transportation and logistics analyst. Your task is to compare three route options based on the data provided and the user's request. Be concise and insightful.
Here is the data for the three routes:
--- Google Route ---
{google_details}
--- HERE Route ---
{here_details}
--- OSM Route ---
{osm_details}
---"""

    try:
        stream = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            stream=True,
        )
        for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                yield content
    except Exception as e:
        logger.error(f"Error during {provider} API call: {e}")
        yield f"An error occurred while contacting the AI: {e}"