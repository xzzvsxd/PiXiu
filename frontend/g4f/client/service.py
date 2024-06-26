from __future__ import annotations

from typing import Union

from .. import debug, version
from ..errors import ProviderNotFoundError, ModelNotFoundError, ProviderNotWorkingError, StreamNotSupportedError
from ..models import Model, ModelUtils
from ..Provider import ProviderUtils
from ..providers.types import BaseRetryProvider, ProviderType
from ..providers.retry_provider import IterProvider

def convert_to_provider(provider: str) -> ProviderType:
    if " " in provider:
        provider_list = [ProviderUtils.convert[p] for p in provider.split() if p in ProviderUtils.convert]
        if not provider_list:
            raise ProviderNotFoundError(f'Providers not found: {provider}')
        provider = IterProvider(provider_list)
    elif provider in ProviderUtils.convert:
        provider = ProviderUtils.convert[provider]
    elif provider:
        raise ProviderNotFoundError(f'Provider not found: {provider}')
    return provider

def get_model_and_provider(model    : Union[Model, str], 
                           provider : Union[ProviderType, str, None], 
                           stream   : bool,
                           ignored  : list[str] = None,
                           ignore_working: bool = False,
                           ignore_stream: bool = False) -> tuple[str, ProviderType]:
    """
    Retrieves the model and provider based on input parameters.

    Args:
        model (Union[Model, str]): The model to use, either as an object or a string identifier.
        provider (Union[ProviderType, str, None]): The provider to use, either as an object, a string identifier, or None.
        stream (bool): Indicates if the operation should be performed as a stream.
        ignored (list[str], optional): List of provider names to be ignored.
        ignore_working (bool, optional): If True, ignores the working status of the provider.
        ignore_stream (bool, optional): If True, ignores the streaming capability of the provider.

    Returns:
        tuple[str, ProviderType]: A tuple containing the model name and the provider type.

    Raises:
        ProviderNotFoundError: If the provider is not found.
        ModelNotFoundError: If the model is not found.
        ProviderNotWorkingError: If the provider is not working.
        StreamNotSupportedError: If streaming is not supported by the provider.
    """
    if debug.version_check:
        debug.version_check = False
        version.utils.check_version()

    if isinstance(provider, str):
        provider = convert_to_provider(provider)

    if isinstance(model, str):
        
        if model in ModelUtils.convert:
            model = ModelUtils.convert[model]
    
    if not provider:
        if isinstance(model, str):
            raise ModelNotFoundError(f'Model not found: {model}')
        provider = model.best_provider

    if not provider:
        raise ProviderNotFoundError(f'No provider found for model: {model}')

    if isinstance(model, Model):
        model = model.name

    if not ignore_working and not provider.working:
        raise ProviderNotWorkingError(f'{provider.__name__} is not working')

    if not ignore_working and isinstance(provider, BaseRetryProvider):
        provider.providers = [p for p in provider.providers if p.working]

    if ignored and isinstance(provider, BaseRetryProvider):
        provider.providers = [p for p in provider.providers if p.__name__ not in ignored]

    if not ignore_stream and not provider.supports_stream and stream:
        raise StreamNotSupportedError(f'{provider.__name__} does not support "stream" argument')

    if debug.logging:
        if model:
            print(f'Using {provider.__name__} provider and {model} model')
        else:
            print(f'Using {provider.__name__} provider')

    debug.last_provider = provider
    debug.last_model = model

    return model, provider

def get_last_provider(as_dict: bool = False) -> Union[ProviderType, dict[str, str]]:
    """
    Retrieves the last used provider.

    Args:
        as_dict (bool, optional): If True, returns the provider information as a dictionary.

    Returns:
        Union[ProviderType, dict[str, str]]: The last used provider, either as an object or a dictionary.
    """
    last = debug.last_provider
    if isinstance(last, BaseRetryProvider):
        last = last.last_provider
    if last and as_dict:
        return {
            "name": last.__name__,
            "url": last.url,
            "model": debug.last_model,
            "label": last.label if hasattr(last, "label") else None
        }
    return last