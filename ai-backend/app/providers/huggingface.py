
import json

from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


class HuggingFaceProvider:

    MODELS = [
        "deepseek-ai/DeepSeek-V3-0324",
        "meta-llama/Llama-3.1-8B-Instruct"
    ]

    API_URL = (
        "https://router.huggingface.co/v1/chat/completions"
    )

    def __init__(self, api_key=None):
        self.api_key = api_key

    def list_models(self):
        return self.MODELS

    def generate_response(self, messages, model):

        if not self.api_key:
            raise RuntimeError(
                "Hugging Face token is missing."
            )

        if model not in self.MODELS:
            raise RuntimeError(
                "Unsupported Hugging Face model."
            )

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": 2048,
            "temperature": 0.2
        }

        request = Request(
            self.API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + self.api_key,
                "Content-Type": "application/json"
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
                    "Hugging Face returned no response."
                )

            answer = (
                choices[0]
                .get("message", {})
                .get("content", "")
            )

            if isinstance(answer, list):
                answer = "\n".join(
                    item.get("text", "")
                    for item in answer
                    if isinstance(item, dict)
                )

            if not answer:
                raise RuntimeError(
                    "Hugging Face returned an empty response."
                )

            return answer

        except HTTPError as error:

            try:
                error_body = error.read().decode("utf-8")
                details = json.loads(error_body)

                message = (
                    details.get("error", {}).get("message")
                    or details.get("error")
                    or error_body
                )

            except Exception:
                message = "Unable to read API error details."

            raise RuntimeError(
                f"Hugging Face API error "
                f"({error.code}): {message}"
            ) from None

        except URLError as error:
            raise RuntimeError(
                "Could not connect to Hugging Face: "
                + str(error.reason)
            ) from None

        except TimeoutError:
            raise RuntimeError(
                "Hugging Face request timed out."
            ) from None
