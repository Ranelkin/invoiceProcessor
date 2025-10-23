import anthropic
import openai
import os
import json
from dotenv import load_dotenv
from xai_sdk import Client
from xai_sdk.chat import user, system


class ModelInterface:
    """Unified interface for different AI model providers"""
    
    def __init__(self, client, model_type: str, model_name: str):
        self.client = client
        self.api_key = os.environ.get("API_KEY")
        self.model_type = model_type
        self.model_name = model_name
    
    def query(self, prompt: str, system_prompt: str = None, **kwargs):
        """
        Query the model with a unified interface
        
        Args:
            prompt: The user's message/prompt
            system_prompt: Optional system prompt to guide the model's behavior
            **kwargs: Additional parameters specific to each provider
        
        Returns:
            str: The model's response
        """
        if self.model_type == "openai":
            return self._query_openai(prompt, system_prompt, **kwargs)
        elif self.model_type == "anthropic":
            return self._query_anthropic(prompt, system_prompt, **kwargs)
        elif self.model_type == "xAI":
            return self._query_xai(prompt, system_prompt, **kwargs)
    
    def _query_openai(self, prompt: str, system_prompt: str = None, **kwargs):
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            **kwargs
        )
        return response.choices[0].message.content
    
    def _query_anthropic(self, prompt: str, system_prompt: str = None, **kwargs):
        messages = [{"role": "user", "content": prompt}]
        
        # Anthropic uses system parameter separately
        params = {"model": self.model_name, "messages": messages, "max_tokens": 4096}
        if system_prompt:
            params["system"] = system_prompt
        params.update(kwargs)
        
        response = self.client.messages.create(**params)
        return response.content[0].text
    
    def _query_xai(self, prompt: str, system_prompt: str = None, **kwargs):
        messages = []
        if system_prompt:
            messages.append(system(system_prompt))
        messages.append(user(prompt))
        
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            **kwargs
        )
        return response.choices[0].message.content


def init_model() -> ModelInterface:
    """
    Initialize and return a model interface based on environment configuration
    
    Returns:
        ModelInterface: A unified interface that can be called with .query()
    """
    
    # Load supported models from vars.json
    with open("./vars.json", "r") as f:
        config = json.load(f)
    
    supported_models = config['supported_models']
    provider = os.environ.get("MODEL_PROVIDER")
    api_key = os.environ.get("API_KEY")
    # Get the specific model name (e.g., gpt-4, claude-3-opus-20240229, etc.)
    model_name = os.environ.get("MODEL_NAME")
    
    match provider:
        case "openai":
            client = openai.OpenAI(api_key=api_key)
            # Default model if not specified
            model_name = model_name or "gpt-4-turbo-preview"
            return ModelInterface(client, "openai", model_name)
        
        case "anthropic":
            client = anthropic.Anthropic(api_key=api_key)
            # Default model if not specified
            model_name = model_name or "claude-3-5-sonnet-20241022"
            return ModelInterface(client, "anthropic", model_name)
        
        case "xAI":
            client = Client(api_key=api_key)
            # Default model if not specified
            model_name = model_name or "grok-beta"
            return ModelInterface(client, "xAI", model_name)
        
        case _:
            raise ValueError(
                f"Non supported provider selected: {provider}. "
                f"Select one of the following: {supported_models}"
            )

load_dotenv()
model = init_model()

# Example usage:
if __name__ == "__main__":
    # Initialize the model
    load_dotenv()
    model = init_model()
    
    # Simple query
    response = model.query("What is the capital of France?")
    print(response)
    
    # Query with system prompt
    response = model.query(
        prompt="Explain quantum computing in simple terms",
        system_prompt="You are a helpful teacher who explains complex topics simply"
    )
    print(response)
    
    # Query with additional parameters (e.g., temperature)
    response = model.query(
        prompt="Write a creative story about a robot",
        temperature=0.9
    )
    print(response)