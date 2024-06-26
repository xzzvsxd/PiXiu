import uuid
import g4f
from g4f import ChatCompletion

TEST_PROMPT = "Generate a sentence with 'ocean'"
EXPECTED_RESPONSE_CONTAINS = "ocean"


class Provider_Class:
    def __init__(self, name, models):
        """
        Initialize the provider with its name and models.
        """
        self.name = name
        self.models = models if isinstance(models, list) else [models]

    def __str__(self):
        return self.name


class ModelProviderManager:
    def __init__(self):
        """
        Initialize the manager that manages the working (active) providers for each model.
        """
        self._working_model_providers = {}

    def add_provider(self, model, provider_name):
        """
        Add a provider to the working provider list of the specified model.
        """
        if model not in self._working_model_providers:
            self._working_model_providers[model] = []
        self._working_model_providers[model].append(provider_name)

    def get_working_providers(self):
        """
        Return the currently active providers for each model.
        """
        return self._working_model_providers


def _fetch_providers_having_models():
    """
    Get providers that have models from g4f.Providers.
    """
    model_providers = []
    from g4f import Provider  # 确保可以导入 Provider

    for provider_name in Provider.ProviderUtils.__relevant_providers__:
        provider = getattr(g4f.Provider, provider_name)

        # 打印类的所有属性和值
        # print(f"\n{provider_name} attributes and values:")
        # for attr in dir(provider):
        #     if not attr.startswith("__") and not callable(getattr(provider, attr)):
        #         print(f"{attr}: {getattr(provider, attr)}")

        if _is_provider_applicable(provider):
            if hasattr(provider, 'models'):
                # print(provider)
                model_providers.append(Provider_Class(provider_name, provider.models))
            # else:
            #     print(f"Error: {provider_name} does not have a 'model' attribute.")

    return model_providers


def _is_provider_applicable(provider):
    """
    Check if the provider has a model and doesn't require authentication.
    """
    # if hasattr(provider, 'needs_auth'):
    #     print(f"Provider {provider} has a model, {provider.needs_auth}")

    return (
            # hasattr(provider, 'model') and
            # hasattr(provider, '_create_completion') and
            hasattr(provider, 'needs_auth') and
            not provider.needs_auth)


def _generate_test_messages():
    """
    Generate messages for testing.
    """
    return [{"role": "system", "content": "You are a trained AI assistant."},
            {"role": "user", "content": TEST_PROMPT}]


def _manage_chat_completion(manager, model_providers, test_messages):
    """
    Generate chat completion for each provider's models and handle positive and negative results.
    """
    for provider in model_providers:
        for model in provider.models:
            try:
                response = _generate_chat_response(
                    provider.name, model, test_messages)
                if EXPECTED_RESPONSE_CONTAINS in response.lower():
                    _print_success_response(provider, model)
                    manager.add_provider(model, provider.name)
                else:
                    raise Exception(f"Unexpected response: {response}")
            except Exception as error:
                _print_error_response(provider, model, error)


def _generate_chat_response(provider_name, model, test_messages):
    """
    Generate a chat response given a provider name, a model, and test messages.
    """
    return ChatCompletion.create(
        model=model,
        messages=test_messages,
        chatId=str(uuid.uuid4()),
        provider=getattr(g4f.Provider, provider_name),
        proxy='http://127.0.0.1:7890'
    )


def _print_success_response(provider, model):
    print(f"\u2705 [{provider}] - [{model}]: Success")


def _print_error_response(provider, model, error):
    print(f"\u26D4 [{provider}] - [{model}]: Error - {str(error)}")


def get_active_model_providers():
    """
    Get providers that are currently working (active).
    """
    model_providers = _fetch_providers_having_models()
    # print(f"model_providers: {model_providers}")

    test_messages = _generate_test_messages()
    # print(f"test_messages: {test_messages}")

    manager = ModelProviderManager()

    _manage_chat_completion(manager, model_providers, test_messages)
    # print(f"model_providers: {model_providers}")

    return manager.get_working_providers()
