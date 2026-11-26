
package com.mada.studio.views;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.eclipse.core.resources.IFile;
import org.eclipse.core.resources.IProject;
import org.eclipse.core.resources.IResource;
import org.eclipse.core.resources.IWorkspaceRoot;
import org.eclipse.core.resources.ResourcesPlugin;
import org.eclipse.jface.viewers.IStructuredSelection;
import org.eclipse.swt.SWT;
import org.eclipse.swt.layout.GridData;
import org.eclipse.swt.layout.GridLayout;
import org.eclipse.swt.widgets.Button;
import org.eclipse.swt.widgets.Combo;
import org.eclipse.swt.widgets.Composite;
import org.eclipse.swt.widgets.Display;
import org.eclipse.swt.widgets.FileDialog;
import org.eclipse.swt.widgets.Label;
import org.eclipse.swt.widgets.Text;
import org.eclipse.ui.IWorkbenchWindow;
import org.eclipse.ui.PlatformUI;
import org.eclipse.ui.part.ViewPart;

import com.mada.studio.services.ProjectContext;
import com.mada.studio.services.ProjectScanner;

public class MadaChatView extends ViewPart {

    public static final String ID = "com.mada.studio.views.assistant";

    private static final String BACKEND_URL = "http://127.0.0.1:8000";

    private static final int MAX_XML_SIZE = 900 * 1024;

    private final HttpClient httpClient = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(10))
            .build();

    private Text chatHistory;
    private Text userInput;
    private Text apiKeyText;

    private Combo providerCombo;
    private Combo modelCombo;

    private Button applyButton;
    private Button sendButton;
    private Button scanProjectButton;
    private Button analyzeXmlButton;
    private Button analyzeWithAiButton;

    private Label apiKeyLabel;
    private Label projectStatusLabel;
    private Label xmlStatusLabel;
    private Label aiStatusLabel;
    private Label configurationStatusLabel;

    private boolean configurationApplied = false;
    private boolean loadingProviders = false;
    private boolean loadingModels = false;

    private ProjectContext currentProjectContext;

    /*
     * Stores raw JSON returned by /analyze/xml.
     */
    private String lastAnalysisJson;

    private String selectedProviderId;
    private String selectedModel;

    @Override
    public void createPartControl(Composite parent) {

        parent.setLayout(new GridLayout(1, false));

        createHeader(parent);
        createProviderConfiguration(parent);
        createProjectControls(parent);
        createXmlAnalysisControls(parent);
        createChatArea(parent);
        createInputArea(parent);

        loadProviders();
        loadChatHistory();

        appendMessage(
                "MADA",
                "Welcome! Select your AI provider and configure it to begin."
        );
    }

    // ============================================================
    // HEADER
    // ============================================================

    private void createHeader(Composite parent) {

        Label heading = new Label(parent, SWT.NONE);
        heading.setText("MADA - MuleSoft AI Developer Assistant");

        heading.setLayoutData(
                new GridData(SWT.FILL, SWT.CENTER, true, false)
        );

        Label description = new Label(parent, SWT.WRAP);
        description.setText(
                "Your AI assistant for MuleSoft development, project analysis, "
                + "XML explanation and troubleshooting."
        );

        description.setLayoutData(
                new GridData(SWT.FILL, SWT.CENTER, true, false)
        );
    }

    // ============================================================
    // PROVIDER CONFIGURATION
    // ============================================================

    private void createProviderConfiguration(Composite parent) {

        Composite configArea = new Composite(parent, SWT.BORDER);
        configArea.setLayout(new GridLayout(2, false));

        configArea.setLayoutData(
                new GridData(SWT.FILL, SWT.CENTER, true, false)
        );

        Label providerLabel = new Label(configArea, SWT.NONE);
        providerLabel.setText("AI Provider:");

        providerCombo = new Combo(
                configArea,
                SWT.DROP_DOWN | SWT.READ_ONLY
        );

        providerCombo.setLayoutData(
                new GridData(SWT.FILL, SWT.CENTER, true, false)
        );

        Label modelLabel = new Label(configArea, SWT.NONE);
        modelLabel.setText("Model:");

        modelCombo = new Combo(
                configArea,
                SWT.DROP_DOWN | SWT.READ_ONLY
        );

        modelCombo.setLayoutData(
                new GridData(SWT.FILL, SWT.CENTER, true, false)
        );

        apiKeyLabel = new Label(configArea, SWT.NONE);
        apiKeyLabel.setText("API Key:");

        apiKeyText = new Text(
                configArea,
                SWT.BORDER | SWT.PASSWORD
        );

        apiKeyText.setLayoutData(
                new GridData(SWT.FILL, SWT.CENTER, true, false)
        );

        applyButton = new Button(configArea, SWT.PUSH);
        applyButton.setText("Apply Configuration");

        configurationStatusLabel = new Label(configArea, SWT.WRAP);
        configurationStatusLabel.setText(
                "Configuration not applied."
        );

        configurationStatusLabel.setLayoutData(
                new GridData(SWT.FILL, SWT.CENTER, true, false)
        );

        providerCombo.addListener(SWT.Selection, event -> {

            configurationApplied = false;

            selectedProviderId = getSelectedProviderId();

            updateApiKeyControls();
            updateAiButtonState();

            configurationStatusLabel.setText(
                    "Provider changed. Apply configuration again."
            );

            loadModels();
        });

        modelCombo.addListener(SWT.Selection, event -> {

            configurationApplied = false;

            selectedModel = modelCombo.getText();

            updateAiButtonState();

            configurationStatusLabel.setText(
                    "Model changed. Apply configuration again."
            );
        });

        applyButton.addListener(
                SWT.Selection,
                event -> applyConfiguration()
        );
    }

    /*
     * Ollama is a local provider.
     * It does not require an API key.
     */
    private boolean isOllamaProvider(String provider) {

        return provider != null
                && provider.equalsIgnoreCase("ollama");
    }

    private void updateApiKeyControls() {

        if (apiKeyText == null || apiKeyText.isDisposed()) {
            return;
        }

        boolean ollama = isOllamaProvider(
                getSelectedProviderId()
        );

        apiKeyText.setEnabled(!ollama);

        if (apiKeyLabel != null && !apiKeyLabel.isDisposed()) {

            apiKeyLabel.setText(
                    ollama
                            ? "API Key (not required):"
                            : "API Key:"
            );
        }

        if (ollama) {

            apiKeyText.setText("");

            configurationStatusLabel.setText(
                    "Ollama selected. No API key required."
            );
        }

        apiKeyText.getParent().layout(true, true);
    }

    // ============================================================
    // PROJECT SCANNER CONTROLS
    // ============================================================

    private void createProjectControls(Composite parent) {

        Composite projectArea = new Composite(parent, SWT.NONE);

        projectArea.setLayout(new GridLayout(2, false));

        projectArea.setLayoutData(
                new GridData(SWT.FILL, SWT.CENTER, true, false)
        );

        scanProjectButton = new Button(projectArea, SWT.PUSH);
        scanProjectButton.setText("Scan Project");

        projectStatusLabel = new Label(projectArea, SWT.WRAP);
        projectStatusLabel.setText("No project scanned.");

        projectStatusLabel.setLayoutData(
                new GridData(SWT.FILL, SWT.CENTER, true, false)
        );

        scanProjectButton.addListener(
                SWT.Selection,
                event -> scanCurrentProject()
        );
    }

    // ============================================================
    // XML ANALYSIS CONTROLS
    // ============================================================

    private void createXmlAnalysisControls(Composite parent) {

        Composite xmlArea = new Composite(parent, SWT.NONE);

        xmlArea.setLayout(new GridLayout(2, false));

        xmlArea.setLayoutData(
                new GridData(SWT.FILL, SWT.CENTER, true, false)
        );

        analyzeXmlButton = new Button(xmlArea, SWT.PUSH);
        analyzeXmlButton.setText("Analyze Selected XML");

        xmlStatusLabel = new Label(xmlArea, SWT.WRAP);
        xmlStatusLabel.setText(
                "Select a Mule XML file to analyze."
        );

        xmlStatusLabel.setLayoutData(
                new GridData(SWT.FILL, SWT.CENTER, true, false)
        );

        analyzeXmlButton.addListener(
                SWT.Selection,
                event -> analyzeWorkspaceXmlFile()
        );

        analyzeWithAiButton = new Button(xmlArea, SWT.PUSH);
        analyzeWithAiButton.setText("Explain with AI");
        analyzeWithAiButton.setEnabled(false);

        aiStatusLabel = new Label(xmlArea, SWT.WRAP);
        aiStatusLabel.setText("Run XML analysis first.");

        aiStatusLabel.setLayoutData(
                new GridData(SWT.FILL, SWT.CENTER, true, false)
        );

        analyzeWithAiButton.addListener(
                SWT.Selection,
                event -> analyzeWithAI()
        );
    }

    // ============================================================
    // CHAT AREA
    // ============================================================

    private void createChatArea(Composite parent) {

        chatHistory = new Text(
                parent,
                SWT.BORDER
                        | SWT.MULTI
                        | SWT.V_SCROLL
                        | SWT.H_SCROLL
                        | SWT.READ_ONLY
                        | SWT.WRAP
        );

        chatHistory.setLayoutData(
                new GridData(SWT.FILL, SWT.FILL, true, true)
        );
    }

    // ============================================================
    // INPUT AREA
    // ============================================================

    private void createInputArea(Composite parent) {

        Composite inputArea = new Composite(parent, SWT.NONE);

        inputArea.setLayout(new GridLayout(2, false));

        inputArea.setLayoutData(
                new GridData(SWT.FILL, SWT.CENTER, true, false)
        );

        userInput = new Text(
                inputArea,
                SWT.BORDER | SWT.MULTI | SWT.WRAP | SWT.V_SCROLL
        );

        GridData inputData = new GridData(
                SWT.FILL,
                SWT.CENTER,
                true,
                false
        );

        inputData.heightHint = 55;

        userInput.setLayoutData(inputData);

        sendButton = new Button(inputArea, SWT.PUSH);
        sendButton.setText("Send");

        sendButton.setLayoutData(
                new GridData(SWT.FILL, SWT.CENTER, false, false)
        );

        sendButton.addListener(
                SWT.Selection,
                event -> sendMessage()
        );

        userInput.addListener(SWT.KeyDown, event -> {

            if (event.keyCode == SWT.CR
                    && (event.stateMask & SWT.SHIFT) == 0) {

                event.doit = false;
                sendMessage();
            }
        });
    }

    // ============================================================
    // PROVIDER LOADING
    // ============================================================

    private void loadProviders() {

        if (loadingProviders) {
            return;
        }

        loadingProviders = true;

        CompletableFuture.runAsync(() -> {

            try {

                String response = get("/providers");

                List<String[]> providers =
                        extractProviderDetails(response);

                ui(() -> {

                    providerCombo.removeAll();

                    for (String[] provider : providers) {

                        providerCombo.add(provider[1]);

                        providerCombo.setData(
                                provider[1],
                                provider[0]
                        );
                    }

                    if (providerCombo.getItemCount() > 0) {

                        providerCombo.select(0);

                        selectedProviderId = getSelectedProviderId();

                        updateApiKeyControls();

                        loadModels();

                    } else {

                        configurationStatusLabel.setText(
                                "No supported providers available."
                        );
                    }

                    loadingProviders = false;
                });

            } catch (Exception e) {

                ui(() -> {

                    loadingProviders = false;

                    configurationStatusLabel.setText(
                            "Could not load providers: " + e.getMessage()
                    );

                    appendMessage(
                            "MADA",
                            "Error loading AI providers: " + e.getMessage()
                    );
                });
            }
        });
    }

    private List<String[]> extractProviderDetails(String json) {

        List<String[]> providers = new ArrayList<>();

        String providersArray = extractJsonArray(
                json,
                "providers"
        );

        if (providersArray == null) {
            return providers;
        }

        Matcher matcher = Pattern.compile(
                "\\{([^{}]*)\\}"
        ).matcher(providersArray);

        while (matcher.find()) {

            String object = matcher.group();

            String id = extractJsonString(object, "id");
            String name = extractJsonString(object, "name");

            if (id == null || name == null) {
                continue;
            }

            /*
             * Only display providers implemented by the backend.
             */
            if (!id.equalsIgnoreCase("groq")
                    && !id.equalsIgnoreCase("gemini")
                    && !id.equalsIgnoreCase("huggingface")
                    && !id.equalsIgnoreCase("ollama")) {

                continue;
            }

            providers.add(new String[] { id, name });
        }

        return providers;
    }

    // ============================================================
    // MODEL LOADING
    // ============================================================

    private void loadModels() {

        if (loadingModels) {
            return;
        }

        String provider = getSelectedProviderId();

        if (provider == null || provider.isBlank()) {
            return;
        }

        loadingModels = true;

        CompletableFuture.runAsync(() -> {

            try {

                String response = get(
                        "/models?provider=" + provider
                );

                List<String> models = extractModelNames(response);

                ui(() -> {

                    modelCombo.removeAll();

                    for (String model : models) {
                        modelCombo.add(model);
                    }

                    if (modelCombo.getItemCount() > 0) {

                        modelCombo.select(0);

                        selectedModel = modelCombo.getText();

                    } else {

                        selectedModel = null;
                    }

                    loadingModels = false;
                });

            } catch (Exception e) {

                ui(() -> {

                    loadingModels = false;

                    modelCombo.removeAll();

                    selectedModel = null;

                    configurationStatusLabel.setText(
                            "Could not load models: " + e.getMessage()
                    );
                });
            }
        });
    }

    private List<String> extractModelNames(String json) {

        List<String> models = new ArrayList<>();

        String modelArray = extractJsonArray(json, "models");

        if (modelArray == null) {
            return models;
        }

        Matcher objectMatcher = Pattern.compile(
                "\\{([^{}]*)\\}"
        ).matcher(modelArray);

        boolean foundObjects = false;

        while (objectMatcher.find()) {

            foundObjects = true;

            String object = objectMatcher.group();

            String model = extractJsonString(object, "id");

            if (model == null) {
                model = extractJsonString(object, "name");
            }

            if (model != null && !models.contains(model)) {
                models.add(model);
            }
        }

        /*
         * Ollama model endpoint may return a string array.
         */
        if (!foundObjects) {

            Matcher stringMatcher = Pattern.compile(
                    "\"((?:\\\\.|[^\"\\\\])*)\""
            ).matcher(modelArray);

            while (stringMatcher.find()) {

                String model = unescapeJson(
                        stringMatcher.group(1)
                );

                if (!models.contains(model)) {
                    models.add(model);
                }
            }
        }

        return models;
    }

    private String getSelectedProviderId() {

        if (providerCombo == null || providerCombo.isDisposed()) {
            return null;
        }

        String selectedName = providerCombo.getText();

        if (selectedName == null || selectedName.isBlank()) {
            return null;
        }

        Object value = providerCombo.getData(selectedName);

        return value == null ? null : value.toString();
    }

    // ============================================================
    // APPLY PROVIDER CONFIGURATION
    // ============================================================

    private void applyConfiguration() {

        String provider = getSelectedProviderId();

        String model = modelCombo.getText();

        String apiKey = apiKeyText.getText().trim();

        if (provider == null || provider.isBlank()) {

            appendMessage(
                    "MADA",
                    "Please select an AI provider."
            );

            return;
        }

        if (model == null || model.isBlank()) {

            appendMessage(
                    "MADA",
                    "Please select an AI model."
            );

            return;
        }

        boolean ollama = isOllamaProvider(provider);

        /*
         * API keys are mandatory for cloud providers only.
         */
        if (!ollama && apiKey.isBlank()) {

            appendMessage(
                    "MADA",
                    "Please enter your API key."
            );

            return;
        }

        applyButton.setEnabled(false);

        configurationStatusLabel.setText(
                "Applying configuration..."
        );

        /*
         * Ollama receives an empty API key.
         * The backend must support Ollama without an API key.
         */
        String body = "{"
                + "\"provider\":\"" + escapeJson(provider) + "\","
                + "\"model\":\"" + escapeJson(model) + "\","
                + "\"api_key\":\"" + escapeJson(apiKey) + "\""
                + "}";

        CompletableFuture.runAsync(() -> {

            try {

                String response = postJson(
                        "/config/provider",
                        body
                );

                String message = extractJsonString(
                        response,
                        "message"
                );

                boolean success = extractJsonBoolean(
                        response,
                        "success"
                );

                if (!success) {

                    throw new RuntimeException(
                            message == null
                                    ? "Provider configuration failed."
                                    : message
                    );
                }

                ui(() -> {

                    configurationApplied = true;

                    selectedProviderId = provider;
                    selectedModel = model;

                    /*
                     * Clear the visible API key after successful setup.
                     */
                    apiKeyText.setText("");

                    configurationStatusLabel.setText(
                            "Configuration applied: " + provider
                    );

                    updateApiKeyControls();
                    updateAiButtonState();

                    appendMessage(
                            "MADA",
                            ollama
                                    ? "Local Ollama configuration applied successfully."
                                    : "AI provider configuration applied successfully."
                    );

                    applyButton.setEnabled(true);
                });

            } catch (Exception e) {

                ui(() -> {

                    configurationApplied = false;

                    configurationStatusLabel.setText(
                            "Configuration failed."
                    );

                    appendMessage(
                            "MADA",
                            "Configuration error: " + e.getMessage()
                    );

                    updateAiButtonState();

                    applyButton.setEnabled(true);
                });
            }
        });
    }

    // ============================================================
    // PROJECT SCANNING
    // ============================================================

    private void scanCurrentProject() {

        IProject project = getSelectedProject();

        if (project == null || !project.isOpen()) {

            appendMessage(
                    "MADA",
                    "Please select an open MuleSoft project in Project Explorer."
            );

            return;
        }

        scanProjectButton.setEnabled(false);

        projectStatusLabel.setText("Scanning project...");

        CompletableFuture.runAsync(() -> {

            try {

                ProjectScanner scanner = new ProjectScanner();

                Map<String, String> files =
                        scanner.scanProject(project);

                ProjectContext context = new ProjectContext(
                        project.getName(),
                        files
                );

                ui(() -> {

                    currentProjectContext = context;

                    projectStatusLabel.setText(
                            "Scanned " + context.getFileCount()
                                    + " files in " + context.getProjectName()
                    );

                    appendMessage(
                            "MADA",
                            "Project scan completed.\n"
                                    + "Project: " + context.getProjectName()
                                    + "\nFiles scanned: " + context.getFileCount()
                                    + "\nTotal bytes scanned: "
                                    + scanner.getTotalBytesScanned()
                    );

                    scanProjectButton.setEnabled(true);
                });

            } catch (Exception e) {

                ui(() -> {

                    projectStatusLabel.setText(
                            "Project scan failed."
                    );

                    appendMessage(
                            "MADA",
                            "Project scan failed: " + e.getMessage()
                    );

                    scanProjectButton.setEnabled(true);
                });
            }
        });
    }

    private IProject getSelectedProject() {

        try {

            IWorkbenchWindow window =
                    PlatformUI.getWorkbench().getActiveWorkbenchWindow();

            if (window != null
                    && window.getSelectionService() != null) {

                Object selection = window.getSelectionService()
                        .getSelection();

                if (selection instanceof IStructuredSelection) {

                    Object selected = ((IStructuredSelection) selection)
                            .getFirstElement();

                    if (selected instanceof IProject) {
                        return (IProject) selected;
                    }

                    if (selected instanceof IResource) {
                        return ((IResource) selected).getProject();
                    }
                }
            }

        } catch (Exception ignored) {
            // Continue with the open-project fallback.
        }

        IWorkspaceRoot root =
                ResourcesPlugin.getWorkspace().getRoot();

        IProject[] projects = root.getProjects();

        IProject onlyOpenProject = null;

        int openProjectCount = 0;

        for (IProject project : projects) {

            if (project.isOpen()) {

                openProjectCount++;

                onlyOpenProject = project;
            }
        }

        return openProjectCount == 1
                ? onlyOpenProject
                : null;
    }

    // ============================================================
    // SELECTED XML FILE
    // ============================================================

    private void analyzeWorkspaceXmlFile() {

        IFile workspaceFile = getSelectedXmlFile();

        if (workspaceFile != null) {

            analyzeXmlWorkspaceFile(workspaceFile);

            return;
        }

        FileDialog dialog = new FileDialog(
                getSite().getShell(),
                SWT.OPEN
        );

        dialog.setText("Select Mule XML File");

        dialog.setFilterExtensions(
                new String[] { "*.xml" }
        );

        String selectedPath = dialog.open();

        if (selectedPath == null) {
            return;
        }

        analyzeXmlLocalFile(Path.of(selectedPath));
    }

    private IFile getSelectedXmlFile() {

        try {

            IWorkbenchWindow window =
                    PlatformUI.getWorkbench().getActiveWorkbenchWindow();

            if (window == null) {
                return null;
            }

            Object selection = window.getSelectionService()
                    .getSelection();

            if (selection instanceof IStructuredSelection) {

                Object selected = ((IStructuredSelection) selection)
                        .getFirstElement();

                if (selected instanceof IFile) {

                    IFile file = (IFile) selected;

                    if ("xml".equalsIgnoreCase(
                            file.getFileExtension())) {

                        return file;
                    }
                }
            }

        } catch (Exception ignored) {
            // User can select a file through the file dialog.
        }

        return null;
    }

    private void analyzeXmlWorkspaceFile(IFile file) {

        try (InputStream input = file.getContents()) {

            byte[] bytes = readLimited(
                    input,
                    MAX_XML_SIZE
            );

            String xml = new String(
                    bytes,
                    StandardCharsets.UTF_8
            );

            submitXmlAnalysis(
                    file.getName(),
                    xml
            );

        } catch (Exception e) {

            appendMessage(
                    "MADA",
                    "Could not read XML file: " + e.getMessage()
            );
        }
    }

    private void analyzeXmlLocalFile(Path path) {

        try {

            long size = Files.size(path);

            if (size > MAX_XML_SIZE) {

                throw new IllegalArgumentException(
                        "XML file is larger than the 900 KB UI limit."
                );
            }

            String xml = Files.readString(
                    path,
                    StandardCharsets.UTF_8
            );

            submitXmlAnalysis(
                    path.getFileName().toString(),
                    xml
            );

        } catch (Exception e) {

            appendMessage(
                    "MADA",
                    "Could not read XML file: " + e.getMessage()
            );
        }
    }

    private byte[] readLimited(
            InputStream input,
            int maxBytes) throws Exception {

        ByteArrayOutputStream output =
                new ByteArrayOutputStream();

        byte[] buffer = new byte[8192];

        int total = 0;
        int count;

        while ((count = input.read(buffer)) != -1) {

            total += count;

            if (total > maxBytes) {

                throw new IllegalArgumentException(
                        "XML file is larger than the 900 KB UI limit."
                );
            }

            output.write(buffer, 0, count);
        }

        return output.toByteArray();
    }

    // ============================================================
    // STATIC XML ANALYSIS
    // ============================================================

    private void submitXmlAnalysis(
            String filename,
            String xml) {

        if (xml == null || xml.isBlank()) {

            appendMessage(
                    "MADA",
                    "The selected XML file is empty."
            );

            return;
        }

        lastAnalysisJson = null;

        updateAiButtonState();

        xmlStatusLabel.setText("Analyzing XML...");

        aiStatusLabel.setText(
                "Waiting for static analysis."
        );

        analyzeXmlButton.setEnabled(false);

        appendMessage(
                "MADA",
                "Analyzing Mule XML file: " + filename
        );

        String body = "{"
                + "\"filename\":\"" + escapeJson(filename) + "\","
                + "\"xml_content\":\"" + escapeJson(xml) + "\""
                + "}";

        CompletableFuture.runAsync(() -> {

            try {

                String response = postJson(
                        "/analyze/xml",
                        body
                );

                boolean success = extractJsonBoolean(
                        response,
                        "success"
                );

                if (!success) {

                    String error = extractJsonString(
                            response,
                            "message"
                    );

                    throw new RuntimeException(
                            error == null
                                    ? "Static XML analysis failed."
                                    : error
                    );
                }

                String analysis = extractJsonObject(
                        response,
                        "analysis"
                );

                if (analysis == null || analysis.isBlank()) {

                    throw new RuntimeException(
                            "The backend did not return structured analysis."
                    );
                }

                String message = extractJsonString(
                        response,
                        "message"
                );

                ui(() -> {

                    lastAnalysisJson = analysis;

                    xmlStatusLabel.setText(
                            "Static analysis completed: " + filename
                    );

                    aiStatusLabel.setText(
                            configurationApplied
                                    ? "Ready for AI explanation."
                                    : "Apply an AI provider configuration first."
                    );

                    updateAiButtonState();

                    appendMessage(
                            "MADA",
                            message == null
                                    ? "Static XML analysis completed."
                                    : message
                    );

                    appendMessage(
                            "MADA",
                            prettyPrintJson(analysis)
                    );

                    analyzeXmlButton.setEnabled(true);
                });

            } catch (Exception e) {

                ui(() -> {

                    lastAnalysisJson = null;

                    xmlStatusLabel.setText(
                            "XML analysis failed."
                    );

                    aiStatusLabel.setText(
                            "Run static XML analysis successfully first."
                    );

                    updateAiButtonState();

                    appendMessage(
                            "MADA",
                            "XML analysis failed: " + e.getMessage()
                    );

                    analyzeXmlButton.setEnabled(true);
                });
            }
        });
    }

    // ============================================================
    // AI-POWERED XML EXPLANATION
    // ============================================================

    private void analyzeWithAI() {

        if (lastAnalysisJson == null
                || lastAnalysisJson.isBlank()) {

            appendMessage(
                    "MADA",
                    "Please run static XML analysis first."
            );

            return;
        }

        if (!configurationApplied) {

            appendMessage(
                    "MADA",
                    "Please configure and apply an AI provider first."
            );

            return;
        }

        analyzeWithAiButton.setEnabled(false);

        aiStatusLabel.setText(
                "AI analysis is running..."
        );

        appendMessage(
                "MADA",
                "Running AI-powered MuleSoft analysis. Please wait..."
        );

        String requestBody =
                "{\"analysis\":" + lastAnalysisJson + "}";

        CompletableFuture.runAsync(() -> {

            try {

                String response = postJson(
                        "/analyze/ai",
                        requestBody
                );

                boolean success = extractJsonBoolean(
                        response,
                        "success"
                );

                if (!success) {

                    String error = extractJsonString(
                            response,
                            "message"
                    );

                    throw new RuntimeException(
                            error == null
                                    ? "AI analysis failed."
                                    : error
                    );
                }

                String resultObject = extractJsonObject(
                        response,
                        "result"
                );

                if (resultObject == null) {
                    resultObject = response;
                }

                String aiAnalysis = extractJsonString(
                        resultObject,
                        "ai_analysis"
                );

                String provider = extractJsonString(
                        resultObject,
                        "provider"
                );

                String model = extractJsonString(
                        resultObject,
                        "model"
                );

                String reportPath = extractJsonString(
                        resultObject,
                        "report_path"
                );

                if (aiAnalysis == null || aiAnalysis.isBlank()) {

                    throw new RuntimeException(
                            "The backend response did not contain ai_analysis."
                    );
                }

                StringBuilder output = new StringBuilder();

                output.append("AI ANALYSIS COMPLETED\n\n");

                if (provider != null) {

                    output.append("Provider: ")
                            .append(provider)
                            .append("\n");
                }

                if (model != null) {

                    output.append("Model: ")
                            .append(model)
                            .append("\n");
                }

                output.append("\n");
                output.append(aiAnalysis);

                if (reportPath != null
                        && !reportPath.isBlank()) {

                    output.append("\n\n");
                    output.append("Report saved to:\n");
                    output.append(reportPath);
                }

                String finalOutput = output.toString();

                ui(() -> {

                    appendMessage(
                            "MADA",
                            finalOutput
                    );

                    aiStatusLabel.setText(
                            "AI-powered analysis completed."
                    );

                    updateAiButtonState();
                });

            } catch (Exception e) {

                ui(() -> {

                    appendMessage(
                            "MADA",
                            "AI analysis failed: " + e.getMessage()
                    );

                    aiStatusLabel.setText(
                            "AI-powered analysis failed."
                    );

                    updateAiButtonState();
                });
            }
        });
    }

    private void updateAiButtonState() {

        if (analyzeWithAiButton == null
                || analyzeWithAiButton.isDisposed()) {

            return;
        }

        boolean hasAnalysis =
                lastAnalysisJson != null
                        && !lastAnalysisJson.isBlank();

        analyzeWithAiButton.setEnabled(
                configurationApplied && hasAnalysis
        );
    }

    // ============================================================
    // CHAT MESSAGE
    // ============================================================

    private void sendMessage() {

        String message = userInput.getText().trim();

        if (message.isBlank()) {
            return;
        }

        if (!configurationApplied) {

            appendMessage(
                    "MADA",
                    "Please configure and apply an AI provider first."
            );

            return;
        }

        userInput.setText("");

        appendMessage("You", message);

        appendMessage("MADA", "Thinking...");

        sendButton.setEnabled(false);

        StringBuilder body = new StringBuilder();

        body.append("{");

        body.append("\"message\":\"")
                .append(escapeJson(message))
                .append("\"");

        if (currentProjectContext != null) {

            body.append(",\"project_context\":\"")
                    .append(escapeJson(
                            currentProjectContext.toPromptContext()
                    ))
                    .append("\"");
        }

        body.append("}");

        CompletableFuture.runAsync(() -> {

            try {

                String response = postJson(
                        "/chat",
                        body.toString()
                );

                String answer = extractJsonString(
                        response,
                        "response"
                );

                if (answer == null) {

                    answer = extractJsonString(
                            response,
                            "message"
                    );
                }

                if (answer == null) {
                    answer = response;
                }

                String finalAnswer = answer;

                ui(() -> {

                    removeLastThinkingMessage();

                    appendMessage(
                            "MADA",
                            finalAnswer
                    );

                    sendButton.setEnabled(true);
                });

            } catch (Exception e) {

                ui(() -> {

                    removeLastThinkingMessage();

                    appendMessage(
                            "MADA",
                            "Request failed: " + e.getMessage()
                    );

                    sendButton.setEnabled(true);
                });
            }
        });
    }

    // ============================================================
    // CHAT HISTORY
    // ============================================================

    private void loadChatHistory() {

        CompletableFuture.runAsync(() -> {

            try {

                String response = get("/chat/history");

                String historyArray = extractJsonArray(
                        response,
                        "history"
                );

                if (historyArray == null) {
                    return;
                }

                Matcher matcher = Pattern.compile(
                        "\\{([^{}]*)\\}"
                ).matcher(historyArray);

                List<String> messages = new ArrayList<>();

                while (matcher.find()) {

                    String object = matcher.group();

                    String role = extractJsonString(
                            object,
                            "role"
                    );

                    String content = extractJsonString(
                            object,
                            "content"
                    );

                    if (role != null && content != null) {

                        messages.add(
                                role + ": " + content
                        );
                    }
                }

                ui(() -> {

                    if (chatHistory == null
                            || chatHistory.isDisposed()) {

                        return;
                    }

                    for (String message : messages) {

                        chatHistory.append(
                                message + "\n\n"
                        );
                    }
                });

            } catch (Exception ignored) {
                // Chat history is optional.
            }
        });
    }

    private void removeLastThinkingMessage() {

        if (chatHistory == null
                || chatHistory.isDisposed()) {

            return;
        }

        String current = chatHistory.getText();

        String thinking = "MADA: Thinking...\n\n";

        int index = current.lastIndexOf(thinking);

        if (index >= 0) {

            chatHistory.setText(
                    current.substring(0, index)
                            + current.substring(
                                    index + thinking.length()
                            )
            );
        }
    }

    // ============================================================
    // HTTP HELPERS
    // ============================================================

    private String get(String endpoint) throws Exception {

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(BACKEND_URL + endpoint))
                .timeout(Duration.ofSeconds(60))
                .GET()
                .build();

        HttpResponse<String> response = httpClient.send(
                request,
                HttpResponse.BodyHandlers.ofString(
                        StandardCharsets.UTF_8
                )
        );

        checkHttpStatus(
                response.statusCode(),
                response.body()
        );

        return response.body();
    }

    private String postJson(
            String endpoint,
            String body) throws Exception {

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(BACKEND_URL + endpoint))
                .timeout(Duration.ofSeconds(180))
                .header("Content-Type", "application/json")
                .POST(
                        HttpRequest.BodyPublishers.ofString(
                                body,
                                StandardCharsets.UTF_8
                        )
                )
                .build();

        HttpResponse<String> response = httpClient.send(
                request,
                HttpResponse.BodyHandlers.ofString(
                        StandardCharsets.UTF_8
                )
        );

        checkHttpStatus(
                response.statusCode(),
                response.body()
        );

        return response.body();
    }

    private void checkHttpStatus(
            int status,
            String body) throws Exception {

        if (status < 200 || status >= 300) {

            String message = extractJsonString(
                    body,
                    "message"
            );

            if (message == null) {

                message = extractJsonString(
                        body,
                        "detail"
                );
            }

            if (message == null || message.isBlank()) {
                message = body;
            }

            throw new RuntimeException(
                    "HTTP " + status + ": " + message
            );
        }
    }

    // ============================================================
    // JSON HELPERS
    // ============================================================

    private String extractJsonString(
            String json,
            String key) {

        if (json == null || key == null) {
            return null;
        }

        String pattern = "\""
                + Pattern.quote(key)
                + "\"\\s*:\\s*\"((?:\\\\.|[^\"\\\\])*)\"";

        Matcher matcher = Pattern.compile(
                pattern,
                Pattern.DOTALL
        ).matcher(json);

        if (!matcher.find()) {
            return null;
        }

        return unescapeJson(matcher.group(1));
    }

    private String extractJsonObject(
            String json,
            String key) {

        if (json == null || key == null) {
            return null;
        }

        Matcher matcher = Pattern.compile(
                "\"" + Pattern.quote(key) + "\"\\s*:\\s*\\{"
        ).matcher(json);

        if (!matcher.find()) {
            return null;
        }

        int start = matcher.end() - 1;

        return extractBalancedJson(
                json,
                start,
                '{',
                '}'
        );
    }

    private String extractJsonArray(
            String json,
            String key) {

        if (json == null || key == null) {
            return null;
        }

        Matcher matcher = Pattern.compile(
                "\"" + Pattern.quote(key) + "\"\\s*:\\s*\\["
        ).matcher(json);

        if (!matcher.find()) {
            return null;
        }

        int start = matcher.end() - 1;

        return extractBalancedJson(
                json,
                start,
                '[',
                ']'
        );
    }

    private String extractBalancedJson(
            String json,
            int start,
            char opening,
            char closing) {

        if (start < 0 || start >= json.length()) {
            return null;
        }

        int depth = 0;

        boolean inString = false;
        boolean escaped = false;

        for (int i = start; i < json.length(); i++) {

            char current = json.charAt(i);

            if (inString) {

                if (escaped) {

                    escaped = false;

                } else if (current == '\\') {

                    escaped = true;

                } else if (current == '"') {

                    inString = false;
                }

                continue;
            }

            if (current == '"') {

                inString = true;

            } else if (current == opening) {

                depth++;

            } else if (current == closing) {

                depth--;

                if (depth == 0) {

                    return json.substring(
                            start,
                            i + 1
                    );
                }
            }
        }

        return null;
    }

    private boolean extractJsonBoolean(
            String json,
            String key) {

        if (json == null || key == null) {
            return false;
        }

        Matcher matcher = Pattern.compile(
                "\"" + Pattern.quote(key)
                        + "\"\\s*:\\s*(true|false)",
                Pattern.CASE_INSENSITIVE
        ).matcher(json);

        return matcher.find()
                && Boolean.parseBoolean(matcher.group(1));
    }

    private String escapeJson(String value) {

        if (value == null) {
            return "";
        }

        StringBuilder result = new StringBuilder();

        for (int i = 0; i < value.length(); i++) {

            char c = value.charAt(i);

            switch (c) {

                case '"':
                    result.append("\\\"");
                    break;

                case '\\':
                    result.append("\\\\");
                    break;

                case '\b':
                    result.append("\\b");
                    break;

                case '\f':
                    result.append("\\f");
                    break;

                case '\n':
                    result.append("\\n");
                    break;

                case '\r':
                    result.append("\\r");
                    break;

                case '\t':
                    result.append("\\t");
                    break;

                default:

                    if (c < 0x20) {

                        result.append(
                                String.format(
                                        "\\u%04x",
                                        (int) c
                                )
                        );

                    } else {

                        result.append(c);
                    }
            }
        }

        return result.toString();
    }

    private String unescapeJson(String value) {

        if (value == null) {
            return null;
        }

        StringBuilder result = new StringBuilder();

        boolean escaped = false;

        for (int i = 0; i < value.length(); i++) {

            char c = value.charAt(i);

            if (!escaped) {

                if (c == '\\') {

                    escaped = true;

                } else {

                    result.append(c);
                }

                continue;
            }

            escaped = false;

            switch (c) {

                case '"':
                    result.append('"');
                    break;

                case '\\':
                    result.append('\\');
                    break;

                case '/':
                    result.append('/');
                    break;

                case 'b':
                    result.append('\b');
                    break;

                case 'f':
                    result.append('\f');
                    break;

                case 'n':
                    result.append('\n');
                    break;

                case 'r':
                    result.append('\r');
                    break;

                case 't':
                    result.append('\t');
                    break;

                case 'u':

                    if (i + 4 < value.length()) {

                        String hex = value.substring(
                                i + 1,
                                i + 5
                        );

                        try {

                            result.append(
                                    (char) Integer.parseInt(hex, 16)
                            );

                            i += 4;

                        } catch (NumberFormatException e) {

                            result.append("\\u")
                                    .append(hex);

                            i += 4;
                        }

                    } else {

                        result.append("\\u");
                    }

                    break;

                default:
                    result.append(c);
            }
        }

        if (escaped) {
            result.append('\\');
        }

        return result.toString();
    }

    private String prettyPrintJson(String json) {

        if (json == null) {
            return "";
        }

        StringBuilder output = new StringBuilder();

        int indent = 0;

        boolean inString = false;
        boolean escaped = false;

        for (int i = 0; i < json.length(); i++) {

            char c = json.charAt(i);

            if (inString) {

                output.append(c);

                if (escaped) {

                    escaped = false;

                } else if (c == '\\') {

                    escaped = true;

                } else if (c == '"') {

                    inString = false;
                }

                continue;
            }

            switch (c) {

                case '"':
                    inString = true;
                    output.append(c);
                    break;

                case '{':
                case '[':

                    output.append(c);
                    output.append('\n');

                    indent++;

                    appendIndent(output, indent);
                    break;

                case '}':
                case ']':

                    output.append('\n');

                    indent = Math.max(0, indent - 1);

                    appendIndent(output, indent);

                    output.append(c);
                    break;

                case ',':

                    output.append(c);
                    output.append('\n');

                    appendIndent(output, indent);
                    break;

                case ':':

                    output.append(": ");
                    break;

                default:

                    if (!Character.isWhitespace(c)) {
                        output.append(c);
                    }
            }
        }

        return output.toString();
    }

    private void appendIndent(
            StringBuilder output,
            int indent) {

        for (int i = 0; i < indent; i++) {
            output.append("    ");
        }
    }

    // ============================================================
    // UI HELPERS
    // ============================================================

    private void appendMessage(
            String sender,
            String message) {

        if (chatHistory == null
                || chatHistory.isDisposed()) {

            return;
        }

        String safeMessage =
                message == null ? "" : message;

        chatHistory.append(
                sender + ": " + safeMessage + "\n\n"
        );

        chatHistory.setSelection(
                chatHistory.getText().length()
        );
    }

    private void ui(Runnable runnable) {

        Display display = Display.getDefault();

        if (display == null || display.isDisposed()) {
            return;
        }

        display.asyncExec(() -> {

            if (display.isDisposed()) {
                return;
            }

            if (getSite() == null
                    || getSite().getShell() == null
                    || getSite().getShell().isDisposed()) {

                return;
            }

            runnable.run();
        });
    }

    // ============================================================
    // VIEW LIFECYCLE
    // ============================================================

    @Override
    public void setFocus() {

        if (userInput != null
                && !userInput.isDisposed()) {

            userInput.setFocus();
        }
    }

    @Override
    public void dispose() {

        lastAnalysisJson = null;
        currentProjectContext = null;

        super.dispose();
    }
}
