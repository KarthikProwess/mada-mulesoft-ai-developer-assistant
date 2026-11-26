
import json
import xml.etree.ElementTree as ET
from pathlib import Path


class MuleXMLParser:
    """
    Read-only MuleSoft XML parser.

    Extracts:
    - Flows and subflows
    - Processors and their execution order
    - Connector information
    - Flow references
    - Error handlers
    - Global configurations
    """

    SENSITIVE_ATTRIBUTES = (
        "password",
        "secret",
        "token",
        "api-key",
        "apikey",
        "client-secret",
        "access-key",
        "private-key"
    )

    CONNECTOR_NAMES = {
        "http": "HTTP",
        "db": "Database",
        "sftp": "SFTP",
        "ftp": "FTP",
        "file": "File",
        "salesforce": "Salesforce",
        "jms": "JMS",
        "vm": "VM",
        "email": "Email",
        "smtp": "SMTP",
        "soap": "SOAP",
        "objectstore": "Object Store",
        "kafka": "Kafka",
        "apikit": "APIkit"
    }

    def __init__(self):
        self.result = {}

    # =====================================================
    # XML HELPERS
    # =====================================================

    @staticmethod
    def local_name(tag):
        """Remove XML namespace from an element name."""

        if "}" in tag:
            return tag.split("}", 1)[1]

        return tag

    @staticmethod
    def namespace(tag):
        """Extract XML namespace URI."""

        if tag.startswith("{") and "}" in tag:
            return tag[1:].split("}", 1)[0]

        return ""

    # =====================================================
    # ATTRIBUTE EXTRACTION AND SECRET MASKING
    # =====================================================

    def safe_attributes(self, element):

        attributes = {}

        for key, value in element.attrib.items():

            attribute_name = self.local_name(key)

            normalized = (
                attribute_name.lower().replace("_", "-")
            )

            if any(
                secret in normalized
                for secret in self.SENSITIVE_ATTRIBUTES
            ):
                value = "***REDACTED***"

            attributes[attribute_name] = value

        return attributes

    # =====================================================
    # CONNECTOR IDENTIFICATION
    # =====================================================

    def identify_connector(self, element):

        tag = self.local_name(element.tag).lower()

        namespace = self.namespace(element.tag).lower()

        # Extract the final namespace component.
        # Example:
        # http://www.mulesoft.org/schema/mule/http
        # becomes http

        connector_namespace = (
            namespace.rstrip("/").split("/")[-1]
        )

        connector_id = connector_namespace.split(":")[-1]

        if connector_id in self.CONNECTOR_NAMES:

            return self.CONNECTOR_NAMES[connector_id]

        # Fallback for connector operations.

        if tag in ("request", "listener"):

            return "HTTP"

        if tag in (
            "select",
            "insert",
            "update",
            "delete",
            "bulk-insert"
        ):

            return "Database"

        return None

    # =====================================================
    # PROCESSOR CLASSIFICATION
    # =====================================================

    def classify_processor(self, tag, connector):

        if tag == "flow-ref":
            return "FLOW_REFERENCE"

        if tag in (
            "listener",
            "scheduler",
            "on-new-message"
        ):
            return "SOURCE"

        if tag in (
            "choice",
            "first-successful",
            "round-robin",
            "scatter-gather"
        ):
            return "ROUTER"

        if tag in (
            "error-handler",
            "on-error-continue",
            "on-error-propagate"
        ):
            return "ERROR_HANDLING"

        if tag in (
            "transform",
            "set-payload",
            "set-variable",
            "remove-variable",
            "set-variables"
        ):
            return "TRANSFORMATION"

        if tag in (
            "logger",
            "raise-error",
            "async",
            "foreach",
            "parallel-foreach",
            "until-successful",
            "batch-job"
        ):
            return "PROCESSOR"

        if connector:
            return "CONNECTOR"

        return "COMPONENT"

    # =====================================================
    # PROCESSOR EXTRACTION
    # =====================================================

    def extract_processor(self, element):

        tag = self.local_name(element.tag)

        namespace = self.namespace(element.tag)

        connector = self.identify_connector(element)

        processor = {
            "component": tag,
            "namespace": namespace,
            "attributes": self.safe_attributes(element),
            "connector": connector,
            "type": self.classify_processor(tag, connector),
            "children": []
        }

        # Extract flow reference target.

        if tag == "flow-ref":

            processor["referenced_flow"] = (
                element.attrib.get("name")
            )

        # Extract nested components.

        for child in list(element):

            child_name = self.local_name(child.tag)

            # Ignore documentation and metadata.

            if child_name in (
                "annotations",
                "metadata",
                "documentation",
                "abstract-message-processor"
            ):
                continue

            if child_name == "error-handler":

                processor["children"].append(
                    self.extract_error_handler(child)
                )

            else:

                processor["children"].append(
                    self.extract_processor(child)
                )

        return processor

    # =====================================================
    # ERROR HANDLER EXTRACTION
    # =====================================================

    def extract_error_handler(self, element):

        handler = {
            "type": "ERROR_HANDLER",
            "component": "error-handler",
            "handlers": []
        }

        for child in list(element):

            child_name = self.local_name(child.tag)

            if child_name in (
                "on-error-continue",
                "on-error-propagate"
            ):

                handler["handlers"].append({

                    "type": child_name.upper().replace("-", "_"),

                    "attributes": self.safe_attributes(child),

                    "processors": [
                        self.extract_processor(processor)
                        for processor in list(child)
                    ]
                })

        return handler

    # =====================================================
    # FLOW REFERENCE COLLECTION
    # =====================================================

    def collect_flow_references(self, processor, references):

        if processor.get("type") == "FLOW_REFERENCE":

            reference = processor.get("referenced_flow")

            if reference:
                references.append(reference)

        for child in processor.get("children", []):

            if child.get("component") == "error-handler":

                for handler in child.get("handlers", []):

                    for nested in handler.get("processors", []):

                        self.collect_flow_references(
                            nested,
                            references
                        )

            else:

                self.collect_flow_references(
                    child,
                    references
                )

    # =====================================================
    # FLOW EXTRACTION
    # =====================================================

    def extract_flow(self, element):

        flow_name = element.attrib.get(
            "name",
            "Unnamed"
        )

        flow_type = self.local_name(element.tag)

        flow = {
            "name": flow_name,
            "type": flow_type,
            "attributes": self.safe_attributes(element),
            "processors": [],
            "error_handlers": [],
            "flow_references": []
        }

        for child in list(element):

            child_name = self.local_name(child.tag)

            if child_name == "error-handler":

                flow["error_handlers"].append(
                    self.extract_error_handler(child)
                )

            elif child_name in (
                "annotations",
                "metadata",
                "documentation"
            ):

                continue

            else:

                processor = self.extract_processor(child)

                flow["processors"].append(processor)

                self.collect_flow_references(
                    processor,
                    flow["flow_references"]
                )

        return flow

    # =====================================================
    # GLOBAL CONFIGURATION EXTRACTION
    # =====================================================

    def extract_global_configuration(self, element):

        return {
            "component": self.local_name(element.tag),
            "namespace": self.namespace(element.tag),
            "attributes": self.safe_attributes(element)
        }

    # =====================================================
    # MAIN XML PARSER
    # =====================================================

    def parse_string(self, xml_content, source="<memory>"):

        try:

            root = ET.fromstring(xml_content)

        except ET.ParseError as error:

            raise ValueError(
                f"Invalid Mule XML in {source}: {error}"
            ) from error

        flows = []
        subflows = []
        global_configurations = []

        for element in list(root):

            tag = self.local_name(element.tag)

            if tag == "flow":

                flows.append(
                    self.extract_flow(element)
                )

            elif tag == "sub-flow":

                subflows.append(
                    self.extract_flow(element)
                )

            elif tag.endswith("-config") or tag in (
                "configuration",
                "global-property"
            ):

                global_configurations.append(
                    self.extract_global_configuration(element)
                )

        self.result = {

            "source": source,

            "application": Path(source).name,

            "flow_count": len(flows),

            "subflow_count": len(subflows),

            "flows": flows,

            "subflows": subflows,

            "global_configurations": global_configurations
        }

        return self.result

    # =====================================================
    # PARSE XML FILE
    # =====================================================

    def parse_file(self, file_path):

        path = Path(file_path)

        if not path.exists():

            raise FileNotFoundError(
                f"Mule XML file not found: {path}"
            )

        if path.suffix.lower() != ".xml":

            raise ValueError(
                "Only XML files can be parsed."
            )

        if path.stat().st_size > 2 * 1024 * 1024:

            raise ValueError(
                "XML file exceeds the 2 MB parser limit."
            )

        xml_content = path.read_text(
            encoding="utf-8-sig"
        )

        return self.parse_string(
            xml_content,
            str(path)
        )

    # =====================================================
    # SUMMARY GENERATION
    # =====================================================

    def get_summary(self):

        if not self.result:

            return "No Mule XML has been parsed."

        lines = []

        lines.append(
            "Application: " + self.result["application"]
        )

        lines.append(
            "Flows: " + str(self.result["flow_count"])
        )

        lines.append(
            "Subflows: " + str(self.result["subflow_count"])
        )

        for flow in (
            self.result["flows"] + self.result["subflows"]
        ):

            lines.append("")

            lines.append(
                flow["type"] + ": " + flow["name"]
            )

            for processor in flow["processors"]:

                connector = processor.get("connector")

                component_line = (
                    "  - " + processor["component"]
                )

                if connector:

                    component_line += (
                        " [" + connector + "]"
                    )

                lines.append(component_line)

        return "\n".join(lines)

    # =====================================================
    # JSON OUTPUT
    # =====================================================

    def to_json(self):

        return json.dumps(
            self.result,
            indent=4,
            ensure_ascii=False
        )


# =========================================================
# COMMAND LINE TEST
# =========================================================

if __name__ == "__main__":

    import sys

    if len(sys.argv) < 2:

        print(
            "Usage: python -m app.agents.mule_xml_parser "
            "<path-to-mule-xml>"
        )

        sys.exit(1)

    parser = MuleXMLParser()

    try:

        parser.parse_file(sys.argv[1])

        print(parser.get_summary())

        print("\nDetailed JSON output:\n")

        print(parser.to_json())

    except Exception as error:

        print("Parser error:", error)

        sys.exit(1)
