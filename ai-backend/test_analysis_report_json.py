
import json
from pathlib import Path

from app.agents.mule_project_analyzer import MuleProjectAnalyzer
from app.agents.analysis_report_agent import AnalysisReportAgent


XML_FILE = r"C:\Users\Karthik\AnypointStudio\studio-workspace\poc-3-student-batch-papi\src\main\mule\implementation.xml"


def main():
    print("Starting MADA JSON Analysis Report Test...")

    if not Path(XML_FILE).exists():
        print(f"XML file not found: {XML_FILE}")
        return

    analyzer = MuleProjectAnalyzer()

    analysis_result = analyzer.analyze_file(XML_FILE)

    report_agent = AnalysisReportAgent()

    json_report = report_agent.generate_json_report(
        analysis_result
    )

    output_dir = Path("reports")
    output_dir.mkdir(exist_ok=True)

    json_path = output_dir / "mada-analysis-report.json"

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(
            json_report,
            file,
            indent=4,
            ensure_ascii=False
        )

    print("\nJSON report generated successfully.")
    print(f"Application: {json_report['application']}")
    print(f"Status: {json_report['status']}")
    print(
        "Flows:",
        json_report["summary"]["flow_count"]
    )
    print(
        "Subflows:",
        json_report["summary"]["subflow_count"]
    )
    print(
        "Warnings:",
        json_report["summary"]["warning_count"]
    )
    print(f"Saved to: {json_path.resolve()}")


if __name__ == "__main__":
    main()
