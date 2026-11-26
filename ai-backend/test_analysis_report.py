
import json

from app.agents.mule_project_analyzer import MuleProjectAnalyzer
from app.agents.analysis_report_agent import AnalysisReportAgent


XML_FILE = r"C:\Users\Karthik\AnypointStudio\studio-workspace\poc-3-student-batch-papi\src\main\mule\implementation.xml"

print("Starting MADA Analysis Report Test...")

# 1. Run the existing unified analyzer
analyzer = MuleProjectAnalyzer()

analysis_result = analyzer.analyze_file(XML_FILE)

# 2. Generate the readable report
report_agent = AnalysisReportAgent()

report = report_agent.generate_report(analysis_result)

# 3. Display the report
print("\nMADA ANALYSIS REPORT")
print("=" * 65)

print(report)

print("=" * 65)

# 4. Save the report
output_file = "mada-analysis-report.md"

with open(output_file, "w", encoding="utf-8") as file:
    file.write(report)

print(f"\nReport saved successfully: {output_file}")
