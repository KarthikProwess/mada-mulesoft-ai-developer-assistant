
from collections import Counter

from app.agents.flow_analysis_agent import FlowAnalysisAgent


class ConnectorAnalyzer:
    """
    Analyzes connector usage in a Mule application.

    Uses structured output from FlowAnalysisAgent.
    This is static analysis; it does not connect to external systems.
    """

    STRUCTURAL_COMPONENTS = {
        "message",
        "sql",
        "error-handler",
        "when",
        "otherwise",
        "route",
        "batch-step",
    }

    OPERATION_EXPLANATIONS = {
        "listener": "Receives inbound requests or messages.",
        "request": "Sends an outbound request to another service.",
        "select": "Reads records from a database.",
        "insert": "Inserts records into a database.",
        "update": "Updates existing database records.",
        "delete": "Deletes records from a database.",
        "bulk-insert": "Inserts multiple database records in a bulk operation.",
        "bulk-update": "Updates multiple database records in a bulk operation.",
        "publish": "Publishes a message to a messaging destination.",
        "consume": "Consumes a message from a messaging destination.",
        "ack": "Acknowledges message processing.",
        "read": "Reads data from a file or remote resource.",
        "write": "Writes data to a file or remote resource.",
        "list": "Lists files or resources.",
        "get": "Retrieves a resource from a service.",
        "create": "Creates a resource in a service.",
        "upsert": "Creates or updates a record.",
        "query": "Executes a query against a service.",
        "send": "Sends a message or notification.",
    }

    def __init__(self):
        self.flow_analyzer = FlowAnalysisAgent()

    def analyze_file(self, file_path):
        """Analyze connectors directly from a Mule XML file."""
        flow_analysis = self.flow_analyzer.analyze_file(file_path)
        return self.analyze_analysis(flow_analysis)

    def analyze_analysis(self, flow_analysis):
        """Analyze connector usage from FlowAnalysisAgent output."""

        connector_operations = []
        connector_counts = Counter()
        operation_counts = Counter()
        config_references = []

        if not isinstance(flow_analysis, dict):
            raise ValueError("Invalid flow analysis input. Expected a dictionary.")

        global_configurations = flow_analysis.get(
            "global_configurations", []
        )

        known_configs = {}

        if isinstance(global_configurations, list):
            for config in global_configurations:
                if not isinstance(config, dict):
                    continue

                attributes = config.get("attributes", {})

                if not isinstance(attributes, dict):
                    continue

                config_name = attributes.get("name")

                if config_name:
                    known_configs[config_name] = config

        def inspect_processor(processor, flow_name):
            """
            Recursively inspect processors.

            FlowAnalysisAgent can return nested lists for components
            such as Try scopes and their error handlers.
            """

            # FIX: Handle nested lists before accessing dictionary methods.
            if isinstance(processor, list):
                for item in processor:
                    inspect_processor(item, flow_name)
                return

            # Ignore unexpected non-dictionary values safely.
            if not isinstance(processor, dict):
                return

            component = processor.get("component", "unknown")
            connector = processor.get("connector")

            attributes = processor.get("attributes", {})
            if not isinstance(attributes, dict):
                attributes = {}

            children = processor.get("children", [])
            if not isinstance(children, list):
                children = []

            # Ignore structural XML elements that are not
            # independent connector operations.
            if (
                component not in self.STRUCTURAL_COMPONENTS
                and connector
            ):
                config_ref = attributes.get("config-ref")

                explanation = self.OPERATION_EXPLANATIONS.get(
                    component,
                    f"Performs the '{component}' operation using "
                    f"the {connector} connector."
                )

                config_status = "Not applicable"

                if config_ref:
                    if config_ref in known_configs:
                        config_status = "Found"
                    else:
                        config_status = (
                            "Not found in extracted configurations"
                        )

                    config_references.append({
                        "flow": flow_name,
                        "component": component,
                        "connector": connector,
                        "config_ref": config_ref,
                        "status": config_status,
                    })

                operation_info = {
                    "flow": flow_name,
                    "component": component,
                    "connector": connector,
                    "config_ref": config_ref,
                    "config_status": config_status,
                    "explanation": explanation,
                }

                connector_operations.append(operation_info)
                connector_counts[connector] += 1
                operation_counts[component] += 1

            # Recursively inspect child processors.
            for child in children:
                inspect_processor(child, flow_name)

            # Some FlowAnalysisAgent outputs store handler processors
            # directly inside a processor's error_handling property.
            nested_error_handling = processor.get("error_handling", [])

            if isinstance(nested_error_handling, list):
                for handler in nested_error_handling:
                    inspect_handler(handler, flow_name)

        def inspect_handler(handler, flow_name):
            """Inspect processors inside an error handler."""

            if isinstance(handler, list):
                for item in handler:
                    inspect_handler(item, flow_name)
                return

            if not isinstance(handler, dict):
                return

            processors = handler.get("processors", [])

            if isinstance(processors, list):
                for processor in processors:
                    inspect_processor(processor, flow_name)

        flows = flow_analysis.get("flows", [])

        if not isinstance(flows, list):
            flows = []

        for flow in flows:
            if not isinstance(flow, dict):
                continue

            flow_name = flow.get("name", "unknown")

            execution_steps = flow.get("execution_steps", [])

            if isinstance(execution_steps, list):
                for processor in execution_steps:
                    inspect_processor(processor, flow_name)

            # Also inspect flow-level error handlers.
            error_handling = flow.get("error_handling", [])

            if isinstance(error_handling, list):
                for handler in error_handling:
                    inspect_handler(handler, flow_name)

        connector_summary = []

        for connector_name, count in connector_counts.items():
            operations = [
                operation
                for operation in connector_operations
                if operation["connector"] == connector_name
            ]

            connector_summary.append({
                "connector": connector_name,
                "usage_count": count,
                "operations": operations,
            })

        warnings = []

        for reference in config_references:
            if reference["status"] != "Found":
                warnings.append(
                    f"Configuration '{reference['config_ref']}' "
                    f"referenced by {reference['component']} in "
                    f"flow '{reference['flow']}' was not found "
                    f"in the extracted global configurations."
                )

        return {
            "application": flow_analysis.get("application"),
            "flow_count": flow_analysis.get("flow_count", 0),
            "subflow_count": flow_analysis.get("subflow_count", 0),
            "total_connector_operations": len(connector_operations),
            "connector_type_count": len(connector_counts),
            "connector_summary": connector_summary,
            "operation_counts": dict(operation_counts),
            "configuration_references": config_references,
            "warnings": warnings,
        }

    def get_report(self, analysis):
        """Generate a readable connector analysis report."""

        lines = [
            "MADA CONNECTOR ANALYSIS REPORT",
            "=" * 45,
            f"Application: {analysis.get('application')}",
            f"Flows: {analysis.get('flow_count')}",
            f"Subflows: {analysis.get('subflow_count')}",
            f"Connector types: {analysis.get('connector_type_count')}",
            (
                "Total connector operations: "
                f"{analysis.get('total_connector_operations')}"
            ),
            "",
            "CONNECTOR USAGE",
            "-" * 45,
        ]

        for connector in analysis.get("connector_summary", []):
            lines.append(
                f"\n{connector['connector']} "
                f"({connector['usage_count']} operation(s))"
            )

            for operation in connector.get("operations", []):
                lines.append(f"  - Flow: {operation['flow']}")
                lines.append(
                    f"    Operation: {operation['component']}"
                )
                lines.append(
                    f"    Explanation: {operation['explanation']}"
                )

                if operation.get("config_ref"):
                    lines.append(
                        f"    Config: {operation['config_ref']}"
                    )
                    lines.append(
                        f"    Config status: {operation['config_status']}"
                    )

        lines.extend([
            "",
            "OPERATION COUNTS",
            "-" * 45,
        ])

        for operation, count in analysis.get(
            "operation_counts", {}
        ).items():
            lines.append(f"{operation}: {count}")

        lines.extend([
            "",
            "CONFIGURATION REFERENCES",
            "-" * 45,
        ])

        references = analysis.get("configuration_references", [])

        if references:
            for reference in references:
                lines.append(
                    f"{reference['config_ref']} -> "
                    f"{reference['status']} "
                    f"(flow: {reference['flow']})"
                )
        else:
            lines.append("No connector configuration references found.")

        lines.extend([
            "",
            "WARNINGS",
            "-" * 45,
        ])

        warnings = analysis.get("warnings", [])

        if warnings:
            for warning in warnings:
                lines.append(f"- {warning}")
        else:
            lines.append("No configuration reference warnings.")

        lines.extend([
            "",
            "Note: This is static XML analysis. "
            "It does not test live connector connectivity.",
        ])

        return "\n".join(lines)


if __name__ == "__main__":
    import json
    import sys

    xml_file = sys.argv[1] if len(sys.argv) > 1 else "sample-mule.xml"

    analyzer = ConnectorAnalyzer()

    print("Starting MADA Connector Analyzer...")

    result = analyzer.analyze_file(xml_file)

    print("\nStructured Connector Analysis:\n")
    print(json.dumps(result, indent=4, ensure_ascii=False))

    print("\n")
    print(analyzer.get_report(result))
