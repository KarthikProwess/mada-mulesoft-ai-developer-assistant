
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path


class DataWeaveAnalyzer:
    """
    Performs static analysis of DataWeave scripts and expressions
    embedded in Mule XML files.

    It does not execute DataWeave or validate scripts using
    the MuleSoft DataWeave compiler.
    """

    DATAWEAVE_OPERATIONS = {
        "map": "Transforms each item in an array.",
        "filter": "Selects items that match a condition.",
        "flatMap": "Maps items and flattens the resulting arrays.",
        "reduce": "Combines array items into a single result.",
        "groupBy": "Groups items based on a grouping expression.",
        "pluck": "Transforms object key-value pairs into an array.",
        "distinctBy": "Removes duplicate items based on a key.",
        "orderBy": "Sorts items based on an expression.",
        "sizeOf": "Returns the size of a value.",
        "isEmpty": "Checks whether a value is empty.",
        "default": "Provides a fallback value when the left value is absent.",
        "read": "Reads content using a specified MIME type.",
        "write": "Serializes a value into a specified MIME type.",
        "now": "Returns the current date and time.",
        "uuid": "Generates a UUID.",
        "upper": "Converts text to uppercase.",
        "lower": "Converts text to lowercase.",
        "substring": "Extracts part of a string.",
        "splitBy": "Splits a string using a separator.",
        "joinBy": "Joins array items using a separator.",
        "++": "Combines arrays, strings, or objects depending on their types.",
    }

    COMPONENT_NAMES = {
        "transform": "Transform Message",
        "set-payload": "Set Payload",
        "set-variable": "Set Variable",
        "set-variables": "Set Variables",
    }

    def local_name(self, tag):
        """Remove an XML namespace from an element name."""
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag


    def read_xml(self, file_path):
        """Read and parse a Mule XML file safely."""
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"XML file not found: {file_path}")

        if path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("XML file exceeds the 2 MB analysis limit.")

        try:
            # utf-8-sig removes a UTF-8 BOM if present.
            content = path.read_text(encoding="utf-8-sig")

            # Remove leading whitespace before the XML declaration.
            content = content.lstrip()

            return ET.fromstring(content)

        except ET.ParseError as error:
            raise ValueError(f"Invalid XML: {error}") from error
        except UnicodeDecodeError as error:
            raise ValueError(f"Unable to decode XML file: {error}") from error


    def extract_dataweave_blocks(self, root):
        """
        Extract DataWeave scripts and inline expressions from
        XML element text and attributes.
        """
        blocks = []

        for element in root.iter():
            component = self.local_name(element.tag)
            attributes = element.attrib

            # Inspect direct element text. CDATA content is exposed
            # as ordinary text by ElementTree.
            text_content = (element.text or "").strip()

            if self.contains_dataweave(text_content):
                blocks.append({
                    "component": component,
                    "component_name": self.COMPONENT_NAMES.get(
                        component, component
                    ),
                    "location": "element-text",
                    "content": text_content,
                })

            # Inspect attributes for inline Mule expressions.
            for attribute_name, attribute_value in attributes.items():
                value = (attribute_value or "").strip()

                if self.contains_dataweave(value):
                    blocks.append({
                        "component": component,
                        "component_name": self.COMPONENT_NAMES.get(
                            component, component
                        ),
                        "location": f"attribute:{attribute_name}",
                        "content": value,
                    })

        return blocks

    def contains_dataweave(self, text):
        if not text:
            return False

        return (
            "%dw" in text
            or "#[" in text
        )

    def analyze_script(self, block, index):
        """Analyze one extracted script or inline expression."""

        script = block["content"]

        version_match = re.search(
            r"%dw\s+([\d.]+)",
            script
        )

        output_match = re.search(
            r"\boutput\s+([A-Za-z0-9_/\-+]+)",
            script
        )

        input_match = re.search(
            r"\binput\s+([A-Za-z0-9_]+)",
            script
        )

        variables = re.findall(
            r"\bvar\s+([A-Za-z_][A-Za-z0-9_]*)\s*=",
            script
        )

        functions = re.findall(
            r"\bfun\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
            script
        )

        operations = []

        for operation, explanation in self.DATAWEAVE_OPERATIONS.items():
            if operation == "++":
                found = "++" in script
            else:
                found = re.search(
                    rf"\b{re.escape(operation)}\s*\(",
                    script
                ) is not None

            if found:
                operations.append({
                    "name": operation,
                    "explanation": explanation,
                })

        references = {
            "payload": bool(re.search(r"\bpayload\b", script)),
            "attributes": bool(re.search(r"\battributes\b", script)),
            "vars": sorted(set(
                re.findall(r"\bvars\.([A-Za-z_][A-Za-z0-9_]*)", script)
            )),
        }

        warnings = []

        is_full_script = version_match is not None

        if is_full_script and not output_match:
            warnings.append(
                "No output directive was detected in this DataWeave script."
            )

        return {
            "script_number": index,
            "component": block["component"],
            "component_name": block["component_name"],
            "location": block["location"],
            "dataweave_version": (
                version_match.group(1) if version_match else None
            ),
            "input_directive": (
                input_match.group(1) if input_match else None
            ),
            "output_directive": (
                output_match.group(1) if output_match else None
            ),
            "declared_variables": sorted(set(variables)),
            "declared_functions": sorted(set(functions)),
            "operations": operations,
            "references": references,
            "is_full_script": is_full_script,
            "warnings": warnings,
            "script_preview": script[:500],
        }

    def analyze_file(self, file_path):
        """Analyze all DataWeave blocks in a Mule XML file."""

        root = self.read_xml(file_path)
        blocks = self.extract_dataweave_blocks(root)

        analyses = []

        for index, block in enumerate(blocks, start=1):
            analyses.append(
                self.analyze_script(block, index)
            )

        all_operations = sorted({
            operation["name"]
            for analysis in analyses
            for operation in analysis["operations"]
        })

        all_variables = sorted({
            variable
            for analysis in analyses
            for variable in analysis["declared_variables"]
        })

        all_functions = sorted({
            function
            for analysis in analyses
            for function in analysis["declared_functions"]
        })

        warnings = []

        for analysis in analyses:
            for warning in analysis["warnings"]:
                warnings.append(
                    f"Script {analysis['script_number']}: {warning}"
                )

        if not analyses:
            warnings.append(
                "No DataWeave scripts or inline expressions were detected."
            )

        return {
            "application": Path(file_path).name,
            "dataweave_block_count": len(analyses),
            "dataweave_operations": all_operations,
            "declared_variables": all_variables,
            "declared_functions": all_functions,
            "scripts": analyses,
            "warnings": warnings,
        }

    def get_report(self, analysis):
        """Generate a readable DataWeave analysis report."""

        lines = [
            "MADA DATAWEAVE ANALYSIS REPORT",
            "=" * 45,
            f"Application: {analysis['application']}",
            f"DataWeave blocks: {analysis['dataweave_block_count']}",
            "",
            "DETECTED OPERATIONS",
            "-" * 45,
        ]

        operations = analysis["dataweave_operations"]

        if operations:
            for operation in operations:
                explanation = self.DATAWEAVE_OPERATIONS.get(
                    operation, "DataWeave operation."
                )
                lines.append(f"- {operation}: {explanation}")
        else:
            lines.append("No known DataWeave operations detected.")

        lines.extend([
            "",
            "SCRIPT DETAILS",
            "-" * 45,
        ])

        for script in analysis["scripts"]:
            lines.append(
                f"\nScript {script['script_number']}: "
                f"{script['component_name']}"
            )
            lines.append(f"Location: {script['location']}")
            lines.append(
                f"DataWeave version: "
                f"{script['dataweave_version'] or 'Not detected'}"
            )
            lines.append(
                f"Input: {script['input_directive'] or 'Not specified'}"
            )
            lines.append(
                f"Output: {script['output_directive'] or 'Not specified'}"
            )
            lines.append(
                f"Variables: "
                f"{', '.join(script['declared_variables']) or 'None'}"
            )
            lines.append(
                f"Functions: "
                f"{', '.join(script['declared_functions']) or 'None'}"
            )

            references = script["references"]

            lines.append(
                f"Uses payload: {'Yes' if references['payload'] else 'No'}"
            )
            lines.append(
                f"Uses attributes: "
                f"{'Yes' if references['attributes'] else 'No'}"
            )
            lines.append(
                f"Variables referenced: "
                f"{', '.join(references['vars']) or 'None'}"
            )

            if script["warnings"]:
                for warning in script["warnings"]:
                    lines.append(f"Warning: {warning}")

        lines.extend([
            "",
            "WARNINGS",
            "-" * 45,
        ])

        if analysis["warnings"]:
            for warning in analysis["warnings"]:
                lines.append(f"- {warning}")
        else:
            lines.append("No basic static-analysis warnings.")

        lines.extend([
            "",
            "Note: Static analysis only. "
            "This does not compile or execute DataWeave scripts.",
        ])

        return "\n".join(lines)


if __name__ == "__main__":
    import sys

    xml_file = (
        sys.argv[1] if len(sys.argv) > 1
        else "sample-mule.xml"
    )

    analyzer = DataWeaveAnalyzer()

    print("Starting MADA DataWeave Analyzer...")

    result = analyzer.analyze_file(xml_file)

    print("\nStructured DataWeave Analysis:\n")
    print(json.dumps(result, indent=4, ensure_ascii=False))

    print("\n")
    print(analyzer.get_report(result))
