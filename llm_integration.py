#!/usr/bin/env python3
"""
LLM integration for AWS Bedrock Claude
Replaces OpenAI ChatGPT with Bedrock Claude for all LLM operations
"""
import os
import requests
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

load_dotenv()

# Import Bedrock client
try:
    from bedrock_client import claude, BEDROCK_AVAILABLE
except ImportError:
    BEDROCK_AVAILABLE = False
    claude = None
    print("⚠️ Bedrock client not available for LLM integration")


class BedrockLLMClient:
    """Bedrock Claude LLM client - replaces ChatGPTLLMClient"""

    def __init__(self):
        if not BEDROCK_AVAILABLE or not claude:
            raise RuntimeError("Bedrock client not available. Check AWS credentials.")
        self.model = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")

    def _parse_conversation_history(self, conversation_history: str) -> list:
        """
        Parse conversation history string into message format

        Expected formats:
        1. "user: message\nassistant: response\nuser: next message\n..."
        2. "User: message\nAssistant: response\n..."
        3. JSON string: '[{"role": "user", "content": "..."}, ...]'

        Returns:
            List of message dictionaries with 'role' and 'content' keys
        """
        messages = []

        if not conversation_history or not conversation_history.strip():
            return messages

        # Try to parse as JSON first (most structured format)
        try:
            import json
            parsed = json.loads(conversation_history)
            if isinstance(parsed, list):
                for msg in parsed:
                    if isinstance(msg, dict) and "role" in msg and "content" in msg:
                        if msg["role"] in ["user", "assistant"]:
                            messages.append({"role": msg["role"], "content": msg["content"]})
                return messages
        except (json.JSONDecodeError, ValueError):
            pass

        # Parse as text format: "user: ...\nassistant: ...\n"
        lines = conversation_history.strip().split('\n')
        current_role = None
        current_content = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if line starts with a role indicator
            lower_line = line.lower()
            if lower_line.startswith('user:') or lower_line.startswith('user :'):
                # Save previous message if exists
                if current_role and current_content:
                    messages.append({
                        "role": current_role,
                        "content": '\n'.join(current_content).strip()
                    })
                current_role = "user"
                current_content = [line.split(':', 1)[1].strip() if ':' in line else '']
            elif lower_line.startswith('assistant:') or lower_line.startswith('assistant :'):
                # Save previous message if exists
                if current_role and current_content:
                    messages.append({
                        "role": current_role,
                        "content": '\n'.join(current_content).strip()
                    })
                current_role = "assistant"
                current_content = [line.split(':', 1)[1].strip() if ':' in line else '']
            else:
                # Continuation of current message
                if current_role:
                    current_content.append(line)

        # Don't forget the last message
        if current_role and current_content:
            messages.append({
                "role": current_role,
                "content": '\n'.join(current_content).strip()
            })

        return messages

    def generate_answer(
        self,
        query: str,
        context: str = "",
        conversation_history: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Generate answer using Bedrock Claude with optional context (RAG)

        Args:
            query: User question
            context: Retrieved context from documents
            conversation_history: Previous conversation in format "user: ...\nassistant: ...\n"
            max_tokens: Maximum response tokens
            temperature: Sampling temperature

        Returns:
            Dictionary with answer and metadata
        """
        print(f"🤖 Generating answer with Bedrock Claude for: '{query[:100]}...'")
        print(f"📝 Context length: {len(context)} chars")
        print(f"💬 Conversation history length: {len(conversation_history)} chars")

        try:
            # Build the system prompt
            if context:
                # Fetch prompt from API with fallback
                try:
                    backend_api_url = os.environ.get("BACKEND_API_URL", "http://localhost:8083")
                    response = requests.get(f"{backend_api_url}/api/prompts/chat", timeout=5)
                    if response.status_code == 200:
                        prompt_data = response.json()
                        if prompt_data.get("success") and prompt_data.get("data", {}).get("prompt"):
                            # Use prompt from API and format with context
                            prompt_template = prompt_data["data"]["prompt"]
                            system_message = prompt_template.format(context=context)
                            print("✅ Using prompt from API")
                        else:
                            raise Exception("Invalid API response format")
                    else:
                        raise Exception(f"API returned status {response.status_code}")
                except Exception as e:
                    print(f"⚠️ Failed to fetch prompt from API: {e}, using fallback")
                    # Fallback prompt
                    system_message = f"""You are the AI assistant inside RapidRFP, an application that helps users provide accurate information about their products and services.

Your job is to produce a clear, concise, professional, and compliant response based ONLY on the relevant text provided for this question.

You must follow all rules exactly.

CORE RULES
    •    Use only the provided relevant text as your source of truth.
If the text contradicts general knowledge, the text wins.
    •    Do NOT invent or assume any facts that are not present in the provided text or in the context provided by the user.
    •    You may use universally accepted common knowledge
(e.g., dates, countries, broad definitions like "cloud computing"),
but you may NOT add any company-specific, technical, or contextual information not found in the text.
    •    Never fill information gaps with outside knowledge.
Only clarify using the text + universal common knowledge.
    •    Keep responses concise, direct, and proposal-ready.
    •    Remove any irrelevant information, disclaimers, noise, or markup.
    •    Do not include line numbers, artifacts, or references to the text itself.
    •    Do not restate or summarize the entire text—only extract what is required to answer the question.
    •    If there are conflicting statements in the text, choose the strictest and safest interpretation.

WHEN INFORMATION IS MISSING

If the relevant text does not contain enough information to answer the question, respond with:

"I'm unable to answer this from the provided company knowledge. Please provide additional context or keywords so I can assist further."

Context:
{context}"""
            else:
                # Simple mode without context
                system_message = "You are the AI assistant inside RapidRFP, an application that helps users provide accurate information about their products and services. Provide clear, concise, and professional responses."

            # Build the prompt with conversation history
            full_prompt = ""
            if conversation_history:
                history_messages = self._parse_conversation_history(conversation_history)
                for msg in history_messages:
                    role_label = "Human" if msg["role"] == "user" else "Assistant"
                    full_prompt += f"{role_label}: {msg['content']}\n\n"
                print(f"📝 Added {len(history_messages)} messages from conversation history")

            # Add current query
            full_prompt += f"Human: {query}\n\nAssistant:"

            # Call Bedrock Claude
            result = claude.call_claude(
                prompt=full_prompt,
                system=system_message,
                max_tokens=max_tokens,
                temperature=temperature,
                response_format="text"
            )

            answer = result.get("text", "").strip()
            print(f"✅ Generated answer: {len(answer)} chars")
            print(f"📋 Answer preview: {answer[:150]}...")

            return {
                "success": True,
                "answer": answer,
                "query": query,
                "context_used": len(context) > 0,
                "context_length": len(context),
                "model": self.model,
                "parameters": {
                    "max_tokens": max_tokens,
                    "temperature": temperature
                }
            }

        except Exception as e:
            error_msg = f"Bedrock Claude generation error: {str(e)}"
            print(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "query": query
            }

    def simple_generate(
        self,
        prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Simple text generation without RAG context

        Args:
            prompt: Text prompt
            max_tokens: Maximum response tokens
            temperature: Sampling temperature

        Returns:
            Dictionary with response and metadata
        """
        print(f"🔤 Simple generation with Bedrock Claude for: '{prompt[:100]}...'")

        try:
            result = claude.call_claude(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                response_format="text"
            )

            response_text = result.get("text", "").strip()
            print(f"✅ Generated response: {len(response_text)} chars")

            return {
                "success": True,
                "response": response_text,
                "prompt": prompt,
                "model": self.model,
                "parameters": {
                    "max_tokens": max_tokens,
                    "temperature": temperature
                }
            }

        except Exception as e:
            error_msg = f"Bedrock Claude generation error: {str(e)}"
            print(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "prompt": prompt
            }

    def health_check(self) -> Dict[str, Any]:
        """Check if Bedrock Claude is accessible"""
        try:
            if not BEDROCK_AVAILABLE or not claude:
                return {
                    "healthy": False,
                    "endpoint": "AWS Bedrock",
                    "error": "Bedrock client not available"
                }

            # Try a simple generation to verify connectivity
            result = claude.call_claude(
                prompt="Say 'ok' if you can hear me.",
                max_tokens=10,
                temperature=0,
                response_format="text"
            )

            if result.get("text"):
                return {
                    "healthy": True,
                    "endpoint": "AWS Bedrock",
                    "model": self.model,
                    "status": "Bedrock Claude accessible"
                }
            else:
                return {
                    "healthy": False,
                    "endpoint": "AWS Bedrock",
                    "error": "Empty response from Claude"
                }

        except Exception as e:
            return {
                "healthy": False,
                "endpoint": "AWS Bedrock",
                "error": str(e)
            }


# Backwards compatibility alias
ChatGPTLLMClient = BedrockLLMClient


# Convenience functions
def generate_rag_answer(query: str, context: str = "", conversation_history: str = "", **kwargs) -> Dict[str, Any]:
    """Generate RAG answer using Bedrock Claude"""
    client = BedrockLLMClient()
    return client.generate_answer(query, context, conversation_history, **kwargs)


def generate_simple_response(prompt: str, **kwargs) -> Dict[str, Any]:
    """Generate simple response using Bedrock Claude"""
    client = BedrockLLMClient()
    return client.simple_generate(prompt, **kwargs)
