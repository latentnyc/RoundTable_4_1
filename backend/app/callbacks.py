from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult
from typing import Any, Dict, List, Optional, Union
import socketio
import logging

class SocketIOCallbackHandler(AsyncCallbackHandler):
    """Callback Handler that streams LLM events to a specific SocketIO client."""

    def __init__(self, sid: str, campaign_id: str, agent_name: str = "System"):
        # self.sio = sio # REMOVED to avoid pickle issues
        self.sid = sid # Target specific client or room? Start with client for direct debug.
        self.campaign_id = campaign_id
        self.agent_name = agent_name
        self.agent_name = agent_name
        self.last_model_name = "unknown"
        self.logger = logging.getLogger(__name__)
        self.logger.debug(f"Initialized SocketIOCallbackHandler for sid {sid} (Agent: {agent_name})")

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
        await sio.emit(event, data, room=self.campaign_id)

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
            self.logger.error(f"Error saving debug log to DB: {e}")

    async def on_chat_model_start(
        self, serialized: Dict[str, Any], messages: List[List[Any]], **kwargs: Any
    ) -> None:
        """Run when Chat Model starts running."""
        try:
            self.logger.debug(f"on_chat_model_start triggered for sid {self.sid}")

            # Capture model name from serialized config
            # serialized: {'id': ['langchain', 'chat_models', 'google_palm', 'ChatGooglePalm'], 'kwargs': {'model_name': 'models/chat-bison-001', ...}}
            self.last_model_name = (
                serialized.get('kwargs', {}).get('model_name') or
                serialized.get('kwargs', {}).get('model') or
                "unknown"
            )
            self.logger.debug(f"Captured model name: {self.last_model_name}")

            # messages is a list of lists of BaseMessage (usually just one list in standard invoke)
            # We want to log the ACTUAL messages sent.

            # Serialize messages for display
            self.logger.debug("Serializing messages...")
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

            self.logger.debug(f"Serialized {len(serialized_messages)} messages. Preparing to emit...")

            await self._emit('debug_log', {
                'type': 'llm_start',
                'content': f"Sending {len(serialized_messages)} messages to LLM...",
                'full_content': serialized_messages,
                'timestamp': 'Just now'
            })
            self.logger.debug("Emit complete.")

        except BaseException as e:
            # Catch EVERYTHING including CancelledError just to see
            import traceback
            self.logger.error(f"CRITICAL ERROR in on_chat_model_start callback: {e}")
            self.logger.error(traceback.format_exc())


    async def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        """Run when LLM starts running (Legacy / Non-Chat)."""
        try:
            self.logger.debug(f"on_llm_start triggered for sid {self.sid}")

            # Capture model name
            self.last_model_name = (
                serialized.get('kwargs', {}).get('model_name') or
                serialized.get('kwargs', {}).get('model') or
                "unknown"
            )
            self.logger.debug(f"Captured model name (LLM): {self.last_model_name}")

            await self._emit('debug_log', {
                'type': 'llm_start',
                'content': f"Generating response for: {prompts[0][:100]}...",
                'full_content': prompts,
                'timestamp': 'Just now'
            })
        except BaseException as e:
            self.logger.error(f"CRITICAL ERROR in on_llm_start callback: {e}")

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Run when LLM ends running."""
        try:
            self.logger.debug("on_llm_end triggered.")
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

            # Emit AI Stats
            await self._handle_token_usage(response)

            self.logger.debug("on_llm_end emit complete.")
        except BaseException as e:
            import traceback
            self.logger.error(f"CRITICAL ERROR in on_llm_end callback: {e}")
            self.logger.error(traceback.format_exc())

    async def on_chat_model_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Run when Chat Model ends running."""
        try:
            self.logger.debug("on_chat_model_end triggered.")
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
                'content': f"Chat Response: {text[:100]}...",
                'full_content': full_content,
                'timestamp': 'Just now'
            })

            # Emit AI Stats
            await self._handle_token_usage(response)

            self.logger.debug("on_chat_model_end emit complete.")
        except BaseException as e:
            import traceback
            self.logger.error(f"CRITICAL ERROR in on_chat_model_end callback: {e}")
            self.logger.error(traceback.format_exc())

    async def _handle_token_usage(self, response: LLMResult):
        usage = {}

        # Standard LangChain usage_metadata (Newer versions)
        # response.llm_output might be empty for some providers, but usage_metadata should be on the message.
        
        # 1. Try Global llm_output
        if response.llm_output:
            usage = response.llm_output.get('token_usage') or response.llm_output.get('usage_metadata') or {}
            self.logger.debug(f"DEBUG: Found usage in llm_output: {usage}")

        # 2. Try Generations (Specific to Chat Models)
        if not usage and response.generations:
            try:
                first_gen = response.generations[0][0]
                # Check message.usage_metadata (Standard)
                if hasattr(first_gen, 'message'):
                    usage = getattr(first_gen.message, 'usage_metadata', {}) or {}
                    self.logger.debug(f"DEBUG: Found usage in message.usage_metadata: {usage}")
                
                # Check generation_info (Google GenAI specific sometimes)
                if not usage and hasattr(first_gen, 'generation_info'):
                     usage = first_gen.generation_info.get('usage_metadata') or {}
                     self.logger.debug(f"DEBUG: Found usage in generation_info: {usage}")

            except (IndexError, AttributeError) as e:
                self.logger.debug(f"DEBUG: Error checking generations for usage: {e}")

        if not usage:
            self.logger.debug("DEBUG: _handle_token_usage found NO usage data in response.")
            # Verify what we DO have
            try:
                self.logger.debug(f"DEBUG: llm_output keys: {response.llm_output.keys() if response.llm_output else 'None'}")
                if response.generations:
                    gen0 = response.generations[0][0]
                    self.logger.debug(f"DEBUG: Gen0 type: {type(gen0)}")
                    if hasattr(gen0, 'message'):
                        self.logger.debug(f"DEBUG: Message metadata: {getattr(gen0.message, 'response_metadata', 'N/A')}")
            except Exception:
                pass
            return

        self.logger.debug(f"_handle_token_usage processing usage: {usage}")

        # Normalize keys
        input_tokens = (
            usage.get('input_tokens') or
            usage.get('prompt_token_count') or
            usage.get('prompt_tokens') or
            0
        )
        output_tokens = (
            usage.get('output_tokens') or
            usage.get('candidates_token_count') or
            usage.get('completion_tokens') or
            0
        )
        total_tokens = (
            usage.get('total_tokens') or
            usage.get('total_token_count') or
            (input_tokens + output_tokens)
        )

        if total_tokens > 0:
            # Update DB (Auto-commit)
            try:
                # Runtime import to avoid circular imports
                from db.session import AsyncSessionLocal
                from sqlalchemy import text

                async with AsyncSessionLocal() as db:
                    await db.execute(
                        text("""
                            UPDATE campaigns
                            SET total_input_tokens = COALESCE(total_input_tokens, 0) + :input,
                                total_output_tokens = COALESCE(total_output_tokens, 0) + :output,
                                query_count = COALESCE(query_count, 0) + 1
                            WHERE id = :cid
                        """),
                        {
                            "input": input_tokens,
                            "output": output_tokens,
                            "cid": self.campaign_id
                        }
                    )
                    await db.commit()

                    # Fetch new totals to emit accurate state
                    result = await db.execute(
                        text("SELECT total_input_tokens, total_output_tokens, query_count FROM campaigns WHERE id = :cid"),
                        {"cid": self.campaign_id}
                    )
                    row = result.mappings().fetchone()
                    if row:
                        current_total = (row['total_input_tokens'] or 0) + (row['total_output_tokens'] or 0)
                        current_query_count = row['query_count'] or 0

                        # Try to get model name from llm_output or generation_info
                        model_name = response.llm_output.get('model_name')
                        if not model_name and response.generations:
                            try:
                                model_name = response.generations[0][0].generation_info.get('model_name')
                            except (IndexError, AttributeError):
                                pass

                        # Fallback to captured model name from start event
                        model_name = model_name or self.last_model_name or 'unknown'

                        await self._emit('ai_stats', {
                            'type': 'update',
                            'input_tokens': row['total_input_tokens'] or 0,
                            'output_tokens': row['total_output_tokens'] or 0,
                            'total_tokens': current_total,
                            'query_count': current_query_count,
                            'model': model_name,
                            'agent_name': self.agent_name,
                            'last_request': {
                                'tokens': total_tokens,
                                'model': model_name,
                                'agent': self.agent_name
                            }
                        })
                        self.logger.debug(f"Emitted updated ai_stats: {current_total} total tokens")

            except Exception as db_err:
                self.logger.error(f"Error updating campaign stats: {db_err}")

    async def on_tool_start(
        self, serialized: Dict[str, Any], input_str: str, **kwargs: Any
    ) -> None:
        """Run when tool starts running."""
        try:
            self.logger.debug(f"on_tool_start triggered for {serialized.get('name')}")
            await self._emit('debug_log', {
                'type': 'tool_start',
                'content': f"Tool Call: {serialized.get('name')} input: {input_str}",
                'full_content': input_str,
                'timestamp': 'Just now'
            })
        except BaseException as e:
            self.logger.error(f"CRITICAL ERROR in on_tool_start callback: {e}")

    async def on_tool_end(self, output: str, **kwargs: Any) -> None:
        """Run when tool ends running."""
        try:
            self.logger.debug("on_tool_end triggered.")
            # Handle ToolMessage object if passed
            content = output
            if hasattr(output, 'content'):
                content = output.content

            await self._emit('debug_log', {
                'type': 'tool_end',
                'content': f"Tool Output: {str(content)[:100]}...",
                'full_content': str(content),
                'timestamp': 'Just now'
            })
        except BaseException as e:
             self.logger.error(f"CRITICAL ERROR in on_tool_end callback: {e}")
