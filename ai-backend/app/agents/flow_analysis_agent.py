
from app.agents.mule_xml_parser import MuleXMLParser


class FlowAnalysisAgent:
    """
    Analyzes parsed MuleSoft XML structures.

    Provides:
    - Flow execution sequence
    - Processor explanations
    - Connector identification
    - Subflow relationships
    - Error handling analysis
    - Human-readable flow reports
    """

    COMPONENT_EXPLANATIONS = {

        "listener": "Receives an incoming HTTP request.",

        "request": "Makes an outbound HTTP request.",

        "logger": "Writes a message to the application logs.",

        "flow-ref": "Calls another Mule flow or subflow.",

        "transform": "Transforms the Mule event using DataWeave.",

        "set-payload": "Sets or replaces the current payload.",

        "set-variable": "Creates or updates a Mule variable.",

        "remove-variable": "Removes a variable from the Mule event.",

        "select": "Executes a database SELECT query.",

        "insert": "Inserts records into a database.",

        "update": "Updates records in a database.",

        "delete": "Deletes records from a database.",

        "choice": "Routes execution based on conditions.",

        "scatter-gather": "Executes routes in parallel and combines their results.",

        "first-successful": "Executes routes until one succeeds.",

        "round-robin": "Distributes execution across configured routes.",

        "foreach": "Processes items in a collection sequentially.",

        "parallel-foreach": "Processes collection items concurrently.",

        "async": "Executes processing asynchronously.",

        "until-successful": "Retries processing until it succeeds or reaches its retry limit.",

        "raise-error": "Raises a Mule application error."
    }

    CONNECTOR_EXPLANATIONS = {

        "HTTP": "Uses the HTTP Connector for inbound or outbound HTTP communication.",

        "Database": "Uses the Database Connector to interact with a database.",

        "SFTP": "Uses SFTP to transfer files securely.",

        "FTP": "Uses FTP to transfer files.",

        "File": "Uses the File Connector to access local files.",

        "Salesforce": "Communicates with Salesforce.",

        "JMS": "Uses JMS messaging.",

        "VM": "Uses the VM Connector for internal messaging.",

        "Email": "Uses email integration.",

        "SOAP": "Communicates with SOAP services.",

        "Kafka": "Communicates with Apache Kafka."
    }

    def __init__(self):

        self.parser = MuleXMLParser()

        self.analysis = {}

    # =====================================================
    # PARSE PROJECT XML
    # =====================================================

    def analyze_file(self, file_path):

        parsed_data = self.parser.parse_file(file_path)

        return self.analyze_parsed_data(parsed_data)

    # =====================================================
    # ANALYZE PARSED DATA
    # =====================================================

    def analyze_parsed_data(self, parsed_data):

        flows = parsed_data.get("flows", [])

        subflows = parsed_data.get("subflows", [])

        all_flows = flows + subflows

        analyzed_flows = []

        for flow in all_flows:

            analyzed_flows.append(
                self.analyze_flow(flow, all_flows)
            )

        self.analysis = {

            "application": parsed_data.get("application"),

            "source": parsed_data.get("source"),

            "flow_count": len(flows),

            "subflow_count": len(subflows),

            "flows": analyzed_flows,

            "global_configurations": parsed_data.get(
                "global_configurations", []
            )

        }

        return self.analysis

    # =====================================================
    # ANALYZE INDIVIDUAL FLOW
    # =====================================================

    def analyze_flow(self, flow, all_flows):

        processors = flow.get("processors", [])

        steps = []

        for index, processor in enumerate(processors, start=1):

            steps.append(
                self.analyze_processor(processor, index)
            )

        references = flow.get("flow_references", [])

        referenced_flow_details = []

        for reference in references:

            matching_flow = next(
                (
                    item for item in all_flows
                    if item.get("name") == reference
                ),
                None
            )

            if matching_flow:

                referenced_flow_details.append({

                    "name": reference,

                    "type": matching_flow.get("type"),

                    "description": (
                        f"This flow calls {reference}, which is "
                        f"a {matching_flow.get('type')}."
                    )

                })

            else:

                referenced_flow_details.append({

                    "name": reference,

                    "type": "UNKNOWN",

                    "description": (
                        f"Referenced flow {reference} was not found "
                        "in the parsed XML."
                    )

                })

        error_analysis = self.analyze_error_handlers(
            flow.get("error_handlers", [])
        )

        return {

            "name": flow.get("name"),

            "type": flow.get("type"),

            "step_count": len(steps),

            "execution_steps": steps,

            "flow_references": referenced_flow_details,

            "error_handling": error_analysis,

            "execution_summary": self.create_execution_summary(
                flow.get("name"),
                steps,
                referenced_flow_details,
                error_analysis
            )

        }

    # =====================================================
    # ANALYZE PROCESSOR
    # =====================================================

    def analyze_processor(self, processor, index):

        component = processor.get("component", "unknown")

        processor_type = processor.get("type", "COMPONENT")

        connector = processor.get("connector")

        explanation = self.COMPONENT_EXPLANATIONS.get(
            component,
            f"Executes the Mule component '{component}'."
        )

        if connector:

            connector_explanation = (
                self.CONNECTOR_EXPLANATIONS.get(
                    connector,
                    f"Uses the {connector} connector."
                )
            )

            explanation += " " + connector_explanation

        if processor_type == "FLOW_REFERENCE":

            target = processor.get(
                "referenced_flow",
                "Unknown"
            )

            explanation += f" Target flow: {target}."

        children = []

        for child_index, child in enumerate(
            processor.get("children", []),
            start=1
        ):

            if child.get("component") == "error-handler":

                children.append(
                    self.analyze_error_handlers([child])
                )

            else:

                children.append(
                    self.analyze_processor(child, child_index)
                )

        return {

            "step": index,

            "component": component,

            "type": processor_type,

            "connector": connector,

            "attributes": processor.get("attributes", {}),

            "explanation": explanation,

            "children": children

        }

    # =====================================================
    # ERROR HANDLER ANALYSIS
    # =====================================================

    def analyze_error_handlers(self, error_handlers):

        results = []

        for error_handler in error_handlers:

            for handler in error_handler.get("handlers", []):

                handler_type = handler.get("type")

                if handler_type == "ON_ERROR_CONTINUE":

                    behavior = (
                        "Handles the error and continues the "
                        "flow execution according to the handler behavior."
                    )

                elif handler_type == "ON_ERROR_PROPAGATE":

                    behavior = (
                        "Handles the error and propagates it to the "
                        "calling flow or error-handling boundary."
                    )

                else:

                    behavior = "Unknown error-handling behavior."

                results.append({

                    "type": handler_type,

                    "attributes": handler.get("attributes", {}),

                    "behavior": behavior,

                    "processors": [

                        self.analyze_processor(processor, index)

                        for index, processor in enumerate(
                            handler.get("processors", []),
                            start=1
                        )

                    ]

                })

        return results

    # =====================================================
    # EXECUTION SUMMARY
    # =====================================================

    def create_execution_summary(
        self,
        flow_name,
        steps,
        references,
        error_handling
    ):

        lines = []

        lines.append(
            f"Flow '{flow_name}' execution analysis:"
        )

        for step in steps:

            lines.append(

                f"Step {step['step']}: "
                f"{step['component']} - "
                f"{step['explanation']}"

            )

        for reference in references:

            lines.append(
                f"Flow reference: {reference['description']}"
            )

        if error_handling:

            lines.append("Error handling:")

            for handler in error_handling:

                lines.append(

                    f"- {handler['type']}: "
                    f"{handler['behavior']}"

                )

        else:

            lines.append(
                "No flow-level error handler was extracted."
            )

        return "\n".join(lines)

    # =====================================================
    # HUMAN-READABLE REPORT
    # =====================================================

    def get_report(self):

        if not self.analysis:

            return "No flow analysis is available."

        lines = []

        lines.append("MADA FLOW ANALYSIS REPORT")

        lines.append("=" * 50)

        lines.append(
            "Application: "
            + str(self.analysis.get("application"))
        )

        lines.append(
            "Flows: "
            + str(self.analysis.get("flow_count"))
        )

        lines.append(
            "Subflows: "
            + str(self.analysis.get("subflow_count"))
        )

        for flow in self.analysis.get("flows", []):

            lines.append("")

            lines.append(
                flow["type"].upper()
                + ": "
                + flow["name"]
            )

            lines.append("-" * 40)

            lines.append(
                flow["execution_summary"]
            )

        return "\n".join(lines)
