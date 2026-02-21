from .openai_adapter import OpenAIAdapter


def build_ai_service(config):
    return OpenAIAdapter(model=config.OPENAI_MODEL, api_key=config.OPENAI_API_KEY)
