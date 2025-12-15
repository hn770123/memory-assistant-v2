from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import List, Optional
import os
from database import init_db, get_memories, add_memory, delete_memory, update_memory
from ai_engine import AIEngine

app = FastAPI(title="AI Secretary")

# Initialize DB
init_db()

# Initialize AI Engine
ai_engine = AIEngine()

# Serve Static Files
app.mount("/static", StaticFiles(directory="static"), name="static")

class ChatRequest(BaseModel):
    message: str
    test_mode: bool = False

class ChatResponse(BaseModel):
    response: str
    context_used: Optional[str] = None

class MemoryItem(BaseModel):
    category: str
    content: str

class MemoryUpdate(BaseModel):
    category: str
    content: str

@app.get("/")
async def read_root():
    return FileResponse("static/index.html")

@app.get("/admin")
async def read_admin():
    return FileResponse("static/admin.html")

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    result = await ai_engine.chat(request.message, request.test_mode)
    return ChatResponse(
        response=result["response"],
        context_used=result["context_used"]
    )

@app.get("/api/memories")
async def get_all_memories(category: Optional[str] = None):
    return get_memories(category)

@app.post("/api/memories")
async def create_memory(item: MemoryItem):
    add_memory(item.category, item.content)
    return {"status": "success"}

@app.put("/api/memories/{memory_id}")
async def update_memory_item(memory_id: int, item: MemoryUpdate):
    update_memory(memory_id, item.content, item.category)
    return {"status": "success"}

@app.delete("/api/memories/{memory_id}")
async def delete_memory_item(memory_id: int):
    delete_memory(memory_id)
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
