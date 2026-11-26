
import json
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


BASE_URL = "http://127.0.0.1:8000"


def post_json(endpoint, data):

    url = BASE_URL + endpoint

    body = json.dumps(data).encode("utf-8")

    request = Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:

        with urlopen(request, timeout=180) as response:

            result = json.loads(
                response.read().decode("utf-8")
            )

            print("HTTP Status:", response.status)

            return result

    except HTTPError as error:

        error_body = error.read().decode(
            "utf-8",
            errors="replace"
        )

        print("HTTP Error:", error.code)
        print("Response:", error_body)

        return None

    except URLError as error:

        print("Connection Error:", error.reason)

        return None


def main():

    print("===================================")
    print(" MADA AI ANALYSIS TEST")
    print("===================================")

    xml_file = Path("sample-mule.xml")

    if not xml_file.exists():

        print("sample-mule.xml not found.")
        return

    xml_content = xml_file.read_text(
        encoding="utf-8-sig"
    )

    # STEP 1: Run static XML analysis.

    print("\nSTEP 1: Running Mule XML analysis...")

    static_result = post_json(
        "/analyze/xml",
        {
            "filename": xml_file.name,
            "xml_content": xml_content
        }
    )

    if not static_result or not static_result.get("success"):

        print("Static analysis failed.")
        return

    analysis = static_result.get("analysis")

    if not isinstance(analysis, dict):

        print("Invalid static analysis response.")
        return

    print("Static analysis completed.")

    # STEP 2: Run AI-powered explanation.

    print("\nSTEP 2: Running AI-powered analysis...")

    ai_result = post_json(
        "/analyze/ai",
        {
            "analysis": analysis
        }
    )

    if not ai_result or not ai_result.get("success"):

        print("AI analysis failed.")
        return

    result = ai_result.get("result", {})

    print("\n===================================")
    print(" AI ANALYSIS COMPLETED")
    print("===================================")

    print("Application:", result.get("application"))
    print("Provider:", result.get("provider"))
    print("Model:", result.get("model"))

    print("\nReport saved:", result.get("report_saved"))
    print("Report path:", result.get("report_path"))

    print("\nAI ANALYSIS:")
    print("-----------------------------------")

    print(result.get("ai_analysis", ""))

    print("\n===================================")

    if result.get("report_saved"):

        print("AI report generated successfully.")

    else:

        print("AI response generated, but report saving failed.")
        print("Reason:", result.get("report_save_error"))


if __name__ == "__main__":
    main()
