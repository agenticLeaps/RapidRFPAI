"""
LangChain Conversation Memory Module

Uses ConversationSummaryBufferMemory for smart memory management:
- Keeps recent messages verbatim
- Auto-summarizes older messages when token limit exceeded
- Integrates with AWS Bedrock Claude for summarization
"""

import os
from typing import List, Dict, Optional
from langchain_aws import ChatBedrock
from langchain_classic.memory import ConversationSummaryBufferMemory
from langchain_core.messages import HumanMessage, AIMessage


class ConversationMemoryManager:
    """Manages conversation memory using LangChain with Bedrock Claude"""

    def __init__(self, max_token_limit: int = 2000):
        """
        Initialize memory manager with Bedrock Claude LLM.

        Args:
            max_token_limit: Max tokens before triggering summarization (default 2000)
        """
        try:
            # Initialize Bedrock Claude for summarization
            self.llm = ChatBedrock(
                model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
                region_name=os.getenv("AWS_REGION", "us-east-1"),
                model_kwargs={"temperature": 0.3, "max_tokens": 1000}
            )

            # Memory store: keeps recent messages, summarizes older ones
            self.memory = ConversationSummaryBufferMemory(
                llm=self.llm,
                max_token_limit=max_token_limit,
                return_messages=True,
                memory_key="chat_history",
                human_prefix="User",
                ai_prefix="Assistant"
            )

            self._initialized = True
            print(f"ConversationMemoryManager initialized with max_token_limit={max_token_limit}")

        except Exception as e:
            print(f"Failed to initialize ConversationMemoryManager: {e}")
            self._initialized = False
            self.memory = None
            self.llm = None

    @property
    def is_initialized(self) -> bool:
        """Check if memory manager is properly initialized"""
        return self._initialized

    def add_message(self, role: str, content: str):
        """
        Add a message to memory.

        Args:
            role: 'user' or 'assistant'
            content: Message content
        """
        if not self._initialized:
            return

        try:
            if role == "user":
                self.memory.chat_memory.add_user_message(content)
            else:
                self.memory.chat_memory.add_ai_message(content)
        except Exception as e:
            print(f"Error adding message to memory: {e}")

    def add_exchange(self, user_message: str, ai_message: str):
        """
        Add a complete exchange (user + AI messages).

        Args:
            user_message: User's message content
            ai_message: AI's response content
        """
        self.add_message("user", user_message)
        self.add_message("assistant", ai_message)

    def load_from_history(self, messages: List[Dict[str, str]]):
        """
        Load existing conversation history into memory.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
        """
        if not self._initialized:
            return

        try:
            self.memory.clear()
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if content:
                    self.add_message(role, content)

            print(f"Loaded {len(messages)} messages into memory")

        except Exception as e:
            print(f"Error loading history: {e}")

    def get_context(self) -> str:
        """
        Get formatted memory context for LLM.
        Returns summary + recent messages as formatted string.

        Returns:
            Formatted conversation context string
        """
        if not self._initialized:
            return ""

        try:
            memory_vars = self.memory.load_memory_variables({})
            chat_history = memory_vars.get("chat_history", [])

            # Format messages as string
            if isinstance(chat_history, list):
                formatted_lines = []
                for msg in chat_history:
                    if isinstance(msg, HumanMessage):
                        formatted_lines.append(f"User: {msg.content}")
                    elif isinstance(msg, AIMessage):
                        formatted_lines.append(f"Assistant: {msg.content}")
                    else:
                        formatted_lines.append(str(msg))
                return "\n".join(formatted_lines)
            else:
                return str(chat_history)

        except Exception as e:
            print(f"Error getting context: {e}")
            return ""

    def get_summary(self) -> str:
        """
        Get current conversation summary (if any).

        Returns:
            Summary string of older conversation parts
        """
        if not self._initialized:
            return ""

        try:
            return self.memory.moving_summary_buffer or ""
        except Exception as e:
            print(f"Error getting summary: {e}")
            return ""

    def get_message_count(self) -> int:
        """Get count of messages in memory"""
        if not self._initialized:
            return 0

        try:
            return len(self.memory.chat_memory.messages)
        except:
            return 0

    def clear(self):
        """Clear all memory"""
        if self._initialized and self.memory:
            try:
                self.memory.clear()
                print("Memory cleared")
            except Exception as e:
                print(f"Error clearing memory: {e}")


# Per-conversation memory cache
_memory_cache: Dict[str, ConversationMemoryManager] = {}


def get_memory_for_conversation(conversation_id: str, max_token_limit: int = 2000) -> ConversationMemoryManager:
    """
    Get or create memory manager for a conversation.

    Args:
        conversation_id: Unique conversation identifier
        max_token_limit: Max tokens before summarization

    Returns:
        ConversationMemoryManager instance for this conversation
    """
    if not conversation_id:
        # Return a new ephemeral memory manager if no ID provided
        return ConversationMemoryManager(max_token_limit)

    if conversation_id not in _memory_cache:
        _memory_cache[conversation_id] = ConversationMemoryManager(max_token_limit)
        print(f"Created new memory manager for conversation: {conversation_id}")

    return _memory_cache[conversation_id]


def clear_conversation_memory(conversation_id: str):
    """
    Clear and remove memory for a specific conversation.

    Args:
        conversation_id: Conversation ID to clear
    """
    if conversation_id in _memory_cache:
        _memory_cache[conversation_id].clear()
        del _memory_cache[conversation_id]
        print(f"Cleared memory for conversation: {conversation_id}")


def get_cache_stats() -> Dict:
    """Get statistics about the memory cache"""
    return {
        "total_conversations": len(_memory_cache),
        "conversations": {
            cid: {
                "message_count": mem.get_message_count(),
                "has_summary": bool(mem.get_summary())
            }
            for cid, mem in _memory_cache.items()
        }
    }
