package com.mada.studio.services;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;

import org.eclipse.core.resources.IFile;
import org.eclipse.core.resources.IProject;
import org.eclipse.core.resources.IResource;
import org.eclipse.core.resources.IResourceVisitor;
import org.eclipse.core.runtime.CoreException;

public class ProjectScanner {

    private static final long MAX_FILE_SIZE = 200 * 1024;
    private static final long MAX_TOTAL_SIZE = 1024 * 1024;

    private static final Set<String> ALLOWED_EXTENSIONS = Set.of(
        "xml",
        "raml",
        "dwl",
        "yaml",
        "yml",
        "properties"
    );

    private static final Set<String> EXCLUDED_FOLDERS = Set.of(
        "target",
        ".git",
        ".metadata",
        ".settings",
        "node_modules",
        "bin"
    );

    private static final Pattern SECRET_PATTERN = Pattern.compile(
        "(?im)(\\b(?:password|passwd|secret|client_secret|"
        + "client\\.secret|api_key|api\\.key|access_token|"
        + "refresh_token|authorization|private_key|"
        + "smtp\\.user|smtp\\.password)\\b"
        + "\\s*[:=]\\s*)(\"[^\"]*\"|'[^']*'|[^\\s,;]+)"
    );

    private long totalBytes = 0;

    /**
     * Scans a MuleSoft project and returns supported source files.
     *
     * This method is read-only. It does not modify project files.
     */
    public Map<String, String> scanProject(IProject project)
            throws CoreException {

        if (project == null || !project.exists()) {
            throw new IllegalArgumentException(
                "Invalid Eclipse project."
            );
        }

        if (!project.isOpen()) {
            throw new IllegalArgumentException(
                "Please open the project before scanning."
            );
        }

        Map<String, String> projectFiles = new LinkedHashMap<>();

        totalBytes = 0;

        project.accept(new IResourceVisitor() {

            @Override
            public boolean visit(IResource resource)
                    throws CoreException {

                // Skip excluded folders.
                if (resource.getType() == IResource.FOLDER) {

                    String folderName = resource.getName();

                    if (EXCLUDED_FOLDERS.contains(folderName)) {
                        return false;
                    }

                    return true;
                }

                if (resource.getType() != IResource.FILE) {
                    return true;
                }

                IFile file = (IFile) resource;

                if (!isSupportedFile(file)) {
                    return true;
                }

                long fileSize = file.getLocation().toFile().length();

                if (fileSize > MAX_FILE_SIZE) {
                    return true;
                }

                if (totalBytes + fileSize > MAX_TOTAL_SIZE) {
                    return false;
                }

                String content = readFile(file);

                if (content != null && !content.isBlank()) {

                    // Remove credentials before returning content.
                    content = redactSecrets(content);

                    String relativePath =
                        file.getProjectRelativePath().toString();

                    projectFiles.put(relativePath, content);

                    totalBytes += fileSize;
                }

                return true;
            }
        });

        return projectFiles;
    }

    /**
     * Checks whether a file is allowed for project analysis.
     */
    private boolean isSupportedFile(IFile file) {

        String fileName = file.getName().toLowerCase(Locale.ROOT);

        int dotIndex = fileName.lastIndexOf('.');

        if (dotIndex < 0) {
            return false;
        }

        String extension = fileName.substring(dotIndex + 1);

        return ALLOWED_EXTENSIONS.contains(extension);
    }

    /**
     * Reads a file using its Eclipse workspace character encoding.
     */
    private String readFile(IFile file) {

        try (InputStream input = file.getContents();
             ByteArrayOutputStream output =
                 new ByteArrayOutputStream()) {

            byte[] buffer = new byte[4096];

            int bytesRead;

            while ((bytesRead = input.read(buffer)) != -1) {
                output.write(buffer, 0, bytesRead);
            }

            String charset = file.getCharset();

            return output.toString(charset);

        } catch (Exception error) {

            System.err.println(
                "[MADA] Could not read file "
                + file.getName()
                + ": "
                + error.getMessage()
            );

            return null;
        }
    }

    /**
     * Redacts common secret values from project configuration.
     */
    private String redactSecrets(String content) {

        return SECRET_PATTERN.matcher(content)
            .replaceAll("$1[REDACTED]");
    }

    public long getTotalBytesScanned() {
        return totalBytes;
    }
}
