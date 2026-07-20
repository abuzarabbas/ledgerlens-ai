"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024;

    let latestPayload = null;

    const apiStatus = document.getElementById("api-status");
    const apiStatusText = document.getElementById("api-status-text");
    const connectionResult = document.getElementById(
        "connection-result"
    );
    const connectionButton = document.getElementById(
        "check-connection-button"
    );
    const reconciliationForm = document.getElementById(
        "reconciliation-form"
    );
    const providerSelect = document.getElementById(
        "provider-select"
    );
    const providerHelp = document.getElementById(
        "provider-help"
    );
    const runButton = document.getElementById(
        "run-reconciliation-button"
    );
    const resetButton = document.getElementById(
        "reset-form-button"
    );
    const runStatus = document.getElementById(
        "run-status"
    );
    const resultsPanel = document.getElementById(
        "results-panel"
    );
    const rawResponse = document.getElementById(
        "raw-response"
    );
    const statusFilter = document.getElementById(
        "status-filter"
    );
    const reviewTableBody = document.getElementById(
        "review-table-body"
    );
    const reviewDialog = document.getElementById(
        "review-dialog"
    );
    const dialogCloseButton = document.getElementById(
        "review-dialog-close"
    );
    const importMappingSection = document.getElementById(
        "import-mapping-section"
    );

    const importPreviewState = {
        invoices: {
            payload: null,
            selectedMapping: {},
            ready: false,
            error: null,
            requestId: 0,
        },
        payments: {
            payload: null,
            selectedMapping: {},
            ready: false,
            error: null,
            requestId: 0,
        },
        bank_transactions: {
            payload: null,
            selectedMapping: {},
            ready: false,
            error: null,
            requestId: 0,
        },
    };

    const fileFields = [
        {
            input: document.getElementById(
                "invoices-file"
            ),
            status: document.getElementById(
                "invoices-file-status"
            ),
            formKey: "invoices_file",
            datasetType: "invoices",
            uiPrefix: "invoices",
            label: "invoices",
        },
        {
            input: document.getElementById(
                "payments-file"
            ),
            status: document.getElementById(
                "payments-file-status"
            ),
            formKey: "payments_file",
            datasetType: "payments",
            uiPrefix: "payments",
            label: "payments",
        },
        {
            input: document.getElementById(
                "bank-transactions-file"
            ),
            status: document.getElementById(
                "bank-transactions-file-status"
            ),
            formKey: "bank_transactions_file",
            datasetType: "bank_transactions",
            uiPrefix: "bank-transactions",
            label: "bank transactions",
        },
    ];

    function formatFileSize(sizeInBytes) {
        if (sizeInBytes < 1024) {
            return `${sizeInBytes} bytes`;
        }

        if (sizeInBytes < 1024 * 1024) {
            return `${(
                sizeInBytes / 1024
            ).toFixed(1)} KB`;
        }

        return `${(
            sizeInBytes /
            (1024 * 1024)
        ).toFixed(1)} MB`;
    }

    function humanizeValue(value) {
        if (
            value === null ||
            value === undefined ||
            value === ""
        ) {
            return "—";
        }

        return String(value)
            .replaceAll("_", " ")
            .replace(
                /\b\w/g,
                (character) => {
                    return character.toUpperCase();
                }
            );
    }

    function formatIdentifierList(values) {
        if (
            !Array.isArray(values) ||
            values.length === 0
        ) {
            return "—";
        }

        return values.join(", ");
    }

    function setText(elementId, value) {
        const element = document.getElementById(
            elementId
        );

        if (element) {
            element.textContent = String(value);
        }
    }

    function validateFile(file) {
        if (!file) {
            return {
                valid: false,
                message: "No file selected",
            };
        }

        if (
            !file.name
                .toLowerCase()
                .endsWith(".csv")
        ) {
            return {
                valid: false,
                message:
                    "Only CSV files are allowed.",
            };
        }

        if (file.size === 0) {
            return {
                valid: false,
                message:
                    "The selected file is empty.",
            };
        }

        if (
            file.size >
            MAX_FILE_SIZE_BYTES
        ) {
            return {
                valid: false,
                message:
                    "The file exceeds the 10 MB limit.",
            };
        }

        return {
            valid: true,
            message:
                `${file.name} · ` +
                formatFileSize(file.size),
        };
    }

    function updateFileField(field) {
        const file =
            field.input.files[0];

        const validation =
            validateFile(file);

        field.status.textContent =
            validation.message;

        field.status.className =
            validation.valid
                ? "file-status file-status-valid"
                : "file-status file-status-invalid";

        return validation.valid;
    }

    function allFilesValid() {
        return fileFields.every((field) => {
            return validateFile(
                field.input.files[0]
            ).valid;
        });
    }

    function allMappingsReady() {
        return fileFields.every((field) => {
            return importPreviewState[
                field.datasetType
            ].ready;
        });
    }

    function updateRunButton() {
        const filesReady =
            allFilesValid();

        const mappingsReady =
            allMappingsReady();

        const ready =
            filesReady &&
            mappingsReady;

        runButton.disabled = !ready;

        if (!filesReady) {
            runStatus.className =
                "run-status";

            runStatus.textContent =
                "Select all three valid CSV files to continue.";

            return;
        }

        if (!mappingsReady) {
            runStatus.className =
                "run-status run-status-running";

            runStatus.textContent =
                "Review the CSV mappings. All three datasets must show Ready before reconciliation.";

            return;
        }

        runStatus.className =
            "run-status run-status-ready";

        runStatus.textContent =
            "All files and column mappings are ready. You can run reconciliation.";
    }

    function updateProviderHelp() {
        if (
            providerSelect.value ===
            "groq"
        ) {
            providerHelp.textContent =
                "Live Groq mode uses the private GROQ_API_KEY configured on the backend.";
        } else {
            providerHelp.textContent =
                "Mock mode requires no API key and produces repeatable decisions.";
        }
    }

    async function checkBackendConnection() {
        apiStatus.className =
            "status status-checking";

        apiStatusText.textContent =
            "Checking API";

        try {
            const response = await fetch(
                "/health",
                {
                    method: "GET",
                    headers: {
                        Accept:
                            "application/json",
                    },
                }
            );

            if (!response.ok) {
                throw new Error(
                    `HTTP ${response.status}`
                );
            }

            const payload =
                await response.json();

            apiStatus.className =
                "status status-connected";

            apiStatusText.textContent =
                "API connected";

            connectionResult.className =
                "connection-result " +
                "connection-result-success";

            connectionResult.textContent =
                "LedgerLens backend is available. " +
                JSON.stringify(payload);

            return true;
        } catch (error) {
            const message =
                error instanceof Error
                    ? error.message
                    : "Unknown error";

            apiStatus.className =
                "status status-error";

            apiStatusText.textContent =
                "API unavailable";

            connectionResult.className =
                "connection-result " +
                "connection-result-error";

            connectionResult.textContent =
                "Backend connection failed: " +
                message;

            return false;
        }
    }

    function getErrorMessage(
        payload,
        statusCode
    ) {
        if (
            typeof payload?.detail ===
            "string"
        ) {
            return payload.detail;
        }

        if (
            payload?.detail &&
            typeof payload.detail.message ===
                "string"
        ) {
            return payload.detail.message;
        }

        if (
            typeof payload?.message ===
            "string"
        ) {
            return payload.message;
        }

        return (
            `The API returned HTTP ` +
            `${statusCode}.`
        );
    }

    function setMappingSummaryStatus(
        field,
        message,
        statusType = ""
    ) {
        const element =
            document.getElementById(
                `${field.uiPrefix}` +
                "-mapping-summary-status"
            );

        element.textContent = message;

        element.className =
            "mapping-summary-status";

        if (statusType) {
            element.classList.add(
                "mapping-summary-status-" +
                statusType
            );
        }
    }

    function setMappingReadiness(
        field,
        message,
        readinessType = ""
    ) {
        const element =
            document.getElementById(
                `${field.uiPrefix}` +
                "-mapping-status"
            );

        element.textContent = message;

        element.className =
            "mapping-readiness";

        if (readinessType) {
            element.classList.add(
                "mapping-readiness-" +
                readinessType
            );
        }
    }

    function resetMappingCard(field) {
        const state =
            importPreviewState[
                field.datasetType
            ];

        state.requestId += 1;
        state.payload = null;
        state.selectedMapping = {};
        state.ready = false;
        state.error = null;

        setMappingSummaryStatus(
            field,
            "Waiting for file"
        );

        setMappingReadiness(
            field,
            `Select a ${field.label} CSV ` +
                "to generate suggestions."
        );

        setText(
            `${field.uiPrefix}` +
                "-preview-filename",
            "—"
        );

        setText(
            `${field.uiPrefix}` +
                "-preview-rows",
            "—"
        );

        setText(
            `${field.uiPrefix}` +
                "-preview-columns",
            "—"
        );

        setText(
            `${field.uiPrefix}` +
                "-preview-delimiter",
            "—"
        );

        setText(
            `${field.uiPrefix}` +
                "-preview-encoding",
            "—"
        );

        const warningsElement =
            document.getElementById(
                `${field.uiPrefix}` +
                "-preview-warnings"
            );

        warningsElement.hidden = true;
        warningsElement.innerHTML = "";

        const mappingBody =
            document.getElementById(
                `${field.uiPrefix}` +
                "-mapping-body"
            );

        mappingBody.innerHTML = `
            <tr>
                <td
                    colspan="4"
                    class="empty-table-message"
                >
                    No ${field.label}
                    preview available.
                </td>
            </tr>
        `;

        const previewHead =
            document.getElementById(
                `${field.uiPrefix}` +
                "-preview-head"
            );

        const previewBody =
            document.getElementById(
                `${field.uiPrefix}` +
                "-preview-body"
            );

        previewHead.innerHTML = "";

        previewBody.innerHTML = `
            <tr>
                <td class="empty-table-message">
                    No preview rows available.
                </td>
            </tr>
        `;

        updateRunButton();
    }

    function updateImportSectionVisibility() {
        const hasSelectedFile =
            fileFields.some((field) => {
                return Boolean(
                    field.input.files[0]
                );
            });

        importMappingSection.hidden =
            !hasSelectedFile;
    }

    function renderImportWarnings(
        field,
        warnings
    ) {
        const warningsElement =
            document.getElementById(
                `${field.uiPrefix}` +
                "-preview-warnings"
            );

        warningsElement.innerHTML = "";

        if (
            !Array.isArray(warnings) ||
            warnings.length === 0
        ) {
            warningsElement.hidden = true;
            return;
        }

        const list =
            document.createElement("ul");

        warnings.forEach((warning) => {
            const item =
                document.createElement("li");

            item.textContent = warning;
            list.appendChild(item);
        });

        warningsElement.appendChild(list);
        warningsElement.hidden = false;
    }

    function formatDelimiter(delimiter) {
        if (delimiter === "\t") {
            return "Tab";
        }

        if (delimiter === ";") {
            return "Semicolon (;)";
        }

        if (delimiter === "|") {
            return "Pipe (|)";
        }

        if (delimiter === ",") {
            return "Comma (,)";
        }

        return delimiter || "—";
    }

    function renderPreviewMetadata(
        field,
        payload
    ) {
        setText(
            `${field.uiPrefix}` +
                "-preview-filename",
            payload.filename || "—"
        );

        setText(
            `${field.uiPrefix}` +
                "-preview-rows",
            payload.row_count ?? 0
        );

        setText(
            `${field.uiPrefix}` +
                "-preview-columns",
            payload.column_count ?? 0
        );

        setText(
            `${field.uiPrefix}` +
                "-preview-delimiter",
            formatDelimiter(
                payload.delimiter
            )
        );

        setText(
            `${field.uiPrefix}` +
                "-preview-encoding",
            payload.encoding || "—"
        );

        renderImportWarnings(
            field,
            payload.warnings
        );
    }

    function renderDataPreview(
        field,
        payload
    ) {
        const previewHead =
            document.getElementById(
                `${field.uiPrefix}` +
                "-preview-head"
            );

        const previewBody =
            document.getElementById(
                `${field.uiPrefix}` +
                "-preview-body"
            );

        previewHead.innerHTML = "";
        previewBody.innerHTML = "";

        const columns =
            payload.source_columns || [];

        const rows =
            payload.preview_rows || [];

        if (columns.length === 0) {
            previewBody.innerHTML = `
                <tr>
                    <td class="empty-table-message">
                        No preview columns available.
                    </td>
                </tr>
            `;

            return;
        }

        const headingRow =
            document.createElement("tr");

        columns.forEach((column) => {
            const heading =
                document.createElement("th");

            heading.scope = "col";
            heading.textContent = column;

            headingRow.appendChild(
                heading
            );
        });

        previewHead.appendChild(
            headingRow
        );

        if (rows.length === 0) {
            const row =
                document.createElement("tr");

            const cell =
                document.createElement("td");

            cell.colSpan = columns.length;

            cell.className =
                "empty-table-message";

            cell.textContent =
                "The CSV contains no preview rows.";

            row.appendChild(cell);
            previewBody.appendChild(row);

            return;
        }

        rows.forEach((previewRecord) => {
            const row =
                document.createElement("tr");

            columns.forEach((column) => {
                const cell =
                    document.createElement("td");

                const value =
                    previewRecord[column];

                cell.textContent =
                    value === null ||
                    value === undefined ||
                    value === ""
                        ? "—"
                        : String(value);

                row.appendChild(cell);
            });

            previewBody.appendChild(row);
        });
    }

    function findDuplicateMappings(
        selectedMapping
    ) {
        const selectedSources =
            Object.values(
                selectedMapping
            ).filter(Boolean);

        return [
            ...new Set(
                selectedSources.filter(
                    (sourceColumn) => {
                        return (
                            selectedSources.filter(
                                (candidate) => {
                                    return (
                                        candidate ===
                                        sourceColumn
                                    );
                                }
                            ).length > 1
                        );
                    }
                )
            ),
        ];
    }

    function updateMappingReadiness(
        field
    ) {
        const state =
            importPreviewState[
                field.datasetType
            ];

        if (!state.payload) {
            state.ready = false;
            updateRunButton();
            return;
        }

        const requiredFields =
            state.payload.mapping
                ?.required_fields || [];

        const missingRequiredFields =
            requiredFields.filter(
                (canonicalField) => {
                    return !state
                        .selectedMapping[
                        canonicalField
                    ];
                }
            );

        const duplicateSources =
            findDuplicateMappings(
                state.selectedMapping
            );

        if (
            missingRequiredFields.length >
            0
        ) {
            state.ready = false;

            setMappingSummaryStatus(
                field,
                `${missingRequiredFields.length} ` +
                    "required missing",
                "warning"
            );

            setMappingReadiness(
                field,
                "Required fields still need a " +
                    "source column: " +
                    missingRequiredFields
                        .map(humanizeValue)
                        .join(", ") +
                    ".",
                "warning"
            );

            updateRunButton();
            return;
        }

        if (
            duplicateSources.length > 0
        ) {
            state.ready = false;

            setMappingSummaryStatus(
                field,
                "Duplicate mapping",
                "warning"
            );

            setMappingReadiness(
                field,
                "A source column cannot be " +
                    "assigned to multiple LedgerLens fields: " +
                    duplicateSources.join(", ") +
                    ".",
                "warning"
            );

            updateRunButton();
            return;
        }

        state.ready = true;

        setMappingSummaryStatus(
            field,
            "Ready",
            "ready"
        );

        setMappingReadiness(
            field,
            "All required fields are mapped and ready " +
                "for normalization and reconciliation.",
            "ready"
        );

        updateRunButton();
    }

    function updateMappingConfidenceCell(
        selectElement,
        confidenceCell,
        suggestedSource,
        suggestedConfidence
    ) {
        if (!selectElement.value) {
            confidenceCell.textContent =
                "Not mapped";

            return;
        }

        if (
            selectElement.value ===
            suggestedSource
        ) {
            confidenceCell.textContent =
                `${Math.round(
                    suggestedConfidence * 100
                )}% suggested`;

            return;
        }

        confidenceCell.textContent =
            "Manual selection";
    }

    function renderMappingTable(
        field,
        payload
    ) {
        const mappingBody =
            document.getElementById(
                `${field.uiPrefix}` +
                "-mapping-body"
            );

        mappingBody.innerHTML = "";

        const mappingPayload =
            payload.mapping || {};

        const canonicalFields =
            mappingPayload.canonical_fields ||
            [];

        const sourceColumns =
            payload.source_columns || [];

        const requiredFieldSet =
            new Set(
                mappingPayload.required_fields ||
                    []
            );

        const suggestedMapping =
            mappingPayload
                .suggested_mapping || {};

        const mappingConfidence =
            mappingPayload
                .mapping_confidence || {};

        const state =
            importPreviewState[
                field.datasetType
            ];

        state.selectedMapping = {
            ...suggestedMapping,
        };

        canonicalFields.forEach(
            (canonicalField) => {
                const row =
                    document.createElement(
                        "tr"
                    );

                const nameCell =
                    document.createElement(
                        "td"
                    );

                nameCell.className =
                    "mapping-field-name";

                nameCell.textContent =
                    humanizeValue(
                        canonicalField
                    );

                const requirementCell =
                    document.createElement(
                        "td"
                    );

                const requirementBadge =
                    document.createElement(
                        "span"
                    );

                const isRequired =
                    requiredFieldSet.has(
                        canonicalField
                    );

                requirementBadge.className =
                    isRequired
                        ? "mapping-required-badge"
                        : "mapping-optional-badge";

                requirementBadge.textContent =
                    isRequired
                        ? "Required"
                        : "Optional";

                requirementCell.appendChild(
                    requirementBadge
                );

                const selectCell =
                    document.createElement(
                        "td"
                    );

                const select =
                    document.createElement(
                        "select"
                    );

                select.className =
                    "mapping-select";

                select.dataset.canonicalField =
                    canonicalField;

                const emptyOption =
                    document.createElement(
                        "option"
                    );

                emptyOption.value = "";

                emptyOption.textContent =
                    isRequired
                        ? "Select source column"
                        : "Not mapped";

                select.appendChild(
                    emptyOption
                );

                sourceColumns.forEach(
                    (sourceColumn) => {
                        const option =
                            document.createElement(
                                "option"
                            );

                        option.value =
                            sourceColumn;

                        option.textContent =
                            sourceColumn;

                        select.appendChild(
                            option
                        );
                    }
                );

                const suggestedSource =
                    suggestedMapping[
                        canonicalField
                    ] || "";

                select.value =
                    suggestedSource;

                selectCell.appendChild(
                    select
                );

                const confidenceCell =
                    document.createElement(
                        "td"
                    );

                confidenceCell.className =
                    "mapping-confidence";

                const suggestedConfidence =
                    Number(
                        mappingConfidence[
                            canonicalField
                        ] || 0
                    );

                updateMappingConfidenceCell(
                    select,
                    confidenceCell,
                    suggestedSource,
                    suggestedConfidence
                );

                select.addEventListener(
                    "change",
                    () => {
                        state.selectedMapping[
                            canonicalField
                        ] =
                            select.value ||
                            null;

                        updateMappingConfidenceCell(
                            select,
                            confidenceCell,
                            suggestedSource,
                            suggestedConfidence
                        );

                        updateMappingReadiness(
                            field
                        );
                    }
                );

                row.appendChild(nameCell);

                row.appendChild(
                    requirementCell
                );

                row.appendChild(
                    selectCell
                );

                row.appendChild(
                    confidenceCell
                );

                mappingBody.appendChild(
                    row
                );
            }
        );

        updateMappingReadiness(field);
    }

    function renderPreviewError(
        field,
        message
    ) {
        const state =
            importPreviewState[
                field.datasetType
            ];

        state.payload = null;
        state.selectedMapping = {};
        state.ready = false;
        state.error = message;

        setMappingSummaryStatus(
            field,
            "Preview failed",
            "error"
        );

        setMappingReadiness(
            field,
            message,
            "error"
        );

        setText(
            `${field.uiPrefix}` +
                "-preview-filename",
            field.input.files[0]?.name ||
                "—"
        );

        setText(
            `${field.uiPrefix}` +
                "-preview-rows",
            "—"
        );

        setText(
            `${field.uiPrefix}` +
                "-preview-columns",
            "—"
        );

        setText(
            `${field.uiPrefix}` +
                "-preview-delimiter",
            "—"
        );

        setText(
            `${field.uiPrefix}` +
                "-preview-encoding",
            "—"
        );

        const warningsElement =
            document.getElementById(
                `${field.uiPrefix}` +
                "-preview-warnings"
            );

        warningsElement.hidden = true;
        warningsElement.innerHTML = "";

        const mappingBody =
            document.getElementById(
                `${field.uiPrefix}` +
                "-mapping-body"
            );

        mappingBody.innerHTML = `
            <tr>
                <td
                    colspan="4"
                    class="empty-table-message"
                >
                    CSV preview could not be generated.
                </td>
            </tr>
        `;

        const previewHead =
            document.getElementById(
                `${field.uiPrefix}` +
                "-preview-head"
            );

        const previewBody =
            document.getElementById(
                `${field.uiPrefix}` +
                "-preview-body"
            );

        previewHead.innerHTML = "";

        previewBody.innerHTML = `
            <tr>
                <td class="empty-table-message">
                    No preview rows available.
                </td>
            </tr>
        `;

        updateRunButton();
    }

    async function previewCsvImport(
        field
    ) {
        const file =
            field.input.files[0];

        const validation =
            validateFile(file);

        if (!validation.valid) {
            resetMappingCard(field);
            updateImportSectionVisibility();
            return;
        }

        importMappingSection.hidden = false;

        const mappingCard =
            document.getElementById(
                `${field.uiPrefix}` +
                "-mapping-card"
            );

        mappingCard.open = true;

        const state =
            importPreviewState[
                field.datasetType
            ];

        state.requestId += 1;

        const currentRequestId =
            state.requestId;

        state.payload = null;
        state.selectedMapping = {};
        state.ready = false;
        state.error = null;

        setMappingSummaryStatus(
            field,
            "Loading preview",
            "loading"
        );

        setMappingReadiness(
            field,
            "Reading CSV headers and generating mapping suggestions."
        );

        updateRunButton();

        const formData =
            new FormData();

        formData.append(
            "file",
            file
        );

        try {
            const response = await fetch(
                `/import/preview/` +
                    field.datasetType,
                {
                    method: "POST",
                    body: formData,
                    headers: {
                        Accept:
                            "application/json",
                    },
                }
            );

            const responseText =
                await response.text();

            let payload;

            try {
                payload =
                    JSON.parse(
                        responseText
                    );
            } catch {
                payload = {
                    message:
                        responseText,
                };
            }

            if (
                currentRequestId !==
                state.requestId
            ) {
                return;
            }

            if (!response.ok) {
                throw new Error(
                    getErrorMessage(
                        payload,
                        response.status
                    )
                );
            }

            state.payload = payload;
            state.error = null;

            renderPreviewMetadata(
                field,
                payload
            );

            renderMappingTable(
                field,
                payload
            );

            renderDataPreview(
                field,
                payload
            );
        } catch (error) {
            if (
                currentRequestId !==
                state.requestId
            ) {
                return;
            }

            const message =
                error instanceof Error
                    ? error.message
                    : "Unexpected preview error";

            renderPreviewError(
                field,
                message
            );
        }
    }

    async function normalizeDataset(
        field
    ) {
        const state =
            importPreviewState[
                field.datasetType
            ];

        if (!state.ready) {
            throw new Error(
                `${humanizeValue(
                    field.datasetType
                )} mapping is not ready.`
            );
        }

        const sourceFile =
            field.input.files[0];

        const normalizationForm =
            new FormData();

        normalizationForm.append(
            "file",
            sourceFile
        );

        normalizationForm.append(
            "mapping_json",
            JSON.stringify(
                state.selectedMapping
            )
        );

        const response = await fetch(
            `/import/normalize/` +
                field.datasetType,
            {
                method: "POST",
                body: normalizationForm,
                headers: {
                    Accept:
                        "application/json",
                },
            }
        );

        const responseText =
            await response.text();

        let payload;

        try {
            payload =
                JSON.parse(
                    responseText
                );
        } catch {
            payload = {
                message:
                    responseText,
            };
        }

        if (!response.ok) {
            throw new Error(
                getErrorMessage(
                    payload,
                    response.status
                )
            );
        }

        if (
            typeof payload.normalized_csv !==
            "string"
        ) {
            throw new Error(
                "The normalization API did not return a valid CSV."
            );
        }

        return new File(
            [payload.normalized_csv],
            payload.normalized_filename ||
                `${field.datasetType}-normalized.csv`,
            {
                type: "text/csv",
            }
        );
    }

    function getConfidenceClass(score) {
        const numericScore =
            Number(score) || 0;

        if (numericScore >= 90) {
            return "confidence-high";
        }

        if (numericScore >= 70) {
            return "confidence-medium";
        }

        return "confidence-low";
    }

    function createTextCell(
        text,
        className = ""
    ) {
        const cell =
            document.createElement("td");

        cell.textContent = text;

        if (className) {
            cell.className =
                className;
        }

        return cell;
    }

    function createBadgeCell(
        text,
        className
    ) {
        const cell =
            document.createElement("td");

        const badge =
            document.createElement(
                "span"
            );

        badge.className =
            className;

        badge.textContent = text;

        cell.appendChild(badge);

        return cell;
    }

    function getAiDecisionMap(payload) {
        const decisions =
            payload?.ai_analysis
                ?.decisions || [];

        return new Map(
            decisions.map((record) => {
                return [
                    record.invoice_id,
                    record,
                ];
            })
        );
    }

    function renderReviewTable(payload) {
        const results =
            payload?.reconciliation
                ?.results || [];

        const selectedStatus =
            statusFilter.value;

        const aiDecisionMap =
            getAiDecisionMap(payload);

        const filteredResults =
            selectedStatus === "all"
                ? results
                : results.filter(
                    (result) => {
                        return (
                            result.status ===
                            selectedStatus
                        );
                    }
                );

        reviewTableBody.innerHTML = "";

        if (
            filteredResults.length === 0
        ) {
            const row =
                document.createElement(
                    "tr"
                );

            const cell =
                document.createElement(
                    "td"
                );

            cell.colSpan = 8;

            cell.className =
                "empty-table-message";

            cell.textContent =
                "No reconciliation records match this filter.";

            row.appendChild(cell);

            reviewTableBody.appendChild(
                row
            );

            return;
        }

        filteredResults.forEach(
            (result) => {
                const row =
                    document.createElement(
                        "tr"
                    );

                const aiRecord =
                    aiDecisionMap.get(
                        result.invoice_id
                    );

                const recommendation =
                    aiRecord?.decision
                        ?.recommendation;

                const status =
                    result.status ||
                    "unmatched";

                const confidenceScore =
                    Number(
                        result.confidence_score
                    ) || 0;

                row.appendChild(
                    createTextCell(
                        result.invoice_id ||
                            "—"
                    )
                );

                row.appendChild(
                    createBadgeCell(
                        humanizeValue(
                            status
                        ),
                        "status-badge " +
                            `status-${String(
                                status
                            ).replaceAll(
                                "_",
                                "-"
                            )}`
                    )
                );

                row.appendChild(
                    createBadgeCell(
                        `${confidenceScore}%`,
                        "confidence-badge " +
                            getConfidenceClass(
                                confidenceScore
                            )
                    )
                );

                row.appendChild(
                    createTextCell(
                        formatIdentifierList(
                            result.payment_ids
                        ),
                        "table-id-list"
                    )
                );

                row.appendChild(
                    createTextCell(
                        formatIdentifierList(
                            result
                                .transaction_ids
                        ),
                        "table-id-list"
                    )
                );

                row.appendChild(
                    createTextCell(
                        humanizeValue(
                            result
                                .matching_method
                        )
                    )
                );

                if (recommendation) {
                    row.appendChild(
                        createBadgeCell(
                            humanizeValue(
                                recommendation
                            ),
                            "recommendation-badge " +
                                `recommendation-${recommendation.replaceAll(
                                    "_",
                                    "-"
                                )}`
                        )
                    );
                } else {
                    row.appendChild(
                        createTextCell(
                            "Not sent to AI",
                            "no-ai-review"
                        )
                    );
                }

                const detailsCell =
                    document.createElement(
                        "td"
                    );

                const detailsButton =
                    document.createElement(
                        "button"
                    );

                detailsButton.type =
                    "button";

                detailsButton.className =
                    "review-details-button";

                detailsButton.textContent =
                    "View";

                detailsButton.dataset.invoiceId =
                    result.invoice_id ||
                    "";

                detailsCell.appendChild(
                    detailsButton
                );

                row.appendChild(
                    detailsCell
                );

                reviewTableBody.appendChild(
                    row
                );
            }
        );
    }

    function setDialogValue(
        elementId,
        value
    ) {
        const element =
            document.getElementById(
                elementId
            );

        if (element) {
            element.textContent = value;
        }
    }

    function openReviewDialog(
        invoiceId
    ) {
        if (!latestPayload) {
            return;
        }

        const results =
            latestPayload
                ?.reconciliation
                ?.results || [];

        const result =
            results.find((record) => {
                return (
                    record.invoice_id ===
                    invoiceId
                );
            });

        if (!result) {
            return;
        }

        const aiRecord =
            getAiDecisionMap(
                latestPayload
            ).get(invoiceId);

        setDialogValue(
            "detail-invoice-id",
            result.invoice_id || "—"
        );

        setDialogValue(
            "detail-status",
            humanizeValue(
                result.status
            )
        );

        setDialogValue(
            "detail-confidence",
            `${Number(
                result.confidence_score
            ) || 0}%`
        );

        setDialogValue(
            "detail-method",
            humanizeValue(
                result.matching_method
            )
        );

        setDialogValue(
            "detail-payments",
            formatIdentifierList(
                result.payment_ids
            )
        );

        setDialogValue(
            "detail-transactions",
            formatIdentifierList(
                result.transaction_ids
            )
        );

        setDialogValue(
            "detail-deterministic-explanation",
            result.explanation ||
                "No explanation provided."
        );

        setDialogValue(
            "detail-supporting-signals",
            formatIdentifierList(
                result.supporting_signals
            )
        );

        setDialogValue(
            "detail-conflicts",
            formatIdentifierList(
                result.conflicts
            )
        );

        if (aiRecord?.decision) {
            const decision =
                aiRecord.decision;

            setDialogValue(
                "detail-ai-recommendation",
                humanizeValue(
                    decision.recommendation
                )
            );

            setDialogValue(
                "detail-ai-confidence",
                `${Number(
                    decision.confidence_score
                ) || 0}%`
            );

            setDialogValue(
                "detail-human-review",
                decision
                    .requires_human_review
                    ? "Required"
                    : "Not required"
            );

            setDialogValue(
                "detail-ai-explanation",
                decision.explanation ||
                    "No AI explanation provided."
            );
        } else {
            setDialogValue(
                "detail-ai-recommendation",
                "Not sent to AI"
            );

            setDialogValue(
                "detail-ai-confidence",
                "Not applicable"
            );

            setDialogValue(
                "detail-human-review",
                "Not applicable"
            );

            setDialogValue(
                "detail-ai-explanation",
                "This record was deterministically confirmed and was not sent for AI review."
            );
        }

        reviewDialog.showModal();
    }

    function updateResults(payload) {
        latestPayload = payload;

        const reconciliation =
            payload.reconciliation || {};

        const counts =
            reconciliation.status_counts ||
            {};

        const aiAnalysis =
            payload.ai_analysis || {};

        setText(
            "summary-total",
            reconciliation
                .total_invoices || 0
        );

        setText(
            "summary-confirmed",
            counts.confirmed || 0
        );

        setText(
            "summary-review",
            counts.review || 0
        );

        setText(
            "summary-duplicate",
            counts.duplicate_review || 0
        );

        setText(
            "summary-unmatched",
            counts.unmatched || 0
        );

        setText(
            "summary-ai-candidates",
            aiAnalysis.total_candidates || 0
        );

        setText(
            "result-analysis-mode",
            aiAnalysis.analysis_mode ||
                "unknown"
        );

        setText(
            "result-model-name",
            aiAnalysis.model_name ||
                "unknown"
        );

        setText(
            "result-provider-badge",
            aiAnalysis.analysis_mode ===
                "groq"
                ? "Live Groq"
                : "Mock AI"
        );

        rawResponse.textContent =
            JSON.stringify(
                payload,
                null,
                2
            );

        statusFilter.value = "all";

        renderReviewTable(payload);

        resultsPanel.hidden = false;

        resultsPanel.scrollIntoView({
            behavior: "smooth",
            block: "start",
        });
    }

    async function submitReconciliation(
        event
    ) {
        event.preventDefault();

        if (!allFilesValid()) {
            runStatus.className =
                "run-status run-status-error";

            runStatus.textContent =
                "Select all three valid CSV files.";

            return;
        }

        if (!allMappingsReady()) {
            runStatus.className =
                "run-status run-status-error";

            runStatus.textContent =
                "All three mappings must show Ready before reconciliation.";

            return;
        }

        const backendAvailable =
            await checkBackendConnection();

        if (!backendAvailable) {
            runStatus.className =
                "run-status run-status-error";

            runStatus.textContent =
                "The backend is unavailable.";

            return;
        }

        const provider =
            providerSelect.value;

        const endpoint =
            `/analyze/${provider}`;

        runButton.disabled = true;
        resetButton.disabled = true;

        runButton.textContent =
            "Normalizing CSV files...";

        runStatus.className =
            "run-status run-status-running";

        runStatus.textContent =
            "Applying the selected column mappings.";

        resultsPanel.hidden = true;

        try {
            const normalizedFiles =
                await Promise.all(
                    fileFields.map(
                        (field) => {
                            return normalizeDataset(
                                field
                            );
                        }
                    )
                );

            const reconciliationFormData =
                new FormData();

            fileFields.forEach(
                (field, index) => {
                    reconciliationFormData.append(
                        field.formKey,
                        normalizedFiles[
                            index
                        ]
                    );
                }
            );

            runButton.textContent =
                provider === "groq"
                    ? "Running Groq analysis..."
                    : "Running mock analysis...";

            runStatus.textContent =
                "Normalization completed. Running deterministic reconciliation and AI review.";

            const response = await fetch(
                endpoint,
                {
                    method: "POST",
                    body:
                        reconciliationFormData,
                    headers: {
                        Accept:
                            "application/json",
                    },
                }
            );

            const responseText =
                await response.text();

            let payload;

            try {
                payload =
                    JSON.parse(
                        responseText
                    );
            } catch {
                payload = {
                    message:
                        responseText,
                };
            }

            if (!response.ok) {
                throw new Error(
                    getErrorMessage(
                        payload,
                        response.status
                    )
                );
            }

            updateResults(payload);

            runStatus.className =
                "run-status run-status-success";

            runStatus.textContent =
                "CSV normalization and reconciliation completed successfully.";
        } catch (error) {
            const message =
                error instanceof Error
                    ? error.message
                    : "Unexpected error";

            runStatus.className =
                "run-status run-status-error";

            runStatus.textContent =
                "Processing failed: " +
                message;
        } finally {
            resetButton.disabled = false;

            runButton.textContent =
                "Run reconciliation";

            runButton.disabled = !(
                allFilesValid() &&
                allMappingsReady()
            );
        }
    }

    function resetForm() {
        reconciliationForm.reset();

        latestPayload = null;

        fileFields.forEach((field) => {
            field.status.className =
                "file-status";

            field.status.textContent =
                "No file selected";

            resetMappingCard(field);
        });

        importMappingSection.hidden =
            true;

        providerSelect.value = "mock";
        statusFilter.value = "all";

        updateProviderHelp();

        resultsPanel.hidden = true;
        rawResponse.textContent = "";

        reviewTableBody.innerHTML = `
            <tr>
                <td
                    colspan="8"
                    class="empty-table-message"
                >
                    Run reconciliation to view
                    invoice-level results.
                </td>
            </tr>
        `;

        updateRunButton();
    }

    fileFields.forEach((field) => {
        field.input.addEventListener(
            "change",
            () => {
                const valid =
                    updateFileField(
                        field
                    );

                resetMappingCard(field);

                updateImportSectionVisibility();

                if (valid) {
                    previewCsvImport(
                        field
                    );
                }
            }
        );
    });

    providerSelect.addEventListener(
        "change",
        updateProviderHelp
    );

    statusFilter.addEventListener(
        "change",
        () => {
            if (latestPayload) {
                renderReviewTable(
                    latestPayload
                );
            }
        }
    );

    reviewTableBody.addEventListener(
        "click",
        (event) => {
            const target =
                event.target instanceof
                Element
                    ? event.target
                    : null;

            const button =
                target?.closest(
                    ".review-details-button"
                );

            if (!button) {
                return;
            }

            openReviewDialog(
                button.dataset.invoiceId
            );
        }
    );

    dialogCloseButton.addEventListener(
        "click",
        () => {
            reviewDialog.close();
        }
    );

    reviewDialog.addEventListener(
        "click",
        (event) => {
            if (
                event.target ===
                reviewDialog
            ) {
                reviewDialog.close();
            }
        }
    );

    reconciliationForm.addEventListener(
        "submit",
        submitReconciliation
    );

    resetButton.addEventListener(
        "click",
        resetForm
    );

    connectionButton.addEventListener(
        "click",
        checkBackendConnection
    );

    fileFields.forEach(
        resetMappingCard
    );

    updateImportSectionVisibility();
    updateProviderHelp();
    updateRunButton();
    checkBackendConnection();
});