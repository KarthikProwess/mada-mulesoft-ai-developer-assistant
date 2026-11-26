
from app.agents.flow_analysis_agent import FlowAnalysisAgent


def main():

    xml_file = "sample-mule.xml"

    agent = FlowAnalysisAgent()

    print("Starting MADA Flow Analysis Agent...")

    analysis = agent.analyze_file(xml_file)

    print("\nStructured Analysis:\n")

    import json

    print(
        json.dumps(
            analysis,
            indent=4,
            ensure_ascii=False
        )
    )

    print("\n")

    print(agent.get_report())


if __name__ == "__main__":

    main()
