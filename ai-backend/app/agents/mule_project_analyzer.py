import json
from pathlib import Path

from app.agents.mule_xml_parser import MuleXMLParser
from app.agents.flow_analysis_agent import FlowAnalysisAgent
from app.agents.connector_analyzer import ConnectorAnalyzer
from app.agents.dataweave_analyzer import DataWeaveAnalyzer
from app.agents.error_handling_analyzer import ErrorHandlingAnalyzer
from app.agents.issue_detection_agent import IssueDetectionAgent


class MuleProjectAnalyzer:
    """
    Unified entry point for MADA's MuleSoft static analyzers.

    Supports project-wide reference validation.

    Static analysis only:
    - Does not execute Mule applications.
    - Does not modify project files.
    """

    MAX_XML_FILES = 50
    MAX_TOTAL_SIZE = 10 * 1024 * 1024

    def __init__(self):
        self.xml_parser = MuleXMLParser()
        self.flow_analyzer = FlowAnalysisAgent()
        self.connector_analyzer = ConnectorAnalyzer()
        self.dataweave_analyzer = DataWeaveAnalyzer()
        self.error_handling_analyzer = ErrorHandlingAnalyzer()
        self.issue_detection_agent = IssueDetectionAgent()

    def discover_xml_files(self, project_path):
        """Find XML files while excluding generated folders."""

        root = Path(project_path)

        if not root.exists():
            raise FileNotFoundError(
                f"Project path not found: {root}"
            )

        if not root.is_dir():
            raise NotADirectoryError(
                f"Expected a project directory: {root}"
            )

        excluded_directories = {
            ".git",
            ".metadata",
            ".settings",
            "target",
            "node_modules",
            "bin",
            "__pycache__",
        }

        xml_files = []

        for path in root.rglob("*.xml"):

            if any(
                part in excluded_directories
                for part in path.relative_to(root).parts
            ):
                continue

            if path.is_file():
                xml_files.append(path)

            if len(xml_files) > self.MAX_XML_FILES:
                raise ValueError(
                    f"Project contains more than "
                    f"{self.MAX_XML_FILES} XML files. "
                    "Please analyze a smaller project or folder."
                )

        return sorted(xml_files)

    def validate_project_size(self, xml_files):
        """Enforce a total XML size limit."""

        total_size = sum(
            path.stat().st_size for path in xml_files
        )

        if total_size > self.MAX_TOTAL_SIZE:
            raise ValueError(
                "Total XML size exceeds the 10 MB analysis limit."
            )

        return total_size

    def invoke_analyzer(self, analyzer, file_path, method_names):
        """Call the first supported file-analysis method."""

        for method_name in method_names:

            method = getattr(analyzer, method_name, None)

            if callable(method):
                return method(file_path)

        raise AttributeError(
            f"{analyzer.__class__.__name__} does not expose "
            f"any supported methods: {method_names}"
        )

    def analyze_one_file(self, file_path, project_root):
        """Run all specialized analyzers against one XML file."""

        relative_path = str(
            file_path.relative_to(project_root)
        )

        result = {
            "file": relative_path,
            "status": "success",
            "analyses": {},
            "errors": [],
        }

        analyzers = [
            (
                "xml_structure",
                self.xml_parser,
                ("parse_file",),
            ),
            (
                "flow_analysis",
                self.flow_analyzer,
                ("analyze_file",),
            ),
            (
                "connector_analysis",
                self.connector_analyzer,
                ("analyze_file", "analyze"),
            ),
            (
                "dataweave_analysis",
                self.dataweave_analyzer,
                ("analyze_file",),
            ),
            (
                "error_handling_analysis",
                self.error_handling_analyzer,
                ("analyze_file",),
            ),
        ]

        for analysis_name, analyzer, methods in analyzers:

            try:
                analysis_result = self.invoke_analyzer(
                    analyzer,
                    file_path,
                    methods,
                )

                result["analyses"][analysis_name] = (
                    analysis_result
                )

            except Exception as error:

                result["status"] = "partial"

                result["errors"].append({
                    "analyzer": analysis_name,
                    "error": str(error),
                })

        # Initial per-file issue detection.
        try:
            result["issue_analysis"] = (
                self.issue_detection_agent.detect_file_issues(
                    result
                )
            )

        except Exception as error:

            result["status"] = "partial"

            result["errors"].append({
                "analyzer": "issue_detection",
                "error": str(error),
            })

        return result

    def analyze_file(self, file_path):
        """Analyze one Mule XML file."""

        path = Path(file_path).resolve()

        if not path.exists():
            raise FileNotFoundError(
                f"Mule XML file not found: {path}"
            )

        if not path.is_file() or path.suffix.lower() != ".xml":
            raise ValueError(
                "Please provide an existing Mule XML file."
            )

        if path.stat().st_size > self.MAX_TOTAL_SIZE:
            raise ValueError(
                "XML file exceeds the 10 MB analysis limit."
            )

        return self.analyze_one_file(
            path,
            path.parent,
        )

    def analyze_project(self, project_path):
        """Analyze every eligible XML file in a Mule project."""

        root = Path(project_path).resolve()

        xml_files = self.discover_xml_files(root)

        if not xml_files:
            raise ValueError(
                "No XML files were found in the selected project."
            )

        total_size = self.validate_project_size(xml_files)

        file_results = []

        for file_path in xml_files:

            file_results.append(
                self.analyze_one_file(
                    file_path,
                    root,
                )
            )

        # -------------------------------------------------
        # PROJECT-WIDE REFERENCE VALIDATION
        # -------------------------------------------------

        project_reference_analysis = (
            self.issue_detection_agent.validate_project_references(
                file_results
            )
        )

        # -------------------------------------------------
        # FILE STATUS SUMMARY
        # -------------------------------------------------

        success_count = sum(
            1 for result in file_results
            if result["status"] == "success"
        )

        partial_count = sum(
            1 for result in file_results
            if result["status"] == "partial"
        )

        failed_count = (
            len(file_results)
            - success_count
            - partial_count
        )

        # -------------------------------------------------
        # PROJECT ISSUE SUMMARY
        # -------------------------------------------------

        severity_counts = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "info": 0,
        }

        total_issues = 0

        for file_result in file_results:

            issue_analysis = file_result.get(
                "issue_analysis", {}
            )

            total_issues += issue_analysis.get(
                "issue_count", 0
            )

            for severity, count in issue_analysis.get(
                "severity_summary", {}
            ).items():

                if severity in severity_counts:
                    severity_counts[severity] += count

        return {
            "project": root.name,
            "project_path": str(root),

            "summary": {
                "xml_file_count": len(xml_files),
                "successful_files": success_count,
                "partially_analyzed_files": partial_count,
                "failed_files": failed_count,
                "total_size_bytes": total_size,
                "total_issues": total_issues,
                "issue_severity_summary": severity_counts,
            },

            "project_reference_analysis": (
                project_reference_analysis
            ),

            "files": file_results,

            "note": (
                "Static analysis only. MADA does not execute "
                "Mule applications or modify project files. "
                "Connector configurations and flow references "
                "are validated across the analyzed XML files. "
                "Findings should be verified against runtime behavior."
            ),
        }

    def get_report(self, result):
        """Create a readable summary of unified analysis."""

        lines = [
            "",
            "MADA UNIFIED MULE PROJECT ANALYSIS",
            "=" * 55,
        ]

        # ------------------------------------------------
        # SINGLE XML FILE REPORT
        # ------------------------------------------------

        if "summary" not in result:

            lines.extend([
                f"File: {result.get('file', 'Unknown')}",
                f"Status: {result.get('status', 'Unknown')}",
                "",
                "STATIC ANALYSIS",
                "-" * 55,
            ])

            for analysis_name in result.get(
                "analyses", {}
            ):
                lines.append(
                    f"- {analysis_name}: Analysis completed"
                )

            for error in result.get("errors", []):

                lines.append(
                    f"- {error['analyzer']} error: "
                    f"{error['error']}"
                )

            issue_analysis = result.get(
                "issue_analysis", {}
            )

            lines.extend([
                "",
                "ISSUE DETECTION",
                "-" * 55,
                f"Total issues: "
                f"{issue_analysis.get('issue_count', 0)}",
                "",
                "SEVERITY SUMMARY",
            ])

            for severity, count in issue_analysis.get(
                "severity_summary", {}
            ).items():
                lines.append(
                    f"{severity.upper()}: {count}"
                )

            for finding in issue_analysis.get(
                "findings", []
            ):
                lines.extend([
                    "",
                    f"[{finding['severity'].upper()}] "
                    f"{finding['title']}",
                    f"  ID: {finding['id']}",
                    f"  Rule: {finding['rule_id']}",
                    f"  Category: {finding['category']}",
                    f"  Flow: {finding.get('flow') or 'N/A'}",
                    f"  Processor: "
                    f"{finding.get('processor') or 'N/A'}",
                    f"  Evidence: {finding['evidence']}",
                    f"  Recommendation: "
                    f"{finding['recommendation']}",
                ])

            if not issue_analysis.get("findings"):
                lines.append(
                    "\nNo issues detected by the current rules."
                )

            lines.extend([
                "",
                issue_analysis.get("note", ""),
            ])

            return "\n".join(lines)

        # ------------------------------------------------
        # COMPLETE PROJECT REPORT
        # ------------------------------------------------

        summary = result["summary"]

        lines.extend([
            f"Project: {result['project']}",
            "",
            "PROJECT SUMMARY",
            "-" * 55,
            f"XML files: {summary['xml_file_count']}",
            f"Successful: {summary['successful_files']}",
            f"Partial: {summary['partially_analyzed_files']}",
            f"Failed: {summary['failed_files']}",
            f"Issues detected: {summary.get('total_issues', 0)}",
            f"Issue severity: "
            f"{summary.get('issue_severity_summary', {})}",
        ])

        # Project registry summary.
        registry = result.get(
            "project_reference_analysis", {}
        )

        lines.extend([
            "",
            "PROJECT-WIDE REFERENCE VALIDATION",
            "-" * 55,
            f"Parsed XML files: "
            f"{registry.get('parsed_file_count', 0)}",
            f"Configurations discovered: "
            f"{registry.get('configuration_count', 0)}",
            f"Flows and subflows discovered: "
            f"{registry.get('flow_count', 0)}",
            f"XML parsing failures: "
            f"{registry.get('parse_failure_count', 0)}",
        ])

        lines.extend([
            "",
            "FILE ANALYSIS",
            "-" * 55,
        ])

        for file_result in result["files"]:

            lines.append(
                f"\nFile: {file_result['file']}"
            )

            lines.append(
                f"Status: {file_result['status']}"
            )

            for analysis_name in file_result.get(
                "analyses", {}
            ):
                lines.append(
                    f"  - {analysis_name}: completed"
                )

            for error in file_result.get("errors", []):

                lines.append(
                    f"  - {error['analyzer']}: "
                    f"{error['error']}"
                )

            issue_analysis = file_result.get(
                "issue_analysis", {}
            )

            findings = issue_analysis.get(
                "findings", []
            )

            lines.append(
                f"  Issues detected: "
                f"{issue_analysis.get('issue_count', 0)}"
            )

            for finding in findings:

                lines.extend([
                    "",
                    f"  [{finding['severity'].upper()}] "
                    f"{finding['title']}",
                    f"    ID: {finding['id']}",
                    f"    Rule: {finding['rule_id']}",
                    f"    Flow: "
                    f"{finding.get('flow') or 'N/A'}",
                    f"    Processor: "
                    f"{finding.get('processor') or 'N/A'}",
                    f"    Evidence: {finding['evidence']}",
                    f"    Recommendation: "
                    f"{finding['recommendation']}",
                ])

        lines.extend([
            "",
            result["note"],
        ])

        return "\n".join(lines)


def main():
    import sys

    print(
        "Starting MADA Unified Mule Project Analyzer..."
    )

    if len(sys.argv) < 2:

        print(
            "\nUsage:\n"
            "Analyze one file:\n"
            "python -m app.agents.mule_project_analyzer "
            "sample-mule.xml\n\n"
            "Analyze a project folder:\n"
            "python -m app.agents.mule_project_analyzer "
            "C:\\MuleProjects\\EmployeeAPI"
        )

        return

    target = Path(sys.argv[1])

    analyzer = MuleProjectAnalyzer()

    try:

        if target.is_dir():
            result = analyzer.analyze_project(target)

        else:
            result = analyzer.analyze_file(target)

        print("\nStructured Unified Analysis:\n")

        print(
            json.dumps(
                result,
                indent=4,
                default=str,
            )
        )

        print(analyzer.get_report(result))

    except Exception as error:

        print(f"\nAnalysis failed: {error}")
        raise


if __name__ == "__main__":
    main()