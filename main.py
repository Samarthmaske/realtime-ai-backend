import asyncio
import json
import uuid
from datetime import datetime
from typing import Optional
import os
from dotenv import load_dotenv

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

from supabase import create_client, Client
import anthropic

load_dotenv()

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Initialize clients
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

app = FastAPI()

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def get_root():
    return FileResponse("static/index.html")

class SessionManager:
    def __init__(self):
        self.active_connections: dict = {}
        self.session_states: dict = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        self.session_states[session_id] = {
            "messages": [],
            "user_id": str(uuid.uuid4()),
            "start_time": datetime.utcnow().isoformat(),
        }

    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]

    async def send_message(self, session_id: str, message: dict):
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(message)

    def get_session_state(self, session_id: str):
        return self.session_states.get(session_id, {})

    def update_session_state(self, session_id: str, state: dict):
        if session_id in self.session_states:
            self.session_states[session_id].update(state)

manager = SessionManager()

# Tool functions
def fetch_user_data(user_id: str) -> dict:
    return {
        "user_id": user_id,
        "name": f"User {user_id[:8]}",
        "email": f"user{user_id[:8]}@example.com",
        "account_status": "active",
    }

def fetch_conversation_analytics(session_id: str) -> dict:
    return {
        "session_id": session_id,
        "message_count": 5,
        "avg_response_time": 1.2,
        "sentiment": "positive",
    }

def process_tool_call(tool_name: str, tool_input: dict) -> str:
    if tool_name == "fetch_user_data":
        result = fetch_user_data(tool_input.get("user_id", "unknown"))
        return json.dumps(result)
    elif tool_name == "fetch_conversation_analytics":
        result = fetch_conversation_analytics(tool_input.get("session_id", "unknown"))
        return json.dumps(result)
    return json.dumps({"error": "Unknown tool"})

async def stream_llm_response(session_id: str, messages: list) -> str:
    tools = [
        {
            "name": "fetch_user_data",
            "description": "Fetch user profile information",
            "input_schema": {
                "type": "object",
                "properties": {"user_id": {"type": "string"}},
                "required": ["user_id"]
            }
        },
        {
            "name": "fetch_conversation_analytics",
            "description": "Fetch conversation analytics",
            "input_schema": {
                "type": "object",
                "properties": {"session_id": {"type": "string"}},
                "required": ["session_id"]
            }
        }
    ]

    system_prompt = "You are a helpful AI assistant. Use tools when appropriate."
    response_text = ""

    response = claude.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        system=system_prompt,
        tools=tools,
        messages=messages
    )

    while response.stop_reason == "tool_use":
        for block in response.content:
            if hasattr(block, 'text'):
                response_text += block.text

        tool_calls = [block for block in response.content if block.type == "tool_use"]

        for tool_call in tool_calls:
            tool_result = process_tool_call(tool_call.name, tool_call.input)
            await manager.send_message(session_id, {
                "type": "tool_use",
                "tool": tool_call.name,
                "status": "completed"
            })

        messages_with_response = messages + [{"role": "assistant", "content": response.content}]
        tool_results = [{"type": "tool_result", "tool_use_id": tool_call.id, "content": process_tool_call(tool_call.name, tool_call.input)} for tool_call in tool_calls]
        messages_with_response.append({"role": "user", "content": tool_results})

        response = claude.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            system=system_prompt,
            tools=tools,
            messages=messages_with_response
        )

    for block in response.content:
        if hasattr(block, 'text'):
            response_text += block.text

    return response_text

async def log_event(session_id: str, event_type: str, data: dict):
    try:
        event_record = {
            "session_id": session_id,
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": json.dumps(data)
        }
        supabase.table("event_logs").insert(event_record).execute()
    except Exception as e:
        print(f"Error logging event: {e}")

@app.websocket("/ws/session/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    try:
        session_record = {
            "session_id": session_id,
            "user_id": manager.get_session_state(session_id)["user_id"],
            "start_time": manager.get_session_state(session_id)["start_time"],
            "status": "active"
        }
        supabase.table("sessions").insert(session_record).execute()

        await manager.send_message(session_id, {"type": "connection", "status": "connected", "session_id": session_id})

        while True:
            data = await websocket.receive_json()
            user_message = data.get("message", "")

            await log_event(session_id, "user_message", {"content": user_message})

            state = manager.get_session_state(session_id)
            messages = state.get("messages", [])
            messages.append({"role": "user", "content": user_message})

            try:
                response_text = await stream_llm_response(session_id, messages)
                await log_event(session_id, "ai_response", {"content": response_text})
                messages.append({"role": "assistant", "content": response_text})
                manager.update_session_state(session_id, {"messages": messages})
                await manager.send_message(session_id, {"type": "response", "content": response_text})
            except Exception as e:
                print(f"Error in LLM processing: {e}")
                await manager.send_message(session_id, {"type": "error", "content": str(e)})

    except WebSocketDisconnect:
        manager.disconnect(session_id)
        end_time = datetime.utcnow().isoformat()
        supabase.table("sessions").update({"end_time": end_time, "status": "completed"}).eq("session_id", session_id).execute()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
