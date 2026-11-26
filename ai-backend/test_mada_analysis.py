
import json
import urllib.request

xml_path = "sample-mule.xml"

with open(xml_path, "r", encoding="utf-8") as file:
    xml_content = file.read()

request_data = {
    "filename": "sample-mule.xml",
    "xml_content": xml_content
}

request_body = json.dumps(request_data).encode("utf-8")

request = urllib.request.Request(
    "http://127.0.0.1:8000/analyze/xml",
    data=request_body,
    headers={
        "Content-Type": "application/json"
    },
    method="POST"
)

try:
    with urllib.request.urlopen(request) as response:

        result = json.loads(
            response.read().decode("utf-8")
        )

        print("HTTP Status:", response.status)
        print("Success:", result.get("success"))
        print("Message:", result.get("message"))

        analysis = result.get("analysis", {})

        print("\nAnalysis Status:", analysis.get("status"))

        print("\nAvailable Analysis Modules:")

        for name in analysis.get("analyses", {}):
            print("-", name)

        print("\nAnalyzer Errors:")
        print(json.dumps(
            analysis.get("errors", []),
            indent=4
        ))

except Exception as error:
    print("Test failed:", error)
