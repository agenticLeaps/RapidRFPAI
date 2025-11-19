#!/usr/bin/env python3
"""
LLM integration for ChatGPT (OpenAI) model
"""
import os
import requests
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

class ChatGPTLLMClient:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        
        self.base_url = "https://api.openai.com/v1"
        self.model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    
    def generate_answer(
        self, 
        query: str, 
        context: str = "", 
        max_tokens: int = 1024,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Generate answer using ChatGPT with optional context (RAG)
        
        Args:
            query: User question
            context: Retrieved context from documents
            max_tokens: Maximum response tokens
            temperature: Sampling temperature
            
        Returns:
            Dictionary with answer and metadata
        """
        print(f"🤖 Generating answer for: '{query[:100]}...'")
        print(f"📝 Context length: {len(context)} chars")
        
        try:
            # Prepare messages for ChatGPT
            messages = []
            
            if context:
                # Fetch prompt from API with fallback
                try:
                    import requests
                    import os
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

⸻

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

⸻

WHEN INFORMATION IS MISSING

If the relevant text does not contain enough information to answer the question, respond with:

"I'm unable to answer this from the provided company knowledge. Please provide additional context or keywords so I can assist further."

⸻

Context:
{context}"""
                
                messages.append({"role": "system", "content": system_message})
            else:
                # Simple mode without context
                messages.append({"role": "system", "content": "You are the AI assistant inside RapidRFP, an application that helps users provide accurate information about their products and services. Provide clear, concise, and professional responses."})
            
            messages.append({"role": "user", "content": query})
            
            # Call OpenAI API
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature
                },
                timeout=60
            )
            
            print(f"📊 OpenAI API Response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                answer = result["choices"][0]["message"]["content"]
                
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
                    },
                    "usage": result.get("usage", {})
                }
            else:
                error_msg = f"OpenAI API error: {response.status_code}"
                try:
                    error_detail = response.json().get("error", {}).get("message", response.text)
                    error_msg += f" - {error_detail}"
                except:
                    error_msg += f" - {response.text}"
                
                print(f"❌ {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "query": query
                }
                
        except requests.exceptions.RequestException as e:
            error_msg = f"OpenAI API request failed: {str(e)}"
            print(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "query": query
            }
        except Exception as e:
            error_msg = f"ChatGPT generation error: {str(e)}"
            print(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "query": query
            }
    
    def simple_generate(
        self, 
        prompt: str, 
        max_tokens: int = 512,
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
        print(f"🔤 Simple generation for: '{prompt[:100]}...'")
        
        try:
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ]
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature
                },
                timeout=60
            )
            
            print(f"📊 OpenAI API Response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                response_text = result["choices"][0]["message"]["content"]
                
                print(f"✅ Generated response: {len(response_text)} chars")
                
                return {
                    "success": True,
                    "response": response_text,
                    "prompt": prompt,
                    "model": self.model,
                    "parameters": {
                        "max_tokens": max_tokens,
                        "temperature": temperature
                    },
                    "usage": result.get("usage", {})
                }
            else:
                error_msg = f"OpenAI API error: {response.status_code}"
                try:
                    error_detail = response.json().get("error", {}).get("message", response.text)
                    error_msg += f" - {error_detail}"
                except:
                    error_msg += f" - {response.text}"
                
                print(f"❌ {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "prompt": prompt
                }
                
        except Exception as e:
            error_msg = f"ChatGPT generation error: {str(e)}"
            print(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "prompt": prompt
            }
    
    def health_check(self) -> Dict[str, Any]:
        """Check if OpenAI API is accessible"""
        try:
            response = requests.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10
            )
            if response.status_code == 200:
                return {
                    "healthy": True,
                    "endpoint": self.base_url,
                    "model": self.model,
                    "status": "OpenAI API accessible"
                }
            else:
                return {
                    "healthy": False,
                    "endpoint": self.base_url,
                    "error": f"Status {response.status_code}"
                }
        except Exception as e:
            return {
                "healthy": False,
                "endpoint": self.base_url,
                "error": str(e)
            }

# Convenience functions
def generate_rag_answer(query: str, context: str = "", **kwargs) -> Dict[str, Any]:
    """Generate RAG answer using ChatGPT"""
    client = ChatGPTLLMClient()
    return client.generate_answer(query, context, **kwargs)

def generate_simple_response(prompt: str, **kwargs) -> Dict[str, Any]:
    """Generate simple response using ChatGPT"""
    client = ChatGPTLLMClient()
    return client.simple_generate(prompt, **kwargs)