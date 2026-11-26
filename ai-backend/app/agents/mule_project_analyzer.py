
import json
from pathlib import Path

from app.agents.mule_xml_parser import MuleXMLParser
from app.agents.flow_analysis_agent import FlowAnalysisAgent
from app.agents.connector_analyzer import ConnectorAnalyzer
from app.agents.dataweave_analyzer import DataWeaveAnalyzer
from app.agents.error_handling_analyzer import ErrorHandlingAnalyzer


class MuleProjectAnalyzer:
    """
    Unified entry point for MADA's MuleSoft static analyzers.

    Runs the individual analyzers against Mule XML files and
    combines their results into one structured response.

    This tool performs static analysis only.
    It does not execute or modify Mule applications.
    """

    MAX_XML_FILES = 50
    MAX_TOTAL_SIZE = 10 * 1024 * 1024

    def __init__(self):
        self.xml_parser = MuleXMLParser()
        self.flow_analyzer = FlowAnalysisAgent()
        self.connector_analyzer = ConnectorAnalyzer()
        self.dataweave_analyzer = DataWeaveAnalyzer()
        self.error_handling_analyzer = ErrorHandlingAnalyzer()

    def discover_xml_files(self, project_path):
        """Find Mule XML files while excluding generated folders."""
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
        total_size = sum(path.stat().st_size for path in xml_files)

        if total_size > self.MAX_TOTAL_SIZE:
            raise ValueError(
                "Total XML size exceeds the 10 MB analysis limit."
            )

        return total_size

    def invoke_analyzer(self, analyzer, file_path, method_names):
        """
        Call the first supported file-analysis method.

        Different analyzers may expose different public method names.
        """
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

                result["analyses"][analysis_name] = analysis_result

            except Exception as error:
                result["status"] = "partial"
                result["errors"].append({
                    "analyzer": analysis_name,
                    "error": str(error),
                })

        return result

    def analyze_file(self, file_path):
        """Analyze one Mule XML file using all available analyzers."""
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

        success_count = sum(
            1 for result in file_results
            if result["status"] == "success"
        )

        partial_count = sum(
            1 for result in file_results
            if result["status"] == "partial"
        )

        failed_count = len(file_results) - success_count - partial_count

        return {
            "project": root.name,
            "project_path": str(root),
            "summary": {
                "xml_file_count": len(xml_files),
                "successful_files": success_count,
                "partially_analyzed_files": partial_count,
                "failed_files": failed_count,
                "total_size_bytes": total_size,
            },
            "files": file_results,
            "note": (
                "Static analysis only. MADA does not execute "
                "Mule applications or modify project files."
            ),
        }

    def get_report(self, result):
        """Create a readable summary of the unified analysis."""
        lines = [
            "",
            "MADA UNIFIED MULE PROJECT ANALYSIS",
            "=" * 55,
        ]

        if "summary" not in result:
            lines.extend([
                f"File: {result.get('file', 'Unknown')}",
                f"Status: {result.get('status', 'Unknown')}",
            ])

            for analysis_name, analysis in result.get(
                "analyses", {}
            ).items():
                lines.append(
                    f"- {analysis_name}: Analysis completed"
                )

            for error in result.get("errors", []):
                lines.append(
                    f"- {error['analyzer']} error: {error['error']}"
                )

            return "\n".join(lines)

        summary = result["summary"]

        lines.extend([
            f"Project: {result['project']}",
            "",
            "SUMMARY",
            "-" * 55,
            f"XML files: {summary['xml_file_count']}",
            f"Successful: {summary['successful_files']}",
            f"Partial: {summary['partially_analyzed_files']}",
            f"Failed: {summary['failed_files']}",
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

            for analysis_name in file_result["analyses"]:
                lines.append(
                    f"  - {analysis_name}: completed"
                )

            for error in file_result["errors"]:
                lines.append(
                    f"  - {error['analyzer']}: {error['error']}"
                )

        lines.extend([
            "",
            result["note"],
        ])

        return "\n".join(lines)


def main():
    import sys

    print("Starting MADA Unified Mule Project Analyzer...")

    if len(sys.argv) < 2:
        print(
            "\nUsage:\n"
            "Analyze one file:\n"
            "python -m app.agents.mule_project_analyzer sample-mule.xml\n\n"
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
