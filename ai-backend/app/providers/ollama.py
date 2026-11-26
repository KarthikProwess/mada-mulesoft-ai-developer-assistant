
import json
import urllib.request
import urllib.error


class OllamaProvider:

    BASE_URL = "http://localhost:11434"

    # Faster responses for normal chat.
    MAX_GENERATION_TOKENS = 350
    TEMPERATURE = 0.2
    REQUEST_TIMEOUT = 180

    def __init__(self, base_url=None):

        self.base_url = (
            base_url or self.BASE_URL
        ).rstrip("/")

    def list_models(self):

        url = f"{self.base_url}/api/tags"

        try:

            request = urllib.request.Request(
                url,
                method="GET"
            )

            with urllib.request.urlopen(
                request,
                timeout=10
            ) as response:

                result = json.loads(
                    response.read().decode("utf-8")
                )

            models = result.get("models", [])

            return [
                model.get("name")
                for model in models
                if model.get("name")
            ]

        except Exception as error:

            raise RuntimeError(
                f"Could not retrieve Ollama models: {error}"
            )

    def generate_response(self, messages, model):

        url = f"{self.base_url}/api/chat"

        body = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": self.MAX_GENERATION_TOKENS,
                "temperature": self.TEMPERATURE
            }
        }

        data = json.dumps(body).encode("utf-8")

        request = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json"
            },
            method="POST"
        )

        try:

            with urllib.request.urlopen(
                request,
                timeout=self.REQUEST_TIMEOUT
            ) as response:

                result = json.loads(
                    response.read().decode("utf-8")
                )

            return result.get(
                "message", {}
            ).get("content", "")

        except urllib.error.HTTPError as error:

            details = error.read().decode(
                "utf-8",
                errors="replace"
            )

            raise RuntimeError(
                f"Ollama API error ({error.code}): {details}"
            )

        except Exception as error:

            raise RuntimeError(
                f"Ollama request failed: {error}"
            )

    def test_connection(self):

        try:

            self.list_models()

            return True

        except Exception:

            return False
