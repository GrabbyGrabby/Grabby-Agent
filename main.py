import os
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from mangum import Mangum

from agent_engine import get_agent
from cloudflare_dns import sync_cloudflare_dns

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("main_server")

app = FastAPI(title="Free AI Agent Portal", description="FastAPI Backend for LLM Agent with Fallback & CF DNS")
handler = Mangum(app)

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup event to run Cloudflare DNS sync
@app.on_event("startup")
async def startup_event():
    logger.info("Starting up FastAPI application...")
    try:
        success = sync_cloudflare_dns()
        if success:
            logger.info("Cloudflare DNS record synchronized successfully.")
        else:
            logger.warning("Cloudflare DNS sync did not complete or was skipped.")
    except Exception as e:
        logger.error(f"Error during startup Cloudflare DNS sync: {e}")

class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default-session"

class ChatResponse(BaseModel):
    reply: str
    thread_id: str

# Cache the agent instance
agent_instance = None

def get_cached_agent():
    global agent_instance
    if agent_instance is None:
        agent_instance = get_agent()
    return agent_instance

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        agent = get_cached_agent()
        config = {"configurable": {"thread_id": request.thread_id}}
        
        # Invoke agent
        logger.info(f"Invoking agent with session {request.thread_id} and query: {request.message}")
        result = agent.invoke(
            {"messages": [{"role": "user", "content": request.message}]},
            config=config
        )
        
        # Extract response
        messages = result.get("messages", [])
        if not messages:
            raise HTTPException(status_code=500, detail="Agent returned no messages.")
            
        raw_content = messages[-1].content
        if isinstance(raw_content, str):
            reply = raw_content
        elif isinstance(raw_content, list):
            text_parts = []
            for part in raw_content:
                if isinstance(part, str):
                    text_parts.append(part)
                elif isinstance(part, dict) and "text" in part:
                    text_parts.append(part["text"])
            reply = "".join(text_parts)
        else:
            reply = str(raw_content)

        return ChatResponse(reply=reply, thread_id=request.thread_id)
        
    except Exception as e:
        logger.error(f"Error processing chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/dns-sync")
async def dns_sync_endpoint():
    try:
        success = sync_cloudflare_dns()
        return {"status": "success" if success else "failed", "message": "DNS sync process finished."}
    except Exception as e:
        logger.error(f"Error triggering DNS sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Serve static web interface
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

# Mount the static files
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def get_index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Server is running, but static/index.html is missing."}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run("main:app", host=host, port=port, reload=True)
