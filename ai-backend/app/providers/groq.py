import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


class GroqProvider:

    MODELS = [
        "openai/gpt-oss-20b"
    ]

    API_URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key=None):
        self.api_key = api_key

    def list_models(self):
        return self.MODELS

    def test_connection(self):
        if not self.api_key:
            raise RuntimeError("Groq API key is missing.")

        return True

    def generate_response(self, messages, model):

        if not self.api_key:
            raise RuntimeError("Groq API key is missing.")

        if model not in self.MODELS:
            raise RuntimeError("Unsupported Groq model: " + model)

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 700
        }

        request = Request(
            self.API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + self.api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "MADA-AI-Assistant/0.1"
            },
            method="POST"
        )

        try:
            with urlopen(request, timeout=120) as response:
                result = json.loads(
                    response.read().decode("utf-8")
                )

            choices = result.get("choices", [])

            if not choices:
                raise RuntimeError(
                    "Groq returned no response: " + str(result)
                )

            answer = choices[0].get("message", {}).get("content", "")

            if not answer:
                raise RuntimeError("Groq returned an empty response.")

            return answer

        except HTTPError as error:

            try:
                error_body = error.read().decode(
                    "utf-8",
                    errors="replace"
                )

                try:
                    details = json.loads(error_body)
                    error_value = details.get("error", details)

                    if isinstance(error_value, dict):
                        message = error_value.get(
                            "message",
                            str(error_value)
                        )
                    else:
                        message = str(error_value)

                except json.JSONDecodeError:
                    message = error_body or "Empty error response."

            except Exception:
                message = "Could not read the API error response."

            raise RuntimeError(
                f"Groq API error ({error.code}): {message[:1500]}"
            ) from None

        except URLError as error:
            raise RuntimeError(
                "Could not connect to Groq: " + str(error.reason)
            ) from None

        except TimeoutError:
            raise RuntimeError(
                "Groq request timed out."
            ) from None