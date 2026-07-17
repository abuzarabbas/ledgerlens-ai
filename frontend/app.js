"use strict";

const apiStatus = document.querySelector("#api-status");
const apiStatusText = document.querySelector("#api-status-text");
const connectionResult = document.querySelector("#connection-result");
const connectionButton = document.querySelector(
    "#check-connection-button"
);

async function checkBackendConnection() {
    apiStatus.className = "status status-checking";
    apiStatusText.textContent = "Checking API";

    connectionButton.disabled = true;
    connectionButton.textContent = "Checking connection...";

    connectionResult.className = "connection-result";
    connectionResult.textContent =
        "Contacting the LedgerLens health endpoint.";

    try {
        const response = await fetch("/health", {
            method: "GET",
            headers: {
                Accept: "application/json",
            },
        });

        if (!response.ok) {
            throw new Error(
                `The API returned HTTP ${response.status}.`
            );
        }

        const payload = await response.json();

        apiStatus.className = "status status-connected";
        apiStatusText.textContent = "API connected";

        connectionResult.className =
            "connection-result connection-result-success";

        connectionResult.textContent =
            `LedgerLens backend is available. ` +
            `Health response: ${JSON.stringify(payload)}`;
    } catch (error) {
        const message =
            error instanceof Error
                ? error.message
                : "Unknown connection error.";

        apiStatus.className = "status status-error";
        apiStatusText.textContent = "API unavailable";

        connectionResult.className =
            "connection-result connection-result-error";

        connectionResult.textContent =
            `The dashboard could not reach the backend. ${message}`;
    } finally {
        connectionButton.disabled = false;
        connectionButton.textContent =
            "Check backend connection";
    }
}

connectionButton.addEventListener(
    "click",
    checkBackendConnection
);

window.addEventListener(
    "DOMContentLoaded",
    checkBackendConnection
);