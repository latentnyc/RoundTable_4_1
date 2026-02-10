from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult
from typing import Any, Dict, List, Optional, Union
import socketio

class SocketIOCallbackHandler(AsyncCallbackHandler):
    """Callback Handler that streams LLM events to a specific SocketIO client."""

    def __init__(self, sid: str, campaign_id: str, agent_name: str = "System"):
        # self.sio = sio # REMOVED to avoid pickle issues
        self.sid = sid # Target specific client or room? Start with client for direct debug.
        self.campaign_id = campaign_id
        self.agent_name = agent_name
        print(f"DEBUG: Initialized SocketIOCallbackHandler for sid {sid} (Agent: {agent_name})", flush=True)

    async def _emit(self, event: str, data: dict):
        # Runtime import to avoid circular imports
        from app.socket_manager import sio
        from db.session import AsyncSessionLocal
        from sqlalchemy import text
        from uuid import uuid4
        import json
        
        # Inject agent name
        data['agent_name'] = self.agent_name
        
        # Emit to frontend first for speed
        await sio.emit(event, data, room=self.sid)
        
        # Save to DB
        try:
            async with AsyncSessionLocal() as db:
                log_id = str(uuid4())
                full_content_str = json.dumps(data.get('full_content', ''))
                
                # Prepend agent name to content for visibility in simple logs
                db_content = f"[{self.agent_name}] {data.get('content', '')}"
                
                await db.execute(
                    text("""INSERT INTO debug_logs (id, campaign_id, type, content, full_content) 
                       VALUES (:id, :campaign_id, :type, :content, :full_content)"""),
                    {
                        "id": log_id, 
                        "campaign_id": self.campaign_id, 
                        "type": data.get('type', 'unknown'), 
                        "content": db_content, 
                        "full_content": full_content_str
                    }
                )
                await db.commit()
        except Exception as e:
            print(f"Error saving debug log to DB: {e}")

    async def on_chat_model_start(
        self, serialized: Dict[str, Any], messages: List[List[Any]], **kwargs: Any
    ) -> None:
        """Run when Chat Model starts running."""
        try:
            print(f"DEBUG: on_chat_model_start triggered for sid {self.sid}", flush=True)
            # messages is a list of lists of BaseMessage (usually just one list in standard invoke)
            # We want to log the ACTUAL messages sent.
            
            # Serialize messages for display
            print("DEBUG: Serializing messages...", flush=True)
            serialized_messages = []
            for sublist in messages:
                for msg in sublist:
                    # msg.content can be complex (list of dicts) for multimodal 
                    # Use str() or just keep it raw if JSON serializable?
                    # LangChain messages usually have .content as str or list.
                    content = msg.content
                    # If it's a list (e.g. image blocks), it might fail simple JSON dump if not careful.
                    # But Python socketio handles basic types. Pydantic models might be tricky.
                    # Let's try to keep it simple.
                    
                    serialized_messages.append({
                        "type": getattr(msg, 'type', 'unknown'),
                        "content": content
                    })
            
            print(f"DEBUG: Serialized {len(serialized_messages)} messages. Preparing to emit...", flush=True)
            
            await self._emit('debug_log', {
                'type': 'llm_start',
                'content': f"Sending {len(serialized_messages)} messages to LLM...",
                'full_content': serialized_messages,
                'timestamp': 'Just now'
            })
            print("DEBUG: Emit complete.", flush=True)

        except BaseException as e:
            # Catch EVERYTHING including CancelledError just to see
            import traceback
            print(f"CRITICAL ERROR in on_chat_model_start callback: {e}", flush=True)
            traceback.print_exc()


    async def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        """Run when LLM starts running (Legacy / Non-Chat)."""
        try:
            print(f"DEBUG: on_llm_start triggered for sid {self.sid}", flush=True)
            await self._emit('debug_log', {
                'type': 'llm_start',
                'content': f"Generating response for: {prompts[0][:100]}...",
                'full_content': prompts,
                'timestamp': 'Just now'
            })
        except BaseException as e:
            print(f"CRITICAL ERROR in on_llm_start callback: {e}", flush=True)

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Run when LLM ends running."""
        try:
            print("DEBUG: on_llm_end triggered.", flush=True)
            # Check if it's a chat generation or regular generation
            text = ""
            if response.generations:
                # Flatten generations
                for gen_list in response.generations:
                    for gen in gen_list:
                        if hasattr(gen, 'message'):
                            text += f"[{gen.message.type}]: {gen.message.content}\n"
                        else:
                            text += gen.text
            
            # Safe serialization for full content
            try:
                full_content = response.dict() if hasattr(response, 'dict') else str(response)
            except Exception:
                full_content = str(response)

            await self._emit('debug_log', {
                'type': 'llm_end',
                'content': f"Response: {text[:100]}...",
                'full_content': full_content,
                'timestamp': 'Just now'
            })
            print("DEBUG: on_llm_end emit complete.", flush=True)
        except BaseException as e:
            import traceback
            print(f"CRITICAL ERROR in on_llm_end callback: {e}", flush=True)
            traceback.print_exc()

    async def on_tool_start(
        self, serialized: Dict[str, Any], input_str: str, **kwargs: Any
    ) -> None:
        """Run when tool starts running."""
        try:
            print(f"DEBUG: on_tool_start triggered for {serialized.get('name')}", flush=True)
            await self._emit('debug_log', {
                'type': 'tool_start',
                'content': f"Tool Call: {serialized.get('name')} input: {input_str}",
                'full_content': input_str,
                'timestamp': 'Just now'
            })
        except BaseException as e:
            print(f"CRITICAL ERROR in on_tool_start callback: {e}", flush=True)

    async def on_tool_end(self, output: str, **kwargs: Any) -> None:
        """Run when tool ends running."""
        try:
            print("DEBUG: on_tool_end triggered.", flush=True)
            await self._emit('debug_log', {
                'type': 'tool_end',
                'content': f"Tool Output: {output[:100]}...",
                'full_content': output,
                'timestamp': 'Just now'
            })
        except BaseException as e:
             print(f"CRITICAL ERROR in on_tool_end callback: {e}", flush=True)
