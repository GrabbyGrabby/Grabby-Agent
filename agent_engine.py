import os
import logging
from dotenv import load_dotenv
from langchain.tools import tool
from duckduckgo_search import DDGS
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("agent_engine")

# 1. Define tools
@tool
def search(query: str) -> str:
    """Search the web for up-to-date information on a topic."""
    try:
        # Use ddgs directly with a strict 2.5 second timeout to stay within Vercel's limits
        with DDGS(timeout=2.5) as ddgs:
            results = list(ddgs.text(query, max_results=3))
            if not results:
                return "No search results found."
            formatted = []
            for r in results:
                formatted.append(f"Title: {r.get('title')}\nLink: {r.get('href')}\nSnippet: {r.get('body')}\n")
            return "\n".join(formatted)
    except Exception as e:
        return f"Search tool timed out or failed: {str(e)}"

@tool
def word_count(text: str) -> int:
    """Count how many words are in a piece of text."""
    return len(text.split())

tools = [search, word_count]

# 2. Model Fallback Factory
def get_model():
    """Attempt to initialize models in order of priority, linking them with dynamic runtime fallbacks."""
    models_list = []
    
    # Priority 1: Gemini
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        try:
            logger.info("Configuring Google Gemini model...")
            model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=gemini_key)
            models_list.append(model)
        except Exception as e:
            logger.error(f"Error configuring Gemini model: {e}")
    else:
        logger.info("Gemini API key not provided.")
 
    # Priority 2: OpenRouter
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_key:
        try:
            logger.info("Configuring OpenRouter model...")
            model = ChatOpenAI(
                model="meta-llama/llama-3.3-70b-instruct:free",
                api_key=openrouter_key,
                base_url="https://openrouter.ai/api/v1"
            )
            models_list.append(model)
        except Exception as e:
            logger.error(f"Error configuring OpenRouter model: {e}")
    else:
        logger.info("OpenRouter API key not provided.")
 
    # Priority 3: Nvidia NIM
    nvidia_key = os.getenv("NVIDIA_API_KEY") or os.getenv("NVIDIA_NIM_API_KEY")
    if nvidia_key:
        try:
            logger.info("Configuring Nvidia NIM model...")
            model = ChatOpenAI(
                model="meta/llama-3.3-70b-instruct",
                api_key=nvidia_key,
                base_url="https://integrate.api.nvidia.com/v1"
            )
            models_list.append(model)
        except Exception as e:
            logger.error(f"Error configuring Nvidia NIM model: {e}")
    else:
        logger.info("Nvidia API key not provided.")
 
    # Priority 4: Mistral AI
    mistral_key = os.getenv("MISTRAL_API_KEY")
    mistral_url = os.getenv("MISTRAL_BASE_URL", "https://api.mistral.ai/v1")
    if mistral_key:
        try:
            logger.info("Configuring Mistral model...")
            model = ChatOpenAI(
                model="mistral-large-latest",
                api_key=mistral_key,
                base_url=mistral_url
            )
            models_list.append(model)
        except Exception as e:
            logger.error(f"Error configuring Mistral model: {e}")
    else:
        logger.info("Mistral API key not provided.")
 
    if not models_list:
        raise RuntimeError("No LLM keys configured. Please add GEMINI_API_KEY or OPENROUTER_API_KEY to your Environment Variables.")
 
    # Apply the fallback chain
    primary_model = models_list[0]
    if len(models_list) > 1:
        logger.info(f"Configuring dynamic fallback chain: {', '.join([type(m).__name__ for m in models_list])}")
        return primary_model.with_fallbacks(models_list[1:])
    else:
        return primary_model

# 3. Create the Agent
def get_agent():
    """Get the compiled LangGraph React Agent with Memory."""
    model = get_model()
    # InMemorySaver persists memory state during execution context
    checkpointer = InMemorySaver()
    
    agent = create_react_agent(
        model=model,
        tools=tools,
        prompt="You are a helpful assistant. Use your tools when they help answer accurately. Be concise and precise.",
        checkpointer=checkpointer
    )
    return agent
