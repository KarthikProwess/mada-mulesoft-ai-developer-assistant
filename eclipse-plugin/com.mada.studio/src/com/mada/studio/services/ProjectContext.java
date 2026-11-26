
package com.mada.studio.services;

import java.util.Map;

public class ProjectContext {

    private final String projectName;
    private final Map<String, String> files;

    public ProjectContext(
            String projectName,
            Map<String, String> files) {

        this.projectName = projectName;
        this.files = files;
    }

    public String getProjectName() {
        return projectName;
    }

    public Map<String, String> getFiles() {
        return files;
    }

    public int getFileCount() {
        return files.size();
    }

    public String toPromptContext() {

        StringBuilder context = new StringBuilder();

        context.append("MULESOFT PROJECT CONTEXT\n");
        context.append("========================\n");

        context.append("Project: ")
               .append(projectName)
               .append("\n\n");

        for (Map.Entry<String, String> entry : files.entrySet()) {

            context.append("\nFILE: ")
                   .append(entry.getKey())
                   .append("\n");

            context.append("--------------------------------\n");

            context.append(entry.getValue());

            context.append("\n");
        }

        return context.toString();
    }
}
