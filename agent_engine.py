import os
import logging
from dotenv import load_dotenv
from langchain.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("agent_engine")

# 1. Define Tools
search = DuckDuckGoSearchRun()

@tool
def word_count(text: str) -> int:
    """Count how many words are in a piece of text."""
    return len(text.split())

tools = [search, word_count]

# 2. Model Fallback Factory
def get_model():
    """Attempt to initialize models in order of priority: Groq -> Gemini -> OpenRouter -> Nvidia."""
    
    # Priority 1: Gemini
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        try:
            logger.info("Attempting to initialize Google Gemini model...")
            model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=gemini_key)
            model.invoke("ping")  # verify API works
            logger.info("Successfully connected to Google Gemini.")
            return model
        except Exception as e:
            logger.warning(f"Google Gemini initialization failed: {e}")
    else:
        logger.info("Gemini API key not provided.")

    # Priority 2: OpenRouter
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_key:
        try:
            logger.info("Attempting to initialize OpenRouter model...")
            model = ChatOpenAI(
                model="meta-llama/llama-3.3-70b-instruct:free",
                api_key=openrouter_key,
                base_url="https://openrouter.ai/api/v1"
            )
            model.invoke("ping")
            logger.info("Successfully connected to OpenRouter (Llama 3.3 70B).")
            return model
        except Exception as e:
            logger.warning(f"OpenRouter initialization failed: {e}")
    else:
        logger.info("OpenRouter API key not provided.")

    # Priority 3: Nvidia NIM
    nvidia_key = os.getenv("NVIDIA_API_KEY") or os.getenv("NVIDIA_NIM_API_KEY")
    if nvidia_key:
        try:
            logger.info("Attempting to initialize Nvidia NIM model...")
            model = ChatOpenAI(
                model="meta/llama-3.3-70b-instruct",
                api_key=nvidia_key,
                base_url="https://integrate.api.nvidia.com/v1"
            )
            model.invoke("ping")
            logger.info("Successfully connected to Nvidia NIM.")
            return model
        except Exception as e:
            logger.warning(f"Nvidia NIM initialization failed: {e}")
    else:
        logger.info("Nvidia API key not provided.")

    # Priority 4: Mistral AI
    mistral_key = os.getenv("MISTRAL_API_KEY")
    mistral_url = os.getenv("MISTRAL_BASE_URL", "https://api.mistral.ai/v1")
    if mistral_key:
        try:
            logger.info("Attempting to initialize Mistral model...")
            model = ChatOpenAI(
                model="mistral-large-latest",
                api_key=mistral_key,
                base_url=mistral_url
            )
            model.invoke("ping")
            logger.info("Successfully connected to Mistral AI.")
            return model
        except Exception as e:
            logger.warning(f"Mistral AI initialization failed: {e}")
    else:
        logger.info("Mistral API key not provided.")

    # Ultimate fallback: Raise error if no models can be loaded
    raise RuntimeError("No LLM providers could be initialized. Please check your API keys in the .env file.")

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
