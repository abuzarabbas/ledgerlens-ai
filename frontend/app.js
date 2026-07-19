"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024;

    let latestPayload = null;

    const apiStatus = document.getElementById("api-status");
    const apiStatusText = document.getElementById(
        "api-status-text"
    );

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

    const fileFields = [
        {
            input: document.getElementById(
                "invoices-file"
            ),
            status: document.getElementById(
                "invoices-file-status"
            ),
            formKey: "invoices_file",
        },
        {
            input: document.getElementById(
                "payments-file"
            ),
            status: document.getElementById(
                "payments-file-status"
            ),
            formKey: "payments_file",
        },
        {
            input: document.getElementById(
                "bank-transactions-file"
            ),
            status: document.getElementById(
                "bank-transactions-file-status"
            ),
            formKey: "bank_transactions_file",
        },
    ];

    function formatFileSize(sizeInBytes) {
        if (sizeInBytes < 1024) {
            return `${sizeInBytes} bytes`;
        }

        if (sizeInBytes < 1024 * 1024) {
            return `${(sizeInBytes / 1024).toFixed(1)} KB`;
        }

        return `${(
            sizeInBytes /
            (1024 * 1024)
        ).toFixed(1)} MB`;
    }

    function humanizeValue(value) {
        if (!value) {
            return "—";
        }

        return String(value)
            .replaceAll("_", " ")
            .replace(/\b\w/g, (character) => {
                return character.toUpperCase();
            });
    }

    function formatIdentifierList(values) {
        if (!Array.isArray(values) || values.length === 0) {
            return "—";
        }

        return values.join(", ");
    }

    function validateFile(file) {
        if (!file) {
            return {
                valid: false,
                message: "No file selected",
            };
        }

        if (!file.name.toLowerCase().endsWith(".csv")) {
            return {
                valid: false,
                message: "Only CSV files are allowed.",
            };
        }

        if (file.size === 0) {
            return {
                valid: false,
                message: "The selected file is empty.",
            };
        }

        if (file.size > MAX_FILE_SIZE_BYTES) {
            return {
                valid: false,
                message: "The file exceeds the 10 MB limit.",
            };
        }

        return {
            valid: true,
            message:
                `${file.name} · ${formatFileSize(file.size)}`,
        };
    }

    function updateFileField(field) {
        const file = field.input.files[0];
        const validation = validateFile(file);

        field.status.textContent = validation.message;

        field.status.className = validation.valid
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

    function updateRunButton() {
        const ready = allFilesValid();

        runButton.disabled = !ready;

        if (ready) {
            runStatus.className =
                "run-status run-status-ready";

            runStatus.textContent =
                "All three CSV files are ready. " +
                "You can run reconciliation.";
        } else {
            runStatus.className = "run-status";

            runStatus.textContent =
                "Select all three valid CSV files to continue.";
        }
    }

    function updateProviderHelp() {
        if (providerSelect.value === "groq") {
            providerHelp.textContent =
                "Live Groq mode uses the private " +
                "GROQ_API_KEY configured on the backend.";
        } else {
            providerHelp.textContent =
                "Mock mode requires no API key and " +
                "produces repeatable decisions.";
        }
    }

    async function checkBackendConnection() {
        apiStatus.className =
            "status status-checking";

        apiStatusText.textContent =
            "Checking API";

        try {
            const response = await fetch("/health", {
                method: "GET",
                headers: {
                    Accept: "application/json",
                },
            });

            if (!response.ok) {
                throw new Error(
                    `HTTP ${response.status}`
                );
            }

            const payload = await response.json();

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
                `Backend connection failed: ${message}`;

            return false;
        }
    }

    function getErrorMessage(payload, statusCode) {
        if (typeof payload.detail === "string") {
            return payload.detail;
        }

        if (
            payload.detail &&
            typeof payload.detail.message === "string"
        ) {
            return payload.detail.message;
        }

        if (typeof payload.message === "string") {
            return payload.message;
        }

        return `The API returned HTTP ${statusCode}.`;
    }

    function getConfidenceClass(score) {
        if (score >= 90) {
            return "confidence-high";
        }

        if (score >= 70) {
            return "confidence-medium";
        }

        return "confidence-low";
    }

    function createTextCell(text, className = "") {
        const cell = document.createElement("td");

        cell.textContent = text;

        if (className) {
            cell.className = className;
        }

        return cell;
    }

    function createBadgeCell(text, className) {
        const cell = document.createElement("td");
        const badge = document.createElement("span");

        badge.className = className;
        badge.textContent = text;

        cell.appendChild(badge);

        return cell;
    }

    function getAiDecisionMap(payload) {
        const decisions =
            payload.ai_analysis?.decisions || [];

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
            payload?.reconciliation?.results || [];

        const selectedStatus =
            statusFilter.value;

        const aiDecisionMap =
            getAiDecisionMap(payload);

        const filteredResults =
            selectedStatus === "all"
                ? results
                : results.filter((result) => {
                    return result.status === selectedStatus;
                });

        reviewTableBody.innerHTML = "";

        if (filteredResults.length === 0) {
            const row = document.createElement("tr");
            const cell = document.createElement("td");

            cell.colSpan = 8;
            cell.className = "empty-table-message";
            cell.textContent =
                "No reconciliation records match this filter.";

            row.appendChild(cell);
            reviewTableBody.appendChild(row);

            return;
        }

        filteredResults.forEach((result) => {
            const row = document.createElement("tr");

            const aiRecord =
                aiDecisionMap.get(result.invoice_id);

            const recommendation =
                aiRecord?.decision?.recommendation;

            row.appendChild(
                createTextCell(result.invoice_id)
            );

            row.appendChild(
                createBadgeCell(
                    humanizeValue(result.status),
                    "status-badge " +
                    `status-${result.status.replaceAll("_", "-")}`
                )
            );

            row.appendChild(
                createBadgeCell(
                    `${result.confidence_score}%`,
                    "confidence-badge " +
                    getConfidenceClass(
                        result.confidence_score
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
                        result.transaction_ids
                    ),
                    "table-id-list"
                )
            );

            row.appendChild(
                createTextCell(
                    humanizeValue(
                        result.matching_method
                    )
                )
            );

            if (recommendation) {
                row.appendChild(
                    createBadgeCell(
                        humanizeValue(recommendation),
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
                document.createElement("td");

            const detailsButton =
                document.createElement("button");

            detailsButton.type = "button";
            detailsButton.className =
                "review-details-button";
            detailsButton.textContent = "View";
            detailsButton.dataset.invoiceId =
                result.invoice_id;

            detailsCell.appendChild(detailsButton);
            row.appendChild(detailsCell);

            reviewTableBody.appendChild(row);
        });
    }

    function setDialogValue(elementId, value) {
        document.getElementById(
            elementId
        ).textContent = value;
    }

    function openReviewDialog(invoiceId) {
        if (!latestPayload) {
            return;
        }

        const result =
            latestPayload.reconciliation.results.find(
                (record) => {
                    return record.invoice_id === invoiceId;
                }
            );

        if (!result) {
            return;
        }

        const aiRecord =
            getAiDecisionMap(latestPayload).get(
                invoiceId
            );

        setDialogValue(
            "detail-invoice-id",
            result.invoice_id
        );

        setDialogValue(
            "detail-status",
            humanizeValue(result.status)
        );

        setDialogValue(
            "detail-confidence",
            `${result.confidence_score}%`
        );

        setDialogValue(
            "detail-method",
            humanizeValue(result.matching_method)
        );

        setDialogValue(
            "detail-payments",
            formatIdentifierList(result.payment_ids)
        );

        setDialogValue(
            "detail-transactions",
            formatIdentifierList(
                result.transaction_ids
            )
        );

        setDialogValue(
            "detail-deterministic-explanation",
            result.explanation || "No explanation provided."
        );

        setDialogValue(
            "detail-supporting-signals",
            formatIdentifierList(
                result.supporting_signals
            )
        );

        setDialogValue(
            "detail-conflicts",
            formatIdentifierList(result.conflicts)
        );

        if (aiRecord) {
            const decision = aiRecord.decision;

            setDialogValue(
                "detail-ai-recommendation",
                humanizeValue(
                    decision.recommendation
                )
            );

            setDialogValue(
                "detail-ai-confidence",
                `${decision.confidence_score}%`
            );

            setDialogValue(
                "detail-human-review",
                decision.requires_human_review
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
                "This record was deterministically confirmed " +
                "and was not sent for AI review."
            );
        }

        reviewDialog.showModal();
    }

    function updateResults(payload) {
        latestPayload = payload;

        const reconciliation =
            payload.reconciliation || {};

        const counts =
            reconciliation.status_counts || {};

        const aiAnalysis =
            payload.ai_analysis || {};

        document.getElementById(
            "summary-total"
        ).textContent =
            reconciliation.total_invoices || 0;

        document.getElementById(
            "summary-confirmed"
        ).textContent =
            counts.confirmed || 0;

        document.getElementById(
            "summary-review"
        ).textContent =
            counts.review || 0;

        document.getElementById(
            "summary-duplicate"
        ).textContent =
            counts.duplicate_review || 0;

        document.getElementById(
            "summary-unmatched"
        ).textContent =
            counts.unmatched || 0;

        document.getElementById(
            "summary-ai-candidates"
        ).textContent =
            aiAnalysis.total_candidates || 0;

        document.getElementById(
            "result-analysis-mode"
        ).textContent =
            aiAnalysis.analysis_mode || "unknown";

        document.getElementById(
            "result-model-name"
        ).textContent =
            aiAnalysis.model_name || "unknown";

        document.getElementById(
            "result-provider-badge"
        ).textContent =
            aiAnalysis.analysis_mode === "groq"
                ? "Live Groq"
                : "Mock AI";

        rawResponse.textContent =
            JSON.stringify(payload, null, 2);

        statusFilter.value = "all";
        renderReviewTable(payload);

        resultsPanel.hidden = false;

        resultsPanel.scrollIntoView({
            behavior: "smooth",
            block: "start",
        });
    }

    async function submitReconciliation(event) {
        event.preventDefault();

        if (!allFilesValid()) {
            runStatus.className =
                "run-status run-status-error";

            runStatus.textContent =
                "Select all three valid CSV files.";

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

        const provider = providerSelect.value;
        const endpoint = `/analyze/${provider}`;

        const formData = new FormData();

        fileFields.forEach((field) => {
            formData.append(
                field.formKey,
                field.input.files[0]
            );
        });

        runButton.disabled = true;
        resetButton.disabled = true;

        runButton.textContent =
            provider === "groq"
                ? "Running Groq analysis..."
                : "Running mock analysis...";

        runStatus.className =
            "run-status run-status-running";

        runStatus.textContent =
            "Running deterministic reconciliation " +
            "and AI review.";

        resultsPanel.hidden = true;

        try {
            const response = await fetch(endpoint, {
                method: "POST",
                body: formData,
                headers: {
                    Accept: "application/json",
                },
            });

            const responseText = await response.text();

            let payload;

            try {
                payload = JSON.parse(responseText);
            } catch {
                payload = {
                    message: responseText,
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
                "Reconciliation completed successfully.";
        } catch (error) {
            const message =
                error instanceof Error
                    ? error.message
                    : "Unexpected error";

            runStatus.className =
                "run-status run-status-error";

            runStatus.textContent =
                `Reconciliation failed: ${message}`;
        } finally {
            resetButton.disabled = false;

            runButton.textContent =
                "Run reconciliation";

            updateRunButton();
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
        });

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
                updateFileField(field);
                updateRunButton();
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
                renderReviewTable(latestPayload);
            }
        }
    );

    reviewTableBody.addEventListener(
        "click",
        (event) => {
            const button = event.target.closest(
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
            if (event.target === reviewDialog) {
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

    updateProviderHelp();
    updateRunButton();
    checkBackendConnection();
});