"""llm_gateway — client IA commun, local d'abord, avec chaîne de secours et profils matériel."""

from llm_gateway.config import GatewaySettings
from llm_gateway.errors import LLMError, ProviderUnavailableError, StructuredOutputError
from llm_gateway.gateway import Gateway, get_gateway
from llm_gateway.profiles import HardwareInfo, Profile, detect_hardware, load_profile
from llm_gateway.providers.fake import FakeProvider
from llm_gateway.types import ChatResult, Role

__all__ = [
    "ChatResult",
    "FakeProvider",
    "Gateway",
    "GatewaySettings",
    "HardwareInfo",
    "LLMError",
    "Profile",
    "ProviderUnavailableError",
    "Role",
    "StructuredOutputError",
    "detect_hardware",
    "get_gateway",
    "load_profile",
]
