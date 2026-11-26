
from app.providers.gemini import GeminiProvider

provider = GeminiProvider()

print("API key configured:", provider.test_connection())

answer = provider.generate_response(
    [
        {
            "role": "user",
            "content": "Explain MuleSoft API-led connectivity in simple terms."
        }
    ],
    "gemini-2.5-flash"
)

print("\nGemini response:\n")
print(answer)
