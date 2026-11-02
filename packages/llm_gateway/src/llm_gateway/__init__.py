"""llm_gateway — client IA commun, local d'abord, avec chaîne de secours et profils matériel."""

from llm_gateway.config import GatewaySettings
from llm_gateway.errors import LLMError, ProviderUnavailableError, StructuredOutputError
from llm_gateway.gateway import Gateway, get_gateway
from llm_gateway.profiles import HardwareInfo, Profile, detect_hardware, load_profile
from llm_gateway.providers.fake import FakeProvider
from llm_gateway.types import ChatResult, Role
from llm_gateway.vectorstore import (
    MemoryVectorStore,
    PgVectorStore,
    Record,
    VectorStore,
    index_records,
    open_vector_store,
)

__all__ = [
    "ChatResult",
    "FakeProvider",
    "Gateway",
    "GatewaySettings",
    "HardwareInfo",
    "LLMError",
    "MemoryVectorStore",
    "PgVectorStore",
    "Profile",
    "ProviderUnavailableError",
    "Record",
    "Role",
    "StructuredOutputError",
    "VectorStore",
    "detect_hardware",
    "get_gateway",
    "index_records",
    "load_profile",
    "open_vector_store",
]
