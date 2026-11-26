
import json
import re
import sys
import xml.etree.ElementTree as ET

from pathlib import Path


class ErrorHandlingAnalyzer:
    """
    Performs static analysis of MuleSoft error-handling configurations.

    Detects:
    - Flow-level error handlers
    - Try-scope error handlers
    - on-error-continue
    - on-error-propagate
    - Error types and conditions
    - Processors inside error handlers
    - Redelivery policy configuration
    """

    MAX_FILE_SIZE = 2 * 1024 * 1024

    SCOPE_TAGS = {
        "flow",
        "sub-flow",
        "try",
    }

    ERROR_HANDLER_TAGS = {
        "on-error-continue",
        "on-error-propagate",
    }

    STRUCTURAL_TAGS = {
        "mule",
        "flows",
        "error-handler",
        "on-error-continue",
        "on-error-propagate",
        "try",
        "message",
        "error-mapping",
    }

    def local_name(self, tag):
        """Remove an XML namespace from an element name."""
        if not isinstance(tag, str):
            return ""

        if "}" in tag:
            return tag.split("}", 1)[1]

        if ":" in tag:
            return tag.split(":", 1)[1]

        return tag

    def safe_attributes(self, element):
        """Return attributes while avoiding sensitive values."""
        sensitive_words = (
            "password",
            "secret",
            "token",
            "api-key",
            "apikey",
            "access-key",
            "private-key",
        )

        result = {}

        for key, value in element.attrib.items():
            attribute_name = self.local_name(key)
            normalized = attribute_name.lower().replace("_", "-")

            if any(word in normalized for word in sensitive_words):
                result[attribute_name] = "[REDACTED]"
            else:
                result[attribute_name] = value

        return result

    def read_xml(self, file_path):
        """Read and parse a Mule XML file."""
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Mule XML file not found: {path}"
            )

        if path.stat().st_size > self.MAX_FILE_SIZE:
            raise ValueError(
                "Mule XML file exceeds the 2 MB size limit."
            )

        try:
            content = path.read_text(encoding="utf-8-sig")
            content = content.lstrip()

            return ET.fromstring(content)

        except ET.ParseError as error:
            raise ValueError(
                f"Invalid Mule XML: {error}"
            ) from error

        except UnicodeDecodeError as error:
            raise ValueError(
                f"Unable to decode Mule XML: {error}"
            ) from error

    def build_parent_map(self, root):
        """Build a child-to-parent mapping for scope detection."""
        return {
            child: parent
            for parent in root.iter()
            for child in parent
        }

    def find_nearest_scope(self, element, parent_map):
        """
        Find the nearest enclosing flow, sub-flow, or Try scope.
        """
        current = parent_map.get(element)

        while current is not None:
            tag = self.local_name(current.tag)

            if tag in self.SCOPE_TAGS:
                return current

            current = parent_map.get(current)

        return None

    def get_element_name(self, element):
        """Get a useful name for a Mule component."""
        attributes = self.safe_attributes(element)

        return (
            attributes.get("doc:name")
            or attributes.get("name")
            or self.local_name(element.tag)
        )

    def extract_processors(self, on_error_element):
        """Extract component names inside an error handler."""
        processors = []

        for element in on_error_element.iter():
            if element is on_error_element:
                continue

            tag = self.local_name(element.tag)

            if tag in self.STRUCTURAL_TAGS:
                continue

            if tag.startswith("set-") or tag in {
                "logger",
                "raise-error",
                "flow-ref",
                "transform",
                "async",
                "choice",
                "foreach",
                "parallel-foreach",
                "until-successful",
                "publish",
                "consume",
                "select",
                "insert",
                "update",
                "delete",
                "http-request",
            }:
                processors.append({
                    "component": tag,
                    "name": self.get_element_name(element),
                    "attributes": self.safe_attributes(element),
                })

        return processors

    def analyze_on_error(self, element):
        """Analyze an on-error-continue or on-error-propagate block."""
        tag = self.local_name(element.tag)
        attributes = self.safe_attributes(element)

        error_type = attributes.get("type")
        condition = attributes.get("when")

        processors = self.extract_processors(element)

        if tag == "on-error-continue":
            behavior = (
                "Handles the error and continues the flow "
                "without propagating the original error."
            )
        else:
            behavior = (
                "Handles the error and propagates the error "
                "to the calling flow or upstream error handler."
            )

        warnings = []

        if not error_type:
            warnings.append(
                "No explicit error type is configured. "
                "Review which errors this handler is intended to catch."
            )

        if not processors:
            warnings.append(
                "No recognizable processors were found inside this "
                "error handler. Review whether it performs the required "
                "logging, response handling, or recovery."
            )

        return {
            "type": tag,
            "behavior": behavior,
            "error_type": error_type or "Not explicitly specified",
            "condition": condition or None,
            "attributes": attributes,
            "processors": processors,
            "warnings": warnings,
        }

    def analyze_error_handler(self, element, parent_map):
        """Analyze one error-handler block and identify its scope."""
        scope = self.find_nearest_scope(element, parent_map)

        if scope is None:
            scope_type = "unknown"
            scope_name = "Unknown scope"
        else:
            scope_type = self.local_name(scope.tag)
            scope_name = (
                self.safe_attributes(scope).get("name")
                or self.get_element_name(scope)
            )

        handlers = []

        for child in list(element):
            child_tag = self.local_name(child.tag)

            if child_tag in self.ERROR_HANDLER_TAGS:
                handlers.append(
                    self.analyze_on_error(child)
                )

        return {
            "scope_type": scope_type,
            "scope_name": scope_name,
            "handlers": handlers,
            "handler_count": len(handlers),
            "attributes": self.safe_attributes(element),
        }

    def analyze_redelivery_policies(self, root):
        """Find configured redelivery-policy elements."""
        policies = []

        for element in root.iter():
            tag = self.local_name(element.tag)

            if "redelivery-policy" not in tag:
                continue

            policies.append({
                "component": tag,
                "attributes": self.safe_attributes(element),
            })

        return policies

    def analyze_flows(self, root):
        """Summarize flows and their error-handler presence."""
        flows = []

        for element in root.iter():
            tag = self.local_name(element.tag)

            if tag not in {"flow", "sub-flow"}:
                continue

            name = (
                self.safe_attributes(element).get("name")
                or "Unnamed flow"
            )

            error_handler_count = sum(
                1
                for child in element.iter()
                if self.local_name(child.tag) == "error-handler"
            )

            flows.append({
                "name": name,
                "type": tag,
                "error_handler_count": error_handler_count,
                "has_error_handler": error_handler_count > 0,
            })

        return flows

    def create_warnings(self, flows, error_handlers):
        """Create general static-analysis warnings."""
        warnings = []

        for flow in flows:
            # A sub-flow can inherit error handling from its caller.
            if flow["type"] == "sub-flow":
                continue

            if not flow["has_error_handler"]:
                warnings.append(
                    f"Flow '{flow['name']}' has no error-handler "
                    "element in its XML scope. Review whether "
                    "local or inherited error handling is appropriate."
                )

        for index, error_handler in enumerate(error_handlers, start=1):
            if error_handler["handler_count"] == 0:
                warnings.append(
                    f"Error handler #{index} contains no recognizable "
                    "on-error-continue or on-error-propagate blocks."
                )

            for handler in error_handler["handlers"]:
                for warning in handler["warnings"]:
                    warnings.append(
                        f"{error_handler['scope_name']}: {warning}"
                    )

        return warnings

    def analyze_string(self, xml_content, application_name="Mule application"):
        """Analyze Mule XML content supplied as a string."""
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as error:
            raise ValueError(
                f"Invalid Mule XML: {error}"
            ) from error

        parent_map = self.build_parent_map(root)

        error_handlers = []

        for element in root.iter():
            if self.local_name(element.tag) == "error-handler":
                error_handlers.append(
                    self.analyze_error_handler(
                        element,
                        parent_map
                    )
                )

        flows = self.analyze_flows(root)
        redelivery_policies = self.analyze_redelivery_policies(root)

        all_on_error_handlers = [
            handler
            for error_handler in error_handlers
            for handler in error_handler["handlers"]
        ]

        continue_count = sum(
            1
            for handler in all_on_error_handlers
            if handler["type"] == "on-error-continue"
        )

        propagate_count = sum(
            1
            for handler in all_on_error_handlers
            if handler["type"] == "on-error-propagate"
        )

        warnings = self.create_warnings(
            flows,
            error_handlers
        )

        return {
            "application": application_name,
            "summary": {
                "flow_count": len(flows),
                "error_handler_count": len(error_handlers),
                "on_error_continue_count": continue_count,
                "on_error_propagate_count": propagate_count,
                "redelivery_policy_count": len(redelivery_policies),
            },
            "flows": flows,
            "error_handlers": error_handlers,
            "redelivery_policies": redelivery_policies,
            "warnings": warnings,
        }

    def analyze_file(self, file_path):
        """Analyze a Mule XML file."""
        path = Path(file_path)
        root = self.read_xml(path)

        xml_content = ET.tostring(
            root,
            encoding="unicode"
        )

        return self.analyze_string(
            xml_content,
            application_name=path.name
        )

    def get_report(self, result):
        """Generate a readable text report."""
        lines = [
            "",
            "MADA ERROR HANDLING ANALYSIS REPORT",
            "=" * 48,
            f"Application: {result['application']}",
            "",
            "SUMMARY",
            "-" * 48,
        ]

        summary = result["summary"]

        lines.extend([
            f"Flows/Sub-flows: {summary['flow_count']}",
            f"Error handlers: {summary['error_handler_count']}",
            f"On Error Continue: {summary['on_error_continue_count']}",
            f"On Error Propagate: {summary['on_error_propagate_count']}",
            f"Redelivery policies: {summary['redelivery_policy_count']}",
        ])

        lines.extend([
            "",
            "FLOW DETAILS",
            "-" * 48,
        ])

        for flow in result["flows"]:
            status = (
                "Error handler present"
                if flow["has_error_handler"]
                else "No local error handler detected"
            )

            lines.append(
                f"- {flow['type']}: {flow['name']} - {status}"
            )

        lines.extend([
            "",
            "ERROR HANDLER DETAILS",
            "-" * 48,
        ])

        if not result["error_handlers"]:
            lines.append("No error-handler elements found.")

        for index, error_handler in enumerate(
            result["error_handlers"],
            start=1
        ):
            lines.append(
                f"\nError Handler #{index}"
            )
            lines.append(
                f"Scope: {error_handler['scope_type']} "
                f"({error_handler['scope_name']})"
            )

            if not error_handler["handlers"]:
                lines.append("  No on-error blocks found.")

            for handler in error_handler["handlers"]:
                lines.append(
                    f"  - {handler['type']}"
                )
                lines.append(
                    f"    Error type: {handler['error_type']}"
                )
                lines.append(
                    f"    Condition: {handler['condition'] or 'None'}"
                )
                lines.append(
                    f"    Behavior: {handler['behavior']}"
                )

                if handler["processors"]:
                    lines.append("    Processors:")

                    for processor in handler["processors"]:
                        lines.append(
                            f"      - {processor['component']}: "
                            f"{processor['name']}"
                        )
                else:
                    lines.append(
                        "    Processors: None recognized"
                    )

                for warning in handler["warnings"]:
                    lines.append(
                        f"    Warning: {warning}"
                    )

        lines.extend([
            "",
            "REDELIVERY POLICIES",
            "-" * 48,
        ])

        if not result["redelivery_policies"]:
            lines.append("No redelivery-policy elements detected.")
        else:
            for policy in result["redelivery_policies"]:
                lines.append(
                    f"- {policy['component']}: {policy['attributes']}"
                )

        lines.extend([
            "",
            "WARNINGS AND RECOMMENDATIONS",
            "-" * 48,
        ])

        if result["warnings"]:
            for warning in result["warnings"]:
                lines.append(f"- {warning}")
        else:
            lines.append("No basic static-analysis warnings.")

        lines.extend([
            "",
            "Note: Static XML analysis only. "
            "This analyzer does not execute Mule flows or prove "
            "runtime error-handling behavior.",
        ])

        return "\n".join(lines)


def main():
    print("Starting MADA Error Handling Analyzer...")

    if len(sys.argv) < 2:
        print(
            "\nUsage:\n"
            "python -m app.agents.error_handling_analyzer "
            "sample-mule.xml"
        )
        return

    file_path = sys.argv[1]

    analyzer = ErrorHandlingAnalyzer()

    try:
        result = analyzer.analyze_file(file_path)

        print("\nStructured Error Handling Analysis:\n")
        print(
            json.dumps(
                result,
                indent=4
            )
        )

        print(analyzer.get_report(result))

    except Exception as error:
        print(f"\nAnalysis failed: {error}")
        raise


if __name__ == "__main__":
    main()
