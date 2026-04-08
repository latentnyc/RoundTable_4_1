import logging
from typing import TypedDict, List, Annotated
import operator
from langchain_core.messages import BaseMessage

logger = logging.getLogger(__name__)

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    campaign_id: str
    sender_name: str
    mode: str
    api_key: str
    model_name: str

def should_continue(state: AgentState):
    from langgraph.graph import END
    messages = state["messages"]
    last_message = messages[-1]
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "tools"
    return END
