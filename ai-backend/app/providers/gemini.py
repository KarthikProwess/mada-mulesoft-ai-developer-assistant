
import json
import time

from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


class GeminiProvider:

    MODELS = [
        "gemini-2.5-flash",
        "gemini-3.8-flash"
    ]

    API_URL = (
        "https://generativelanguage.googleapis.com/v1beta/"
        "models/{model}:generateContent"
    )

    def __init__(self, api_key=None):
        self.api_key = api_key

    def list_models(self):
        return self.MODELS

    def test_connection(self):
        if not self.api_key:
            raise RuntimeError(
                "Gemini API key is missing."
            )

        return True

    def generate_response(self, messages, model):

        if not self.api_key:
            raise RuntimeError(
                "Gemini API key is not configured. "
                "Enter your API key in the MADA UI."
            )

        if model not in self.MODELS:
            raise RuntimeError(
                "Unsupported Gemini model: " + str(model)
            )

        contents = []

        for item in messages:

            role = item.get("role", "user")
            content = item.get("content", "")

            gemini_role = (
                "model" if role == "assistant" else "user"
            )

            contents.append({
                "role": gemini_role,
                "parts": [
                    {
                        "text": str(content)
                    }
                ]
            })

        if not contents:
            raise RuntimeError(
                "No messages were provided to Gemini."
            )

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 2048
            }
        }

        url = self.API_URL.format(model=model)

        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key
            },
            method="POST"
        )

        max_attempts = 3

        for attempt in range(max_attempts):

            try:

                print(
                    f"[MADA] Gemini request attempt "
                    f"{attempt + 1}/{max_attempts}"
                )

                with urlopen(request, timeout=180) as response:

                    result = json.loads(
                        response.read().decode("utf-8")
                    )

                candidates = result.get("candidates", [])

                if not candidates:
                    raise RuntimeError(
                        "Gemini returned no response candidates."
                    )

                parts = (
                    candidates[0]
                    .get("content", {})
                    .get("parts", [])
                )

                answer = "\n".join(
                    part.get("text", "")
                    for part in parts
                    if part.get("text")
                )

                if not answer:
                    raise RuntimeError(
                        "Gemini returned an empty response."
                    )

                return answer

            except HTTPError as error:

                retryable_errors = (
                    429,
                    500,
                    502,
                    503,
                    504
                )

                if (
                    error.code in retryable_errors
                    and attempt < max_attempts - 1
                ):

                    wait_seconds = 2 ** (attempt + 1)

                    print(
                        f"[MADA] Gemini returned HTTP "
                        f"{error.code}. Retrying in "
                        f"{wait_seconds} seconds..."
                    )

                    time.sleep(wait_seconds)
                    continue

                try:

                    error_body = error.read().decode("utf-8")
                    details = json.loads(error_body)

                    message = (
                        details.get("error", {}).get("message")
                        or error_body
                    )

                except Exception:

                    message = (
                        "Unable to read Gemini error details."
                    )

                raise RuntimeError(
                    f"Gemini API error ({error.code}): {message}"
                ) from None

            except URLError as error:

                raise RuntimeError(
                    f"Could not connect to Gemini: {error.reason}"
                ) from None

            except TimeoutError:

                raise RuntimeError(
                    "Gemini request timed out after 180 seconds. "
                    "Please check your connection and try again."
                ) from None

        raise RuntimeError(
            "Gemini is temporarily unavailable after "
            "multiple attempts. Please try again later."
        )
