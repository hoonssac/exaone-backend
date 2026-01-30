"""
에이전트 스키마
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class AgentAction(str, Enum):
    """에이전트 액션"""
    QUERY_ENTITIES = "query_entities"
    QUERY_PRODUCTION = "query_production"
    ASK_CLARIFICATION = "ask_clarification"
    RETURN_ANSWER = "return_answer"


class AgentResponse(BaseModel):
    """에이전트 응답"""
    action: AgentAction
    reasoning: str
    entities_to_query: Optional[List[str]] = None  # query_entities 시 (["machines", "materials"])
    message: Optional[str] = None  # ask_clarification 시
    sql: Optional[str] = None  # query_production 시
    answer: Optional[str] = None  # return_answer 시


class AgentContext(BaseModel):
    """에이전트 컨텍스트"""
    user_message: str
    extracted_info: Dict[str, Any] = {}
    available_entities: Dict[str, List[Dict[str, Any]]] = {}  # {"machines": [{id, name}, ...], "materials": [...]}
    previous_result: Optional[Any] = None
    iteration: int = 0
    max_iterations: int = 5
    history: List[Dict[str, Any]] = []
    conversation_history: str = ""  # 이전 대화 기록 (맥락 파악용)

    class Config:
        arbitrary_types_allowed = True
