from collections import Counter


class IssueDetectionAgent:
    """
    Detects potential MuleSoft project issues using evidence
    extracted by MADA's static analyzers.

    Supports:
    - Individual XML file issue detection.
    - Project-wide connector configuration validation.
    - Project-wide flow and subflow reference validation.

    This agent does not execute Mule applications or modify files.
    """

    REFERENCE_RULES = {
        "MADA-CONN-001",
        "MADA-FLOW-001",
    }

    SEVERITIES = (
        "critical",
        "high",
        "medium",
        "low",
        "info",
    )

    def _create_finding(
        self,
        rule_id,
        category,
        severity,
        title,
        file_name,
        flow,
        processor,
        evidence,
        recommendation,
        confidence="medium",
        counter=1,
    ):
        return {
            "id": f"{rule_id}-{counter:03d}",
            "rule_id": rule_id,
            "category": category,
            "severity": severity,
            "confidence": confidence,
            "title": title,
            "file": file_name,
            "flow": flow,
            "processor": processor,
            "evidence": evidence,
            "recommendation": recommendation,
        }

    def _refresh_summary(self, issue_analysis):
        """Recalculate finding counts after project validation."""

        findings = issue_analysis.get("findings", [])

        severity_counts = Counter(
            finding.get("severity", "info")
            for finding in findings
        )

        category_counts = Counter(
            finding.get("category", "unknown")
            for finding in findings
        )

        issue_analysis["issue_count"] = len(findings)

        issue_analysis["severity_summary"] = {
            severity: severity_counts.get(severity, 0)
            for severity in self.SEVERITIES
        }

        issue_analysis["category_summary"] = dict(
            category_counts
        )

        return issue_analysis

    def detect_file_issues(self, file_result):
        """Detect issues in one file's unified analysis result."""

        if not isinstance(file_result, dict):
            raise ValueError(
                "Expected a file analysis dictionary."
            )

        file_name = file_result.get("file", "Unknown")
        analyses = file_result.get("analyses", {})

        if not isinstance(analyses, dict):
            analyses = {}

        findings = []
        rule_counters = Counter()

        def add_finding(
            rule_id,
            category,
            severity,
            title,
            flow,
            processor,
            evidence,
            recommendation,
            confidence="medium",
        ):
            rule_counters[rule_id] += 1

            findings.append(
                self._create_finding(
                    rule_id=rule_id,
                    category=category,
                    severity=severity,
                    title=title,
                    file_name=file_name,
                    flow=flow,
                    processor=processor,
                    evidence=evidence,
                    recommendation=recommendation,
                    confidence=confidence,
                    counter=rule_counters[rule_id],
                )
            )

        # -------------------------------------------------
        # RULE 1: XML parsing failure
        # -------------------------------------------------

        for error in file_result.get("errors", []):
            if not isinstance(error, dict):
                continue

            if error.get("analyzer") == "xml_structure":
                add_finding(
                    rule_id="MADA-XML-001",
                    category="xml",
                    severity="high",
                    title="Mule XML parsing failed",
                    flow=None,
                    processor=None,
                    evidence={
                        "error": error.get("error"),
                        "source": "MuleXMLParser",
                    },
                    recommendation=(
                        "Check XML syntax, namespace declarations, "
                        "closing tags and element structure. "
                        "Validate the XML before analyzing it again."
                    ),
                    confidence="high",
                )

        # -------------------------------------------------
        # RULE 2: Potential unresolved connector config-ref
        # -------------------------------------------------

        connector_analysis = analyses.get(
            "connector_analysis", {}
        )

        if isinstance(connector_analysis, dict):
            references = connector_analysis.get(
                "configuration_references", []
            )

            if isinstance(references, list):
                for reference in references:
                    if not isinstance(reference, dict):
                        continue

                    if reference.get("status") != (
                        "Not found in extracted configurations"
                    ):
                        continue

                    config_ref = reference.get("config_ref")

                    add_finding(
                        rule_id="MADA-CONN-001",
                        category="connector",
                        severity="medium",
                        title=(
                            "Connector configuration reference "
                            "was not found in this XML file"
                        ),
                        flow=reference.get("flow"),
                        processor=reference.get("component"),
                        evidence={
                            "connector": reference.get("connector"),
                            "config_ref": config_ref,
                            "configuration_status": reference.get(
                                "status"
                            ),
                        },
                        recommendation=(
                            f"Verify that configuration '{config_ref}' "
                            "exists. It may be defined in another "
                            "Mule XML file."
                        ),
                        confidence="medium",
                    )

        # -------------------------------------------------
        # RULE 3: Potential unresolved flow reference
        # -------------------------------------------------

        flow_analysis = analyses.get("flow_analysis", {})

        if isinstance(flow_analysis, dict):
            flows = flow_analysis.get("flows", [])

            if isinstance(flows, list):
                for flow in flows:
                    if not isinstance(flow, dict):
                        continue

                    flow_name = flow.get("name", "Unknown")

                    references = flow.get(
                        "flow_references", []
                    )

                    if not isinstance(references, list):
                        continue

                    for reference in references:
                        if not isinstance(reference, dict):
                            continue

                        if reference.get("type") != "UNKNOWN":
                            continue

                        target = reference.get(
                            "name", "Unknown"
                        )

                        add_finding(
                            rule_id="MADA-FLOW-001",
                            category="flow",
                            severity="medium",
                            title=(
                                "Potential unresolved flow reference"
                            ),
                            flow=flow_name,
                            processor="flow-ref",
                            evidence={
                                "referenced_flow": target,
                                "reference_status": "UNKNOWN",
                                "description": reference.get(
                                    "description"
                                ),
                            },
                            recommendation=(
                                f"Verify that flow or subflow "
                                f"'{target}' exists in the Mule "
                                "application. It may be defined in "
                                "another XML file."
                            ),
                            confidence="medium",
                        )

        # -------------------------------------------------
        # RULE 4: Flow with no extracted execution steps
        # -------------------------------------------------

        if isinstance(flow_analysis, dict):
            flows = flow_analysis.get("flows", [])

            if isinstance(flows, list):
                for flow in flows:
                    if not isinstance(flow, dict):
                        continue

                    if flow.get("step_count") != 0:
                        continue

                    add_finding(
                        rule_id="MADA-FLOW-002",
                        category="flow",
                        severity="low",
                        title="Flow has no extracted execution steps",
                        flow=flow.get("name", "Unknown"),
                        processor=None,
                        evidence={
                            "flow_type": flow.get("type", "unknown"),
                            "step_count": flow.get("step_count"),
                        },
                        recommendation=(
                            "Review this flow to confirm that its "
                            "empty structure is intentional. Check "
                            "whether the expected source or processors "
                            "are present in the XML."
                        ),
                        confidence="medium",
                    )

        severity_counts = Counter(
            finding["severity"]
            for finding in findings
        )

        category_counts = Counter(
            finding["category"]
            for finding in findings
        )

        return {
            "file": file_name,
            "issue_count": len(findings),
            "severity_summary": {
                severity: severity_counts.get(severity, 0)
                for severity in self.SEVERITIES
            },
            "category_summary": dict(category_counts),
            "findings": findings,
            "note": (
                "Findings are based on static analyzer evidence. "
                "Potential issues must be verified against the "
                "complete MuleSoft project and runtime behavior."
            ),
        }

    # =====================================================
    # PROJECT-WIDE REGISTRY
    # =====================================================

    def build_project_registry(self, file_results):
        """
        Build configuration and flow registries using all
        successfully extracted XML analysis results.
        """

        configuration_registry = {}
        flow_registry = {}

        parsed_file_count = 0
        parse_failure_count = 0

        for file_result in file_results:

            if not isinstance(file_result, dict):
                continue

            analyses = file_result.get("analyses", {})

            if not isinstance(analyses, dict):
                continue

            xml_analysis = analyses.get(
                "xml_structure", {}
            )

            if not isinstance(xml_analysis, dict):
                continue

            parsed_file_count += 1

            file_name = file_result.get("file", "Unknown")

            # ---------------------------------------------
            # Collect global configurations
            # ---------------------------------------------

            configurations = xml_analysis.get(
                "global_configurations", []
            )

            if isinstance(configurations, list):

                for configuration in configurations:

                    if not isinstance(configuration, dict):
                        continue

                    attributes = configuration.get(
                        "attributes", {}
                    )

                    if not isinstance(attributes, dict):
                        continue

                    config_name = attributes.get("name")

                    if config_name:
                        configuration_registry.setdefault(
                            config_name, []
                        ).append(file_name)

            # ---------------------------------------------
            # Collect flows and subflows from XML parser
            # ---------------------------------------------

            for collection_name in ("flows", "subflows"):

                definitions = xml_analysis.get(
                    collection_name, []
                )

                if not isinstance(definitions, list):
                    continue

                for definition in definitions:

                    if not isinstance(definition, dict):
                        continue

                    flow_name = definition.get("name")

                    if flow_name:
                        flow_registry.setdefault(
                            flow_name, []
                        ).append({
                            "file": file_name,
                            "type": definition.get("type"),
                        })

        # Check whether any XML parser failed.
        for file_result in file_results:

            for error in file_result.get("errors", []):

                if (
                    isinstance(error, dict)
                    and error.get("analyzer") == "xml_structure"
                ):
                    parse_failure_count += 1

        return {
            "configurations": configuration_registry,
            "flows": flow_registry,
            "parsed_file_count": parsed_file_count,
            "parse_failure_count": parse_failure_count,
        }

    # =====================================================
    # PROJECT-WIDE REFERENCE VALIDATION
    # =====================================================

    def validate_project_references(self, file_results):
        """
        Re-evaluate connector and flow references using the
        complete project registry.

        Local unresolved-reference findings are removed and
        recreated only when the target is absent project-wide.
        """

        registry = self.build_project_registry(file_results)

        configurations = registry["configurations"]
        flows_registry = registry["flows"]

        config_counters = Counter()
        flow_counters = Counter()

        for file_result in file_results:

            issue_analysis = file_result.get("issue_analysis")

            if not isinstance(issue_analysis, dict):
                continue

            # Remove local-only reference findings.
            findings = [
                finding
                for finding in issue_analysis.get("findings", [])
                if finding.get("rule_id") not in self.REFERENCE_RULES
            ]

            file_name = file_result.get("file", "Unknown")
            analyses = file_result.get("analyses", {})

            # ---------------------------------------------
            # Validate connector config-ref values
            # ---------------------------------------------

            connector_analysis = analyses.get(
                "connector_analysis", {}
            )

            if isinstance(connector_analysis, dict):

                references = connector_analysis.get(
                    "configuration_references", []
                )

                if isinstance(references, list):

                    for reference in references:

                        if not isinstance(reference, dict):
                            continue

                        if reference.get("status") != (
                            "Not found in extracted configurations"
                        ):
                            continue

                        config_ref = reference.get("config_ref")

                        if not config_ref:
                            continue

                        if config_ref in configurations:
                            continue

                        config_counters[file_name] += 1

                        # If some XML files failed parsing,
                        # the registry may be incomplete.
                        confidence = (
                            "low"
                            if registry["parse_failure_count"] > 0
                            else "high"
                        )

                        findings.append(
                            self._create_finding(
                                rule_id="MADA-CONN-001",
                                category="connector",
                                severity="medium",
                                title=(
                                    "Connector configuration "
                                    "reference was not found "
                                    "in the Mule project"
                                ),
                                file_name=file_name,
                                flow=reference.get("flow"),
                                processor=reference.get("component"),
                                evidence={
                                    "connector": reference.get(
                                        "connector"
                                    ),
                                    "config_ref": config_ref,
                                    "project_registry_match": False,
                                    "configuration_files_checked": (
                                        registry["parsed_file_count"]
                                    ),
                                },
                                recommendation=(
                                    f"Define a Mule configuration named "
                                    f"'{config_ref}' or correct the "
                                    "config-ref value. Check the "
                                    "configuration name and XML files "
                                    "that could not be parsed."
                                ),
                                confidence=confidence,
                                counter=config_counters[file_name],
                            )
                        )

            # ---------------------------------------------
            # Validate flow-ref values
            # ---------------------------------------------

            flow_analysis = analyses.get("flow_analysis", {})

            if isinstance(flow_analysis, dict):

                analyzed_flows = flow_analysis.get("flows", [])

                if isinstance(analyzed_flows, list):

                    for flow in analyzed_flows:

                        if not isinstance(flow, dict):
                            continue

                        flow_name = flow.get("name", "Unknown")

                        references = flow.get(
                            "flow_references", []
                        )

                        if not isinstance(references, list):
                            continue

                        for reference in references:

                            if not isinstance(reference, dict):
                                continue

                            if reference.get("type") != "UNKNOWN":
                                continue

                            target = reference.get("name")

                            if not target:
                                continue

                            if target in flows_registry:
                                continue

                            flow_counters[file_name] += 1

                            confidence = (
                                "low"
                                if registry["parse_failure_count"] > 0
                                else "high"
                            )

                            findings.append(
                                self._create_finding(
                                    rule_id="MADA-FLOW-001",
                                    category="flow",
                                    severity="medium",
                                    title=(
                                        "Flow reference was not found "
                                        "in the Mule project"
                                    ),
                                    file_name=file_name,
                                    flow=flow_name,
                                    processor="flow-ref",
                                    evidence={
                                        "referenced_flow": target,
                                        "reference_status": "UNKNOWN",
                                        "project_registry_match": False,
                                        "flow_files_checked": (
                                            registry["parsed_file_count"]
                                        ),
                                    },
                                    recommendation=(
                                        f"Create a flow or subflow named "
                                        f"'{target}', or correct the "
                                        "flow-ref name. Check whether "
                                        "any XML files containing its "
                                        "definition failed to parse."
                                    ),
                                    confidence=confidence,
                                    counter=flow_counters[file_name],
                                )
                            )

            issue_analysis["findings"] = findings

            self._refresh_summary(issue_analysis)

            if registry["parse_failure_count"] > 0:
                issue_analysis["note"] = (
                    "Project-wide reference validation was performed, "
                    "but one or more XML files could not be parsed. "
                    "Some references may remain unresolved because "
                    "the project registry may be incomplete."
                )
            else:
                issue_analysis["note"] = (
                    "Project-wide reference validation completed. "
                    "Connector configurations and flow references "
                    "were checked across the analyzed XML files."
                )

        return {
            "configuration_count": len(configurations),
            "flow_count": len(flows_registry),
            "parsed_file_count": registry["parsed_file_count"],
            "parse_failure_count": registry["parse_failure_count"],
            "configurations": configurations,
            "flows": flows_registry,
        }

    # =====================================================
    # REPORT
    # =====================================================

    def get_report(self, result):
        """Generate a readable issue detection report."""

        lines = [
            "MADA EVIDENCE-BASED ISSUE DETECTION REPORT",
            "=" * 55,
            f"File: {result.get('file', 'Unknown')}",
            f"Total issues: {result.get('issue_count', 0)}",
            "",
            "SEVERITY SUMMARY",
            "-" * 55,
        ]

        for severity, count in result.get(
            "severity_summary", {}
        ).items():
            lines.append(f"{severity.upper()}: {count}")

        lines.extend([
            "",
            "FINDINGS",
            "-" * 55,
        ])

        findings = result.get("findings", [])

        if not findings:
            lines.append(
                "No issues detected by the current rules."
            )

        for finding in findings:
            lines.extend([
                "",
                f"ID: {finding['id']}",
                f"Rule: {finding['rule_id']}",
                f"Severity: {finding['severity'].upper()}",
                f"Category: {finding['category']}",
                f"Issue: {finding['title']}",
                f"Flow: {finding.get('flow') or 'N/A'}",
                f"Processor: {finding.get('processor') or 'N/A'}",
                f"Evidence: {finding['evidence']}",
                f"Recommendation: {finding['recommendation']}",
            ])

        lines.extend([
            "",
            result.get("note", ""),
        ])

        return "\n".join(lines)