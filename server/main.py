# main.py
from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import List, Optional
import requests
import json

from agent import chat_with_agent

app = FastAPI(title="LLM Task Manager")

# --- Pydantic input model ---
class ChatRequest(BaseModel):
    message: str


# --- LLM response parser ---
def parse_llm_response(content: str) -> dict:
    try:
        start = content.find("{")
        end = content.rfind("}")
        json_str = content[start:end + 1]
        return json.loads(json_str)
    except:
        return {
            "intent": "unknown",
            "task_description": None,
            "response_message": "❌ Could not parse LLM response."
        }


@app.post("/chat")
def chat(req: ChatRequest):
    user_input = req.message
    response = chat_with_agent(user_input)
    return response
