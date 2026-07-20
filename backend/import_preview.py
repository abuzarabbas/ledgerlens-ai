import csv
import io
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.import_mapper import (
    ImportMappingError,
    suggest_column_mapping,
)


MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024
PREVIEW_ROW_LIMIT = 5

router = APIRouter(
    prefix="/import",
    tags=["import"],
)


class CSVPreviewError(ValueError):
    """
    Raised when an uploaded CSV cannot be previewed safely.
    """


def _decode_csv_bytes(
    file_bytes: bytes,
) -> tuple[str, str]:
    """
    Decode CSV bytes using common export encodings.
    """

    encodings = [
        "utf-8-sig",
        "utf-8",
        "cp1252",
        "latin-1",
    ]

    for encoding in encodings:
        try:
            return (
                file_bytes.decode(encoding),
                encoding,
            )
        except UnicodeDecodeError:
            continue

    raise CSVPreviewError(
        "The CSV encoding could not be detected."
    )


def _detect_delimiter(text: str) -> str:
    """
    Detect a common CSV delimiter.
    """

    sample = text[:8192]

    try:
        dialect = csv.Sniffer().sniff(
            sample,
            delimiters=",;\t|",
        )

        return dialect.delimiter
    except csv.Error:
        return ","


def _find_duplicate_headers(
    headers: list[str],
) -> list[str]:
    """
    Find duplicate headers using case-insensitive matching.
    """

    normalized_headers = [
        header.strip().casefold()
        for header in headers
    ]

    duplicate_headers: list[str] = []

    for index, normalized_header in enumerate(
        normalized_headers
    ):
        if normalized_headers.count(
            normalized_header
        ) <= 1:
            continue

        original_header = headers[index]

        if original_header not in duplicate_headers:
            duplicate_headers.append(
                original_header
            )

    return duplicate_headers


def build_csv_preview(
    file_bytes: bytes,
    filename: str,
    dataset_type: str,
) -> dict[str, Any]:
    """
    Read a CSV and return metadata, preview rows, and mapping
    suggestions without modifying the uploaded data.
    """

    safe_filename = filename.strip() or "uploaded.csv"

    if Path(safe_filename).suffix.lower() != ".csv":
        raise CSVPreviewError(
            "Only CSV files are supported."
        )

    if not file_bytes:
        raise CSVPreviewError(
            "The uploaded CSV is empty."
        )

    if len(file_bytes) > MAX_UPLOAD_SIZE_BYTES:
        raise CSVPreviewError(
            "The uploaded CSV exceeds the 10 MB limit."
        )

    text, encoding = _decode_csv_bytes(
        file_bytes
    )

    if not text.strip():
        raise CSVPreviewError(
            "The uploaded CSV contains no readable data."
        )

    delimiter = _detect_delimiter(text)

    reader = csv.reader(
        io.StringIO(
            text,
            newline="",
        ),
        delimiter=delimiter,
    )

    try:
        raw_headers = next(reader)
    except StopIteration as exc:
        raise CSVPreviewError(
            "The uploaded CSV contains no header row."
        ) from exc

    headers = [
        header.strip()
        for header in raw_headers
    ]

    if not headers:
        raise CSVPreviewError(
            "The uploaded CSV contains no columns."
        )

    empty_header_positions = [
        str(index + 1)
        for index, header in enumerate(headers)
        if not header
    ]

    if empty_header_positions:
        raise CSVPreviewError(
            "The CSV contains unnamed column(s) at "
            f"position(s): {', '.join(empty_header_positions)}."
        )

    duplicate_headers = _find_duplicate_headers(
        headers
    )

    if duplicate_headers:
        raise CSVPreviewError(
            "The CSV contains duplicate column name(s): "
            f"{', '.join(duplicate_headers)}."
        )

    preview_rows: list[dict[str, str]] = []
    malformed_row_numbers: list[int] = []
    row_count = 0

    for csv_row_number, row in enumerate(
        reader,
        start=2,
    ):
        if not row or not any(
            value.strip()
            for value in row
        ):
            continue

        row_count += 1

        if len(row) != len(headers):
            malformed_row_numbers.append(
                csv_row_number
            )
            continue

        if len(preview_rows) < PREVIEW_ROW_LIMIT:
            preview_rows.append(
                {
                    header: value.strip()
                    for header, value in zip(
                        headers,
                        row,
                    )
                }
            )

    warnings: list[str] = []

    if row_count == 0:
        warnings.append(
            "The CSV contains headers but no data rows."
        )

    if malformed_row_numbers:
        displayed_rows = malformed_row_numbers[:10]

        warnings.append(
            "Rows with a different number of values than "
            "the header were excluded from the preview: "
            + ", ".join(
                str(row_number)
                for row_number in displayed_rows
            )
        )

    mapping_suggestion = suggest_column_mapping(
        source_columns=headers,
        dataset_type=dataset_type,
    )

    return {
        "filename": safe_filename,
        "dataset_type": dataset_type,
        "encoding": encoding,
        "delimiter": delimiter,
        "row_count": row_count,
        "column_count": len(headers),
        "source_columns": headers,
        "preview_rows": preview_rows,
        "warnings": warnings,
        "mapping": mapping_suggestion,
    }


@router.post("/preview/{dataset_type}")
async def preview_csv_import(
    dataset_type: str,
    file: UploadFile = File(...),
) -> dict[str, Any]:
    """
    Preview an uploaded CSV and suggest LedgerLens mappings.
    """

    try:
        file_bytes = await file.read()

        return build_csv_preview(
            file_bytes=file_bytes,
            filename=file.filename or "uploaded.csv",
            dataset_type=dataset_type,
        )
    except (
        CSVPreviewError,
        ImportMappingError,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    finally:
        await file.close()