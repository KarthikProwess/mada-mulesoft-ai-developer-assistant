
import json
import tempfile
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from app.prompts.mulesoft_system_prompt import MULESOFT_SYSTEM_PROMPT

from app.providers.gemini import GeminiProvider
from app.providers.huggingface import HuggingFaceProvider
from app.providers.groq import GroqProvider
from app.providers.ollama import OllamaProvider

from app.providers.registry import (
    list_providers,
    set_provider_configured,
    reset_provider_configuration
)

from app.agents.mule_project_analyzer import MuleProjectAnalyzer
from app.agents.ai_analysis_agent import AIAnalysisAgent


# ============================================================
# MADA SERVER CONFIGURATION
# ============================================================

HOST = "127.0.0.1"
PORT = 8000

MAX_REQUEST_SIZE = 2 * 1024 * 1024
MAX_PROJECT_CONTEXT_CHARS = 12000
MAX_HISTORY_MESSAGES = 4
MAX_XML_SIZE = 2 * 1024 * 1024

ACTIVE_CONFIG = {
    "provider": None,
    "model": None,
    "api_key": None
}

CHAT_HISTORY = []


# ============================================================
# MADA SYSTEM PROMPT
# ============================================================

# Use the dedicated MuleSoft system prompt.
SYSTEM_PROMPT = MULESOFT_SYSTEM_PROMPT


# ============================================================
# PROVIDER MANAGEMENT
# ============================================================

def get_provider_instance(provider_id, api_key=None):
    """
    Create the requested AI provider instance.
    """

    if provider_id == "groq":
        return GroqProvider(api_key)

    if provider_id == "gemini":
        return GeminiProvider(api_key)

    if provider_id == "huggingface":
        return HuggingFaceProvider(api_key)

    if provider_id == "ollama":
        return OllamaProvider()

    raise RuntimeError(
        "Unsupported provider: " + str(provider_id)
    )


def get_active_provider():
    """
    Return the currently configured AI provider.
    """

    provider_id = ACTIVE_CONFIG.get("provider")
    api_key = ACTIVE_CONFIG.get("api_key")

    if not provider_id:
        raise RuntimeError(
            "No AI provider has been configured."
        )

    if provider_id == "ollama":
        return get_provider_instance("ollama")

    if not api_key:
        raise RuntimeError(
            "API key is missing. Configure the provider first."
        )

    return get_provider_instance(
        provider_id,
        api_key
    )


def get_available_models(provider_id, api_key=None):
    """
    Retrieve available models for a provider.
    """

    supported_providers = (
        "groq",
        "gemini",
        "huggingface",
        "ollama"
    )

    if provider_id not in supported_providers:
        raise RuntimeError(
            "Unsupported provider: " + str(provider_id)
        )

    if provider_id == "ollama":
        provider = OllamaProvider()

    else:

        if not api_key:
            raise RuntimeError(
                "API key is required for this provider."
            )

        provider = get_provider_instance(
            provider_id,
            api_key
        )

    return provider.list_models()


# ============================================================
# UNIFIED MULE PROJECT ANALYSIS
# ============================================================

def analyze_xml_content(filename, xml_content):
    """
    Analyze XML supplied directly by the Eclipse plugin.
    """

    if not isinstance(filename, str) or not filename.strip():
        raise ValueError(
            "A filename is required."
        )

    if not isinstance(xml_content, str) or not xml_content.strip():
        raise ValueError(
            "XML content cannot be empty."
        )

    xml_bytes = xml_content.encode("utf-8")

    if len(xml_bytes) > MAX_XML_SIZE:
        raise ValueError(
            "XML file exceeds the maximum allowed size."
        )

    safe_filename = Path(filename).name

    if not safe_filename.lower().endswith(".xml"):
        raise ValueError(
            "Only XML files can be analyzed."
        )

    with tempfile.TemporaryDirectory(
        prefix="mada_analysis_"
    ) as temp_dir:

        xml_path = Path(temp_dir) / safe_filename

        xml_path.write_text(
            xml_content,
            encoding="utf-8"
        )

        analyzer = MuleProjectAnalyzer()

        result = analyzer.analyze_file(
            str(xml_path)
        )

        return result


# ============================================================
# AI-POWERED ANALYSIS
# ============================================================

def run_ai_analysis(analysis_result):
    """
    Explain static MuleSoft analysis results using AI.
    """

    if not isinstance(analysis_result, dict):
        raise ValueError(
            "Analysis result must be a JSON object."
        )

    if not analysis_result:
        raise ValueError(
            "Analysis result cannot be empty."
        )

    provider_id = ACTIVE_CONFIG.get("provider")
    model = ACTIVE_CONFIG.get("model")

    if not provider_id or not model:
        raise RuntimeError(
            "Configure an AI provider and model before "
            "running AI analysis."
        )

    provider = get_active_provider()

    ai_agent = AIAnalysisAgent()

    ai_result = ai_agent.analyze(
        analysis_result,
        provider,
        model
    )

    if not isinstance(ai_result, dict):
        raise RuntimeError(
            "AI Analysis Agent returned an invalid response."
        )

    if not ai_result.get("success"):
        raise RuntimeError(
            "AI analysis could not be completed."
        )

    report_path = None
    report_saved = False
    report_save_error = None

    try:

        report_path = ai_agent.save_report(
            ai_result,
            "reports/mada-ai-analysis-report.md"
        )

        if report_path is not None:
            report_path = str(report_path)

        report_saved = True

    except (OSError, ValueError) as error:

        report_save_error = str(error)

        print(
            "[MADA] AI report could not be saved:",
            report_save_error
        )

    return {
        "success": True,
        "application": ai_result.get("application"),
        "analysis_status": ai_result.get("analysis_status"),
        "provider": ai_result.get("provider"),
        "model": ai_result.get("model"),
        "ai_analysis": ai_result.get("ai_analysis"),
        "report_saved": report_saved,
        "report_path": report_path,
        "report_save_error": report_save_error
    }


# ============================================================
# PROVIDER CONFIGURATION
# ============================================================

def configure_provider(provider_id, model, api_key=None):
    """
    Validate and configure an AI provider.

    Ollama does not require an API key.
    """

    if not isinstance(provider_id, str) or not provider_id.strip():
        raise ValueError(
            "Provider is required."
        )

    if not isinstance(model, str) or not model.strip():
        raise ValueError(
            "Model is required."
        )

    provider_id = provider_id.strip()
    model = model.strip()

    if provider_id == "ollama":
        api_key = None

    else:

        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError(
                "API key is required for this provider."
            )

        api_key = api_key.strip()

    provider = get_provider_instance(
        provider_id,
        api_key
    )

    available_models = provider.list_models()

    if model not in available_models:
        raise ValueError(
            "Selected model is not supported. "
            "Available models: "
            + ", ".join(available_models)
        )

    ACTIVE_CONFIG["provider"] = provider_id
    ACTIVE_CONFIG["model"] = model
    ACTIVE_CONFIG["api_key"] = api_key

    set_provider_configured(provider_id)

    return {
        "success": True,
        "provider": provider_id,
        "model": model
    }


# ============================================================
# RESET ACTIVE CONFIGURATION
# ============================================================

def reset_active_configuration():
    """
    Clear the active provider configuration.
    """

    ACTIVE_CONFIG["provider"] = None
    ACTIVE_CONFIG["model"] = None
    ACTIVE_CONFIG["api_key"] = None

    reset_provider_configuration()


# ============================================================
# HTTP SERVER
# ============================================================

class MADARequestHandler(BaseHTTPRequestHandler):

    server_version = "MADA/1.0"

    # --------------------------------------------------------
    # JSON RESPONSE
    # --------------------------------------------------------

    def send_json(self, status_code, response_data):

        response_body = json.dumps(
            response_data,
            ensure_ascii=False
        ).encode("utf-8")

        self.send_response(status_code)

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8"
        )

        self.send_header(
            "Content-Length",
            str(len(response_body))
        )

        self.send_header(
            "Access-Control-Allow-Origin",
            "http://localhost"
        )

        self.send_header(
            "Access-Control-Allow-Methods",
            "GET, POST, OPTIONS"
        )

        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type"
        )

        self.end_headers()

        self.wfile.write(response_body)

    # --------------------------------------------------------
    # READ JSON REQUEST
    # --------------------------------------------------------

    def read_json_body(self):

        try:
            content_length = int(
                self.headers.get("Content-Length", 0)
            )

        except ValueError:
            raise ValueError(
                "Invalid Content-Length header."
            )

        if content_length <= 0:
            raise ValueError(
                "Request body is empty."
            )

        if content_length > MAX_REQUEST_SIZE:
            raise ValueError(
                "Request body is too large."
            )

        raw_body = self.rfile.read(
            content_length
        )

        try:

            data = json.loads(
                raw_body.decode("utf-8")
            )

        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ValueError(
                "Invalid JSON request."
            )

        if not isinstance(data, dict):
            raise ValueError(
                "JSON request must be an object."
            )

        return data

    # --------------------------------------------------------
    # OPTIONS
    # --------------------------------------------------------

    def do_OPTIONS(self):

        self.send_response(204)

        self.send_header(
            "Access-Control-Allow-Origin",
            "http://localhost"
        )

        self.send_header(
            "Access-Control-Allow-Methods",
            "GET, POST, OPTIONS"
        )

        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type"
        )

        self.end_headers()

    # ========================================================
    # GET ENDPOINTS
    # ========================================================

    def do_GET(self):

        parsed_url = urlparse(self.path)
        path = parsed_url.path

        # HEALTH CHECK
        if path == "/health":

            self.send_json(200, {
                "status": "UP",
                "application": "MADA",
                "message": "MADA backend is running."
            })

            return

        # PROVIDERS
        if path == "/providers":

            providers = list_providers()

            self.send_json(200, {
                "providers": providers
            })

            return

        # MODELS
        if path == "/models":

            query_parameters = parse_qs(
                parsed_url.query
            )

            provider_id = query_parameters.get(
                "provider",
                [None]
            )[0]

            if not provider_id:

                self.send_json(400, {
                    "error": "Provider is required."
                })

                return

            try:

                api_key = None

                if provider_id == ACTIVE_CONFIG.get("provider"):
                    api_key = ACTIVE_CONFIG.get("api_key")

                models = get_available_models(
                    provider_id,
                    api_key
                )

                self.send_json(200, {
                    "models": models
                })

            except Exception as error:

                self.send_json(400, {
                    "error": str(error)
                })

            return

        # CHAT HISTORY
        if path == "/chat/history":

            self.send_json(200, {
                "history": CHAT_HISTORY
            })

            return

        # UNKNOWN ENDPOINT
        self.send_json(404, {
            "error": "Endpoint not found."
        })

    # ========================================================
    # POST ENDPOINTS
    # ========================================================

    def do_POST(self):

        parsed_url = urlparse(self.path)
        path = parsed_url.path

        # CLEAR CHAT HISTORY
        if path == "/chat/clear":

            CHAT_HISTORY.clear()

            self.send_json(200, {
                "success": True,
                "message": "Chat history cleared."
            })

            return

        try:

            data = self.read_json_body()

        except ValueError as error:

            self.send_json(400, {
                "error": str(error)
            })

            return

        # ----------------------------------------------------
        # UNIFIED MULE XML ANALYSIS
        # ----------------------------------------------------

        if path == "/analyze/xml":

            filename = data.get("filename")
            xml_content = data.get("xml_content")

            try:

                result = analyze_xml_content(
                    filename,
                    xml_content
                )

                self.send_json(200, {
                    "success": True,
                    "message": "Mule XML analysis completed.",
                    "analysis": result
                })

            except (ValueError, OSError) as error:

                self.send_json(400, {
                    "success": False,
                    "error": str(error)
                })

            except Exception as error:

                print(
                    "[MADA] XML analysis error:",
                    str(error)
                )

                self.send_json(500, {
                    "success": False,
                    "error": "Mule XML analysis failed."
                })

            return

        # ----------------------------------------------------
        # AI-POWERED MULE ANALYSIS
        # ----------------------------------------------------

        if path == "/analyze/ai":

            analysis_result = data.get("analysis")

            try:

                result = run_ai_analysis(
                    analysis_result
                )

                self.send_json(200, {
                    "success": True,
                    "message": (
                        "AI-powered MuleSoft analysis completed."
                    ),
                    "result": result
                })

            except ValueError as error:

                self.send_json(400, {
                    "success": False,
                    "error": str(error)
                })

            except RuntimeError as error:

                self.send_json(400, {
                    "success": False,
                    "error": str(error)
                })

            except Exception as error:

                print(
                    "[MADA] AI analysis error:",
                    str(error)
                )

                self.send_json(502, {
                    "success": False,
                    "error": (
                        "AI-powered analysis failed. "
                        "Check the provider configuration "
                        "and backend logs."
                    )
                })

            return

        # ----------------------------------------------------
        # CONFIGURE AI PROVIDER
        # ----------------------------------------------------

        if path == "/config/provider":

            provider_id = data.get("provider")
            model = data.get("model")
            api_key = data.get("api_key")

            try:

                result = configure_provider(
                    provider_id,
                    model,
                    api_key
                )

                self.send_json(200, {
                    "success": True,
                    "message": (
                        "AI provider configured successfully."
                    ),
                    "provider": result["provider"],
                    "model": result["model"]
                })

            except ValueError as error:

                self.send_json(400, {
                    "success": False,
                    "error": str(error)
                })

            except Exception as error:

                print(
                    "[MADA] Provider configuration error:",
                    str(error)
                )

                self.send_json(400, {
                    "success": False,
                    "error": str(error)
                })

            return

        # ----------------------------------------------------
        # CHAT
        # ----------------------------------------------------

        if path == "/chat":

            message = data.get(
                "message",
                ""
            )

            if not isinstance(message, str) or not message.strip():

                self.send_json(400, {
                    "error": "Message cannot be empty."
                })

                return

            if not ACTIVE_CONFIG.get("provider"):

                self.send_json(400, {
                    "error": (
                        "Please configure an AI provider "
                        "before chatting."
                    )
                })

                return

            project_context = data.get(
                "project_context",
                ""
            )

            if project_context is None:
                project_context = ""

            if not isinstance(project_context, str):

                self.send_json(400, {
                    "error": "Project context must be a string."
                })

                return

            project_context = project_context[
                :MAX_PROJECT_CONTEXT_CHARS
            ]

            user_content = message.strip()

            if project_context:

                user_content = (
                    "PROJECT CONTEXT START\n"
                    "The following content was scanned from the "
                    "user's local MuleSoft project.\n"
                    "Use it only as reference material for answering "
                    "the user's question.\n\n"
                    + project_context
                    + "\n\nPROJECT CONTEXT END\n\n"
                    + "USER QUESTION:\n"
                    + message.strip()
                )

            recent_history = CHAT_HISTORY[
                -MAX_HISTORY_MESSAGES:
            ]

            # System prompt is sent once per request.
            messages = [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                }
            ] + recent_history + [
                {
                    "role": "user",
                    "content": user_content
                }
            ]

            try:

                provider = get_active_provider()
                model = ACTIVE_CONFIG.get("model")

                answer = provider.generate_response(
                    messages,
                    model
                )

                # Store only user and assistant messages.
                # Never store the system prompt.
                CHAT_HISTORY.append({
                    "role": "user",
                    "content": message.strip()
                })

                CHAT_HISTORY.append({
                    "role": "assistant",
                    "content": answer
                })

                if len(CHAT_HISTORY) > MAX_HISTORY_MESSAGES:

                    del CHAT_HISTORY[
                        :-MAX_HISTORY_MESSAGES
                    ]

                self.send_json(200, {
                    "success": True,
                    "response": answer
                })

            except Exception as error:

                print(
                    "[MADA] Chat error:",
                    str(error)
                )

                self.send_json(502, {
                    "success": False,
                    "error": str(error)
                })

            return

        # UNKNOWN ENDPOINT
        self.send_json(404, {
            "error": "Endpoint not found."
        })

    # --------------------------------------------------------
    # LOGGING
    # --------------------------------------------------------

    def log_message(self, format_string, *args):

        print(
            "[MADA] %s - %s"
            % (
                self.address_string(),
                format_string % args
            )
        )


# ============================================================
# START SERVER
# ============================================================

def start_server():

    server = ThreadingHTTPServer(
        (HOST, PORT),
        MADARequestHandler
    )

    print("----------------------------------------")
    print(" MADA Backend Started")
    print("----------------------------------------")
    print(f" Server: http://{HOST}:{PORT}")
    print(f" Health: http://{HOST}:{PORT}/health")
    print(f" Providers: http://{HOST}:{PORT}/providers")
    print(f" Models: http://{HOST}:{PORT}/models")
    print(f" XML Analysis: http://{HOST}:{PORT}/analyze/xml")
    print(f" AI Analysis: http://{HOST}:{PORT}/analyze/ai")
    print("----------------------------------------")

    try:

        server.serve_forever()

    except KeyboardInterrupt:

        print("\n[MADA] Server shutting down...")

    finally:

        server.server_close()


if __name__ == "__main__":
    start_server()
