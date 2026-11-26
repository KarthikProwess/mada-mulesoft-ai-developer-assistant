
# ============================================================
# MADA AI PROVIDER REGISTRY
# ============================================================

PROVIDERS = {
    "openai": {
        "name": "OpenAI",
        "adapter": None,
        "configured": False
    },

    "gemini": {
        "name": "Google Gemini",
        "adapter": None,
        "configured": False
    },

    "huggingface": {
        "name": "Hugging Face",
        "adapter": None,
        "configured": False
    },

    "groq": {
        "name": "Groq",
        "adapter": None,
        "configured": False
    },

    "anthropic": {
        "name": "Anthropic Claude",
        "adapter": None,
        "configured": False
    },

    "deepseek": {
        "name": "DeepSeek",
        "adapter": None,
        "configured": False
    },

    "ollama": {
        "name": "Ollama (Local)",
        "adapter": None,
        "configured": False
    }
}


# ============================================================
# LIST ALL PROVIDERS
# ============================================================

def list_providers():
    """
    Return all registered AI providers and their status.
    """

    result = []

    for provider_id, details in PROVIDERS.items():

        result.append({
            "id": provider_id,
            "name": details["name"],
            "configured": details["configured"]
        })

    return result


# ============================================================
# UPDATE PROVIDER CONFIGURATION STATUS
# ============================================================

def set_provider_configured(provider_id):
    """
    Mark the selected provider as configured.

    Only one provider is marked active at a time.
    """

    if provider_id not in PROVIDERS:
        raise ValueError(
            f"Unsupported provider: {provider_id}"
        )

    for current_provider in PROVIDERS:
        PROVIDERS[current_provider]["configured"] = False

    PROVIDERS[provider_id]["configured"] = True


# ============================================================
# RESET PROVIDER CONFIGURATION STATUS
# ============================================================

def reset_provider_configuration():
    """
    Reset the configured status of all providers.
    """

    for provider_id in PROVIDERS:
        PROVIDERS[provider_id]["configured"] = False


# ============================================================
# CHECK PROVIDER CONFIGURATION
# ============================================================

def is_provider_configured(provider_id):
    """
    Check whether a provider is currently configured.
    """

    if provider_id not in PROVIDERS:
        return False

    return PROVIDERS[provider_id]["configured"]
