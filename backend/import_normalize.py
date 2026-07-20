import io
import json
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from backend.import_mapper import (
    ImportMappingError,
    apply_column_mapping,
)
from backend.import_preview import (
    CSVPreviewError,
    build_csv_preview,
)


router = APIRouter(
    prefix="/import",
    tags=["import"],
)


class CSVNormalizationError(ValueError):
    """
    Raised when an uploaded CSV cannot be normalized safely.
    """


def _parse_mapping_json(
    mapping_json: str,
) -> dict[str, str | None]:
    """
    Parse the mapping submitted by the dashboard.
    """

    try:
        mapping = json.loads(mapping_json)
    except json.JSONDecodeError as exc:
        raise CSVNormalizationError(
            "The column mapping is not valid JSON."
        ) from exc

    if not isinstance(mapping, dict):
        raise CSVNormalizationError(
            "The column mapping must be a JSON object."
        )

    cleaned_mapping: dict[str, str | None] = {}

    for canonical_field, source_column in mapping.items():
        if not isinstance(canonical_field, str):
            raise CSVNormalizationError(
                "Every canonical mapping field must be text."
            )

        if source_column is None:
            cleaned_mapping[canonical_field] = None
            continue

        if not isinstance(source_column, str):
            raise CSVNormalizationError(
                "Every mapped source column must be text or null."
            )

        cleaned_source = source_column.strip()

        cleaned_mapping[canonical_field] = (
            cleaned_source
            if cleaned_source
            else None
        )

    return cleaned_mapping


def _read_source_dataframe(
    file_bytes: bytes,
    encoding: str,
    delimiter: str,
) -> pd.DataFrame:
    """
    Read the uploaded CSV while preserving source values as text.
    """

    try:
        text = file_bytes.decode(encoding)
    except UnicodeDecodeError as exc:
        raise CSVNormalizationError(
            "The uploaded CSV could not be decoded "
            "using the detected encoding."
        ) from exc

    try:
        dataframe = pd.read_csv(
            io.StringIO(text),
            sep=delimiter,
            dtype=str,
            keep_default_na=False,
            on_bad_lines="error",
        )
    except pd.errors.ParserError as exc:
        raise CSVNormalizationError(
            "The CSV contains malformed rows and cannot "
            "be normalized safely."
        ) from exc
    except pd.errors.EmptyDataError as exc:
        raise CSVNormalizationError(
            "The uploaded CSV contains no readable data."
        ) from exc

    dataframe.columns = [
        str(column).strip()
        for column in dataframe.columns
    ]

    for column in dataframe.columns:
        dataframe[column] = (
            dataframe[column]
            .astype(str)
            .str.strip()
        )

    return dataframe


def normalize_csv_import(
    file_bytes: bytes,
    filename: str,
    dataset_type: str,
    mapping: dict[str, str | None],
) -> dict[str, Any]:
    """
    Convert an uploaded CSV into LedgerLens's canonical schema.
    """

    preview = build_csv_preview(
        file_bytes=file_bytes,
        filename=filename,
        dataset_type=dataset_type,
    )

    source_dataframe = _read_source_dataframe(
        file_bytes=file_bytes,
        encoding=preview["encoding"],
        delimiter=preview["delimiter"],
    )

    normalized_dataframe = apply_column_mapping(
        dataframe=source_dataframe,
        dataset_type=dataset_type,
        mapping=mapping,
    )

    normalized_csv = normalized_dataframe.to_csv(
        index=False,
        lineterminator="\n",
    )

    source_stem = (
        Path(filename).stem.strip()
        or dataset_type
    )

    return {
        "dataset_type": dataset_type,
        "source_filename": filename,
        "normalized_filename": (
            f"{source_stem}-normalized.csv"
        ),
        "row_count": len(normalized_dataframe),
        "column_count": len(
            normalized_dataframe.columns
        ),
        "canonical_columns": list(
            normalized_dataframe.columns
        ),
        "encoding": "utf-8",
        "delimiter": ",",
        "normalized_csv": normalized_csv,
    }


@router.post("/normalize/{dataset_type}")
async def normalize_uploaded_csv(
    dataset_type: str,
    mapping_json: str = Form(...),
    file: UploadFile = File(...),
) -> dict[str, Any]:
    """
    Normalize a real CSV using the selected column mapping.
    """

    try:
        file_bytes = await file.read()

        mapping = _parse_mapping_json(
            mapping_json
        )

        return normalize_csv_import(
            file_bytes=file_bytes,
            filename=file.filename or "uploaded.csv",
            dataset_type=dataset_type,
            mapping=mapping,
        )
    except (
        CSVNormalizationError,
        CSVPreviewError,
        ImportMappingError,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    finally:
        await file.close()