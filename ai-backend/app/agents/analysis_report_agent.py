
import json
import sys
from pathlib import Path
from collections import Counter


class AnalysisReportAgent:
    """
    Converts MuleProjectAnalyzer output into a beginner-friendly
    MuleSoft application report.

    This agent performs static report generation only.
    It does not modify Mule XML or execute Mule flows.
    """

    ANALYSIS_MODULES = [
        "xml_structure",
        "flow_analysis",
        "connector_analysis",
        "dataweave_analysis",
        "error_handling_analysis",
    ]

    def __init__(self):
        self.result = {}
        self.analysis = {}
        self.report_sections = []

    # ---------------------------------------------------------
    # Main entry point
    # ---------------------------------------------------------

    def generate_report(self, analysis_result):
        if not isinstance(analysis_result, dict):
            raise ValueError("Analysis result must be a dictionary.")

        # Preserve the complete unified analyzer response.
        self.result = analysis_result

        # Extract only the individual analyzer results.
        self.analysis = analysis_result.get(
            "analyses",
            analysis_result
        )

        if not isinstance(self.analysis, dict):
            raise ValueError("Invalid analyses structure.")

        self.report_sections = []

        self._add_application_overview()
        self._add_flow_analysis()
        self._add_connector_analysis()
        self._add_dataweave_analysis()
        self._add_error_handling_analysis()
        self._add_warnings_and_recommendations()
        self._add_final_summary()

        return "\n\n".join(self.report_sections)

    # ---------------------------------------------------------
    # General helpers
    # ---------------------------------------------------------

    def _get_module(self, module_name):
        result = self.analysis.get(module_name, {})
        return result if isinstance(result, dict) else {}

    def _add_section(self, title, content):
        self.report_sections.append(
            f"## {title}\n\n{content}"
        )

    def _walk_dicts(self, value):
        """Recursively yield dictionaries from nested data."""

        if isinstance(value, dict):
            yield value

            for child in value.values():
                yield from self._walk_dicts(child)

        elif isinstance(value, list):
            for child in value:
                yield from self._walk_dicts(child)

    def _get_status(self):
        """
        Read status from the unified analyzer response.

        If status is not supplied, derive a reasonable status
        from the available modules and analyzer errors.
        """

        status = self.result.get("status")

        if status and str(status).lower() != "unknown":
            return str(status)

        completed = self._completed_module_count()
        errors = self.result.get("errors", [])

        if completed == len(self.ANALYSIS_MODULES) and not errors:
            return "success"

        if completed > 0:
            return "partial"

        return "unknown"

    def _get_application_name(self):
        xml_data = self._get_module("xml_structure")
        flow_data = self._get_module("flow_analysis")

        return (
            self.result.get("application")
            or self.result.get("source")
            or xml_data.get("application")
            or flow_data.get("application")
            or self.result.get("file")
            or "Unknown Mule application"
        )

    def _completed_module_count(self):
        return sum(
            1
            for name in self.ANALYSIS_MODULES
            if isinstance(self.analysis.get(name), dict)
            and bool(self.analysis.get(name))
        )

    def _collect_warnings(self):
        warnings = []

        for module_name in self.ANALYSIS_MODULES:
            module = self._get_module(module_name)
            module_warnings = module.get("warnings", [])

            if isinstance(module_warnings, list):
                for warning in module_warnings:
                    warnings.append({
                        "module": module_name,
                        "message": str(warning)
                    })

        return warnings

    def _format_warning(self, module_name, message):
        """
        Add context to static-analysis warnings so they are not
        incorrectly interpreted as confirmed runtime failures.
        """

        formatted = message

        if (
            module_name == "connector_analysis"
            and "not found in the extracted global configurations"
            in message
        ):
            formatted += (
                " This may mean the configuration is declared in "
                "another XML file or was not recognized by the "
                "current configuration extractor. Verify it in "
                "the complete Mule project before changing anything."
            )

        if (
            module_name == "error_handling_analysis"
            and "has no error-handler element in its XML scope"
            in message
        ):
            formatted += (
                " This is a review suggestion, not automatically "
                "an error. Check whether an inherited or global "
                "error handler applies to this flow."
            )

        return formatted

    # ---------------------------------------------------------
    # 1. Application overview
    # ---------------------------------------------------------

    def _add_application_overview(self):
        xml_data = self._get_module("xml_structure")
        flow_data = self._get_module("flow_analysis")

        application = self._get_application_name()

        flow_count = xml_data.get(
            "flow_count",
            flow_data.get("flow_count", 0)
        )

        subflow_count = xml_data.get(
            "subflow_count",
            flow_data.get("subflow_count", 0)
        )

        status = self._get_status()

        content = (
            f"- **Application:** {application}\n"
            f"- **Analysis status:** {status}\n"
            f"- **Total flows:** {flow_count}\n"
            f"- **Total subflows:** {subflow_count}\n"
            f"- **Analysis modules:** "
            f"{self._completed_module_count()} of "
            f"{len(self.ANALYSIS_MODULES)}"
        )

        self._add_section("1. Application Overview", content)

    # ---------------------------------------------------------
    # 2. Flow analysis
    # ---------------------------------------------------------

    def _add_flow_analysis(self):
        flow_data = self._get_module("flow_analysis")
        flows = flow_data.get("flows", [])

        if not isinstance(flows, list) or not flows:
            self._add_section(
                "2. Flow Analysis",
                "No flow information was returned by the analyzer."
            )
            return

        lines = []

        for flow in flows:
            if not isinstance(flow, dict):
                continue

            name = flow.get("name", "Unnamed flow")
            flow_type = flow.get("type", "flow")
            step_count = flow.get("step_count", 0)

            lines.append(
                f"### {name}\n"
                f"- **Type:** {flow_type}\n"
                f"- **Execution steps:** {step_count}"
            )

            references = flow.get("flow_references", [])

            if references:
                lines.append("- **Flow references:**")

                for reference in references:
                    if isinstance(reference, dict):
                        ref_name = reference.get(
                            "name", "Unknown reference"
                        )
                        ref_type = reference.get(
                            "type", "unknown"
                        )

                        lines.append(
                            f"  - {ref_name} ({ref_type})"
                        )
                    else:
                        lines.append(f"  - {reference}")

            steps = flow.get("execution_steps", [])

            if steps:
                lines.append("- **Execution sequence:**")

                for step in steps:
                    if not isinstance(step, dict):
                        continue

                    number = step.get("step", "?")
                    component = step.get(
                        "component", "Unknown component"
                    )
                    explanation = step.get("explanation", "")

                    line = f"  {number}. `{component}`"

                    if explanation:
                        line += f" — {explanation}"

                    lines.append(line)

            error_handling = flow.get("error_handling", [])

            if error_handling:
                lines.append("- **Error handling:**")

                for handler in error_handling:
                    if not isinstance(handler, dict):
                        continue

                    handler_type = handler.get(
                        "type", "Unknown handler"
                    )

                    attributes = handler.get("attributes", {})

                    if not isinstance(attributes, dict):
                        attributes = {}

                    error_type = attributes.get(
                        "type", "Not specified"
                    )

                    lines.append(
                        f"  - {handler_type} "
                        f"(error type: {error_type})"
                    )

            lines.append("")

        self._add_section(
            "2. Flow Analysis",
            "\n".join(lines).strip()
            or "No flow details were available."
        )

    # ---------------------------------------------------------
    # 3. Connector analysis
    # ---------------------------------------------------------

    def _add_connector_analysis(self):
        connector_data = self._get_module(
            "connector_analysis"
        )

        if not connector_data:
            self._add_section(
                "3. Connector Analysis",
                "Connector analysis results are unavailable."
            )
            return

        connector_counts = Counter()
        operations = []
        seen_operations = set()

        for item in self._walk_dicts(connector_data):
            connector = item.get("connector")
            component = item.get("component")

            if connector:
                connector_counts[str(connector)] += 1

            attributes = item.get("attributes", {})

            if not isinstance(attributes, dict):
                attributes = {}

            if connector and component:
                config_ref = attributes.get("config-ref", "")

                operation_key = (
                    str(connector),
                    str(component),
                    str(config_ref)
                )

                if operation_key not in seen_operations:
                    seen_operations.add(operation_key)
                    operations.append(operation_key)

        lines = []

        if connector_counts:
            lines.append("**Detected connector references:**")

            for connector, count in sorted(
                connector_counts.items()
            ):
                lines.append(
                    f"- {connector}: {count} occurrence(s)"
                )

        if operations:
            lines.append("\n**Connector components:**")

            for connector, component, config_ref in operations:
                description = (
                    f"- {connector}: `{component}`"
                )

                if config_ref:
                    description += (
                        f" (config-ref: `{config_ref}`)"
                    )

                lines.append(description)

        warnings = connector_data.get("warnings", [])

        if warnings:
            lines.append("\n**Connector warnings:**")

            for warning in warnings:
                lines.append(
                    f"- {self._format_warning('connector_analysis', str(warning))}"
                )

        if not lines:
            lines.append(
                "No connector details were identified in the "
                "returned analysis."
            )

        lines.append(
            "\nNote: These are static XML findings. "
            "They do not confirm that external systems are "
            "currently reachable."
        )

        self._add_section(
            "3. Connector Analysis",
            "\n".join(lines)
        )

    # ---------------------------------------------------------
    # 4. DataWeave analysis
    # ---------------------------------------------------------

    def _add_dataweave_analysis(self):
        dw_data = self._get_module("dataweave_analysis")

        if not dw_data:
            self._add_section(
                "4. DataWeave Analysis",
                "DataWeave analysis results are unavailable."
            )
            return

        scripts = dw_data.get("scripts", [])

        if not isinstance(scripts, list):
            scripts = []

        full_scripts = []
        inline_expressions = []

        for script in scripts:
            if not isinstance(script, dict):
                continue

            if script.get("is_full_script") is True:
                full_scripts.append(script)
            else:
                inline_expressions.append(script)

        detected_count = dw_data.get(
            "dataweave_block_count",
            len(scripts)
        )

        lines = [
            f"- **Detected DataWeave blocks/expressions:** "
            f"{detected_count}",
            f"- **Complete DataWeave scripts:** "
            f"{len(full_scripts)}",
            f"- **Inline expressions:** "
            f"{len(inline_expressions)}"
        ]

        # Display complete DataWeave scripts first.
        for script in full_scripts:
            self._append_dataweave_item(
                lines,
                script,
                "Full DataWeave script"
            )

        # Inline expressions are not incorrectly presented
        # as complete DataWeave scripts.
        for index, script in enumerate(
            inline_expressions,
            start=1
        ):
            self._append_dataweave_item(
                lines,
                script,
                f"Inline expression {index}"
            )

        warnings = dw_data.get("warnings", [])

        if warnings:
            lines.append("\n**DataWeave warnings:**")

            for warning in warnings:
                lines.append(f"- {warning}")

        if not scripts:
            lines.append("No DataWeave blocks were detected.")

        lines.append(
            "\nNote: This is static DataWeave inspection. "
            "The expressions and scripts have not been compiled "
            "or executed by Mule Runtime."
        )

        self._add_section(
            "4. DataWeave Analysis",
            "\n".join(lines)
        )

    def _append_dataweave_item(self, lines, item, title):
        number = item.get("script_number", "?")

        component = item.get(
            "component_name",
            item.get("component", "Unknown component")
        )

        version = item.get(
            "dataweave_version",
            "Not identified"
        )

        output = item.get(
            "output_directive",
            "Not identified"
        )

        lines.append(
            f"\n### {title} {number}\n"
            f"- **Component:** {component}\n"
            f"- **DataWeave version:** {version}\n"
            f"- **Output format:** {output}"
        )

        operations = item.get("operations", [])

        if operations:
            operation_names = [
                operation.get("name", "unknown")
                for operation in operations
                if isinstance(operation, dict)
            ]

            if operation_names:
                lines.append(
                    "- **Operations:** "
                    + ", ".join(operation_names)
                )

        references = item.get("references", {})

        if isinstance(references, dict):
            used = [
                name
                for name, value in references.items()
                if value
            ]

            if used:
                lines.append(
                    "- **Referenced values:** "
                    + ", ".join(used)
                )

        location = item.get("location")

        if location:
            lines.append(f"- **Location:** {location}")

    # ---------------------------------------------------------
    # 5. Error handling analysis
    # ---------------------------------------------------------

    def _add_error_handling_analysis(self):
        error_data = self._get_module(
            "error_handling_analysis"
        )

        if not error_data:
            self._add_section(
                "5. Error Handling Analysis",
                "Error handling results are unavailable."
            )
            return

        summary = error_data.get("summary", {})

        if not isinstance(summary, dict):
            summary = {}

        lines = [
            f"- **Error handlers:** "
            f"{summary.get('error_handler_count', 0)}",
            f"- **On Error Continue:** "
            f"{summary.get('on_error_continue_count', 0)}",
            f"- **On Error Propagate:** "
            f"{summary.get('on_error_propagate_count', 0)}",
            f"- **Redelivery policies:** "
            f"{summary.get('redelivery_policy_count', 0)}"
        ]

        scopes = error_data.get("flows", [])

        if not isinstance(scopes, list):
            scopes = []

        for scope in scopes:
            if not isinstance(scope, dict):
                continue

            scope_name = scope.get(
                "scope_name",
                scope.get("name", "Unknown scope")
            )

            scope_type = scope.get(
                "scope_type",
                scope.get("type", "unknown")
            )

            lines.append(
                f"\n### Scope: {scope_name}\n"
                f"- **Scope type:** {scope_type}"
            )

            handlers = scope.get(
                "handlers",
                scope.get("error_handlers", [])
            )

            if not isinstance(handlers, list):
                continue

            for handler in handlers:
                if not isinstance(handler, dict):
                    continue

                handler_type = handler.get(
                    "type", "Unknown handler"
                )

                attributes = handler.get("attributes", {})

                if not isinstance(attributes, dict):
                    attributes = {}

                error_type = attributes.get(
                    "type", "Not specified"
                )

                handler_name = attributes.get(
                    "name", "Unnamed handler"
                )

                lines.append(
                    f"- **{handler_type}:** {handler_name} "
                    f"(error type: {error_type})"
                )

        warnings = error_data.get("warnings", [])

        if warnings:
            lines.append("\n**Error-handling review notes:**")

            for warning in warnings:
                lines.append(
                    f"- {self._format_warning('error_handling_analysis', str(warning))}"
                )

        self._add_section(
            "5. Error Handling Analysis",
            "\n".join(lines)
        )

    # ---------------------------------------------------------
    # 6. Warnings and recommendations
    # ---------------------------------------------------------

    def _add_warnings_and_recommendations(self):
        warnings = self._collect_warnings()
        analyzer_errors = self.result.get("errors", [])

        if not isinstance(analyzer_errors, list):
            analyzer_errors = [analyzer_errors]

        lines = []

        if warnings:
            lines.append("### Analyzer warnings")

            for warning in warnings:
                message = self._format_warning(
                    warning["module"],
                    warning["message"]
                )

                lines.append(
                    f"- **{warning['module']}:** {message}"
                )
        else:
            lines.append(
                "No warnings were returned by the analyzers."
            )

        if analyzer_errors:
            lines.append("\n### Analyzer errors")

            for error in analyzer_errors:
                lines.append(f"- {error}")

        lines.append(
            "\n### Recommended review\n"
            "- Confirm that every referenced `config-ref` "
            "resolves to a configuration in the complete Mule project.\n"
            "- Check whether connector configurations are declared "
            "in other XML files or externalized configuration files.\n"
            "- Verify external API endpoints and credentials using "
            "secure configuration and appropriate connection tests.\n"
            "- Review whether important flows have suitable local, "
            "inherited, or global error handling.\n"
            "- Test DataWeave transformations with representative "
            "input and expected output payloads.\n"
            "- Validate batch processing and database outcomes "
            "with integration tests."
        )

        lines.append(
            "\n**Important:** Static analyzer warnings are review "
            "items. They are not proof of a runtime failure."
        )

        self._add_section(
            "6. Warnings and Recommendations",
            "\n".join(lines)
        )

    # ---------------------------------------------------------
    # 7. Final summary
    # ---------------------------------------------------------

    def _add_final_summary(self):
        xml_data = self._get_module("xml_structure")

        flow_count = xml_data.get("flow_count", 0)
        subflow_count = xml_data.get("subflow_count", 0)

        status = self._get_status()
        completed = self._completed_module_count()

        content = (
            f"The static analysis of this Mule application "
            f"identified **{flow_count} flows** and "
            f"**{subflow_count} subflows**.\n\n"
            f"The unified analyzer status is **{status}**. "
            f"{completed} of {len(self.ANALYSIS_MODULES)} "
            f"analysis modules returned results.\n\n"
            "The report summarizes XML structure, flow execution, "
            "connector usage, DataWeave expressions and error handling.\n\n"
            "This report is based on static XML inspection. It does "
            "not establish runtime health, successful database "
            "connectivity, or successful execution of the application."
        )

        self._add_section(
            "7. Overall Application Summary",
            content
        )

    def generate_json_report(self, analysis_result):
        """
        Generate structured JSON containing analysis results
        and the generated Markdown report.
        """

        markdown_report = self.generate_report(analysis_result)

        xml_data = self._get_module("xml_structure")
        flow_data = self._get_module("flow_analysis")

        flow_count = xml_data.get(
            "flow_count",
            flow_data.get("flow_count", 0)
        )

        subflow_count = xml_data.get(
            "subflow_count",
            flow_data.get("subflow_count", 0)
        )

        json_report = {
            "application": self._get_application_name(),
            "status": self._get_status(),

            "summary": {
                "flow_count": flow_count,
                "subflow_count": subflow_count,
                "completed_modules": self._completed_module_count(),
                "total_modules": len(self.ANALYSIS_MODULES),
                "warning_count": len(self._collect_warnings())
            },

            "analyses": self.analysis,
            "markdown_report": markdown_report
        }

        return json_report





# -------------------------------------------------------------
# Command-line test
# -------------------------------------------------------------

def main():
    if len(sys.argv) != 2:
        print(
            "Usage: python -m app.agents.analysis_report_agent "
            "analysis-result.json"
        )
        return

    json_path = Path(sys.argv[1])

    if not json_path.exists():
        print(f"File not found: {json_path}")
        return

    try:
        with json_path.open("r", encoding="utf-8") as file:
            analysis_result = json.load(file)

        agent = AnalysisReportAgent()
        report = agent.generate_report(analysis_result)

        print("\nMADA ANALYSIS REPORT\n")
        print("=" * 65)
        print(report)
        print("=" * 65)

    except (json.JSONDecodeError, ValueError, OSError) as error:
        print(f"Report generation failed: {error}")


if __name__ == "__main__":
    main()
