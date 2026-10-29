"""
EcoTwin-AI
Phase 2: Solar Telemetry Preprocessing

Prepares the external solar telemetry dataset for
machine-learning model development.

SRS parameters:
    - ambient_temperature
    - module_temperature
    - voltage
    - current
    - power
    - irradiance
"""

from pathlib import Path
import json

import numpy as np
import pandas as pd


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"

EXTERNAL_DATA_DIR = DATA_DIR / "external"

PROCESSED_DATA_DIR = DATA_DIR / "processed"

PROCESSED_DATA_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# INPUT / OUTPUT
# ============================================================

DEFAULT_INPUT_FILE = (
    EXTERNAL_DATA_DIR / "solards.csv"
)

DEFAULT_OUTPUT_FILE = (
    PROCESSED_DATA_DIR /
    "solards_cleaned.csv"
)

METADATA_FILE = (
    PROCESSED_DATA_DIR /
    "preprocessing_metadata.json"
)


# ============================================================
# SRS FEATURES
# ============================================================

FEATURE_COLUMNS = [

    "ambient_temperature",

    "module_temperature",

    "voltage",

    "current",

    "power",

    "irradiance"

]


# ============================================================
# SOURCE COLUMN MAPPING
# ============================================================

SOURCE_COLUMN_MAPPING = {

    "SR_NO": "record_id",

    "AMBIENT_TEMP": (
        "ambient_temperature"
    ),

    "MODULE_TEMP": (
        "module_temperature"
    ),

    "VOLTAGE": "voltage",

    "CURRENT": "current",

    "POWER": "power",

    "IR": "irradiance"

}


# ============================================================
# BASIC VALIDATION RANGES
# ============================================================

# These ranges are deliberately broad.
# They are intended to identify obviously invalid
# records rather than remove legitimate operating values.

VALIDATION_RANGES = {

    "ambient_temperature": (
        -50,
        1000
    ),

    "module_temperature": (
        -50,
        1000
    ),

    "voltage": (
        0,
        1000
    ),

    "current": (
        0,
        1000
    ),

    "power": (
        0,
        100000
    ),

    "irradiance": (
        0,
        5000
    )

}


# ============================================================
# LOAD DATA
# ============================================================

def load_dataset(
    input_file=DEFAULT_INPUT_FILE
):

    input_file = Path(
        input_file
    )

    if not input_file.exists():

        raise FileNotFoundError(

            "Solar telemetry dataset "
            f"not found: {input_file}"

        )

    dataframe = pd.read_csv(
        input_file
    )

    return dataframe


# ============================================================
# NORMALIZE COLUMN NAMES
# ============================================================

def normalize_columns(
    dataframe
):

    dataframe = dataframe.copy()

    dataframe.columns = [

        str(column)
        .strip()
        .upper()

        for column in dataframe.columns

    ]

    return dataframe


# ============================================================
# VALIDATE SOURCE COLUMNS
# ============================================================

def validate_source_columns(
    dataframe
):

    required_columns = set(
        SOURCE_COLUMN_MAPPING.keys()
    )

    available_columns = set(
        dataframe.columns
    )

    missing = sorted(
        required_columns -
        available_columns
    )

    if missing:

        raise ValueError(

            "Missing required source columns: "
            + ", ".join(missing)

        )

    return True


# ============================================================
# SELECT AND RENAME FEATURES
# ============================================================

def prepare_features(
    dataframe
):

    dataframe = dataframe.copy()

    validate_source_columns(
        dataframe
    )

    dataframe = dataframe[
        list(
            SOURCE_COLUMN_MAPPING.keys()
        )
    ].copy()

    dataframe.rename(

        columns=SOURCE_COLUMN_MAPPING,

        inplace=True

    )

    return dataframe


# ============================================================
# CONVERT NUMERIC VALUES
# ============================================================

def convert_numeric(
    dataframe
):

    dataframe = dataframe.copy()

    for column in FEATURE_COLUMNS:

        dataframe[column] = pd.to_numeric(

            dataframe[column],

            errors="coerce"

        )

    return dataframe


# ============================================================
# REMOVE INVALID VALUES
# ============================================================

def remove_invalid_values(
    dataframe
):

    dataframe = dataframe.copy()

    initial_rows = len(
        dataframe
    )

    # Remove rows with missing feature values

    dataframe.dropna(

        subset=FEATURE_COLUMNS,

        inplace=True

    )

    missing_removed = (
        initial_rows -
        len(dataframe)
    )


    # Remove infinite values

    dataframe.replace(

        [
            np.inf,
            -np.inf
        ],

        np.nan,

        inplace=True

    )

    dataframe.dropna(

        subset=FEATURE_COLUMNS,

        inplace=True

    )


    # Apply broad validation ranges

    range_invalid_mask = pd.Series(

        False,

        index=dataframe.index

    )


    for column, limits in (
        VALIDATION_RANGES.items()
    ):

        minimum, maximum = limits

        invalid = (

            (dataframe[column] < minimum)

            |

            (dataframe[column] > maximum)

        )

        range_invalid_mask |= invalid


    range_invalid_rows = int(
        range_invalid_mask.sum()
    )

    dataframe = dataframe[
        ~range_invalid_mask
    ].copy()


    return (

        dataframe,

        {

            "initial_rows": initial_rows,

            "missing_or_invalid_removed": (
                missing_removed
            ),

            "range_invalid_removed": (
                range_invalid_rows
            )

        }

    )


# ============================================================
# REMOVE DUPLICATES
# ============================================================

def remove_duplicates(
    dataframe
):

    dataframe = dataframe.copy()

    before = len(
        dataframe
    )

    dataframe.drop_duplicates(

        subset=FEATURE_COLUMNS,

        keep="first",

        inplace=True

    )

    removed = (
        before -
        len(dataframe)
    )

    return dataframe, removed


# ============================================================
# DERIVED FEATURES
# ============================================================

def create_derived_features(
    dataframe
):

    dataframe = dataframe.copy()

    # Temperature difference between module and ambient.

    dataframe[
        "temperature_difference"
    ] = (

        dataframe[
            "module_temperature"
        ]

        -

        dataframe[
            "ambient_temperature"
        ]

    )

    return dataframe


# ============================================================
# FINAL COLUMN ORDER
# ============================================================

def arrange_columns(
    dataframe
):

    dataframe = dataframe.copy()

    columns = [

        "record_id",

        "ambient_temperature",

        "module_temperature",

        "temperature_difference",

        "voltage",

        "current",

        "power",

        "irradiance"

    ]

    existing_columns = [

        column

        for column in columns

        if column in dataframe.columns

    ]

    return dataframe[
        existing_columns
    ]


# ============================================================
# SAVE DATASET
# ============================================================

def save_dataset(
    dataframe,
    output_file=DEFAULT_OUTPUT_FILE
):

    output_file = Path(
        output_file
    )

    output_file.parent.mkdir(

        parents=True,

        exist_ok=True

    )

    dataframe.to_csv(

        output_file,

        index=False

    )

    return output_file


# ============================================================
# SAVE METADATA
# ============================================================

def save_metadata(
    metadata,
    metadata_file=METADATA_FILE
):

    metadata_file = Path(
        metadata_file
    )

    metadata_file.parent.mkdir(

        parents=True,

        exist_ok=True

    )

    with open(

        metadata_file,

        "w",

        encoding="utf-8"

    ) as file:

        json.dump(

            metadata,

            file,

            indent=4

        )

    return metadata_file


# ============================================================
# COMPLETE PREPROCESSING PIPELINE
# ============================================================

def preprocess_dataset(

    input_file=DEFAULT_INPUT_FILE,

    output_file=DEFAULT_OUTPUT_FILE

):

    print("=" * 60)

    print(
        "EcoTwin-AI Solar Telemetry Preprocessing"
    )

    print("=" * 60)


    # --------------------------------------------------------
    # Load
    # --------------------------------------------------------

    print(
        f"\nInput: {input_file}"
    )

    raw = load_dataset(
        input_file
    )

    print(
        f"Raw rows: {len(raw)}"
    )


    # --------------------------------------------------------
    # Normalize
    # --------------------------------------------------------

    raw = normalize_columns(
        raw
    )


    # --------------------------------------------------------
    # Prepare
    # --------------------------------------------------------

    dataframe = prepare_features(
        raw
    )


    # --------------------------------------------------------
    # Numeric conversion
    # --------------------------------------------------------

    dataframe = convert_numeric(
        dataframe
    )


    # --------------------------------------------------------
    # Invalid values
    # --------------------------------------------------------

    (
        dataframe,
        invalid_stats
    ) = remove_invalid_values(
        dataframe
    )


    # --------------------------------------------------------
    # Duplicate removal
    # --------------------------------------------------------

    (
        dataframe,
        duplicates_removed
    ) = remove_duplicates(
        dataframe
    )


    # --------------------------------------------------------
    # Derived features
    # --------------------------------------------------------

    dataframe = create_derived_features(
        dataframe
    )


    # --------------------------------------------------------
    # Arrange
    # --------------------------------------------------------

    dataframe = arrange_columns(
        dataframe
    )


    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    saved_file = save_dataset(

        dataframe,

        output_file

    )


    # --------------------------------------------------------
    # Metadata
    # --------------------------------------------------------

    metadata = {

        "input_file": str(
            input_file
        ),

        "output_file": str(
            saved_file
        ),

        "raw_rows": int(
            len(raw)
        ),

        "processed_rows": int(
            len(dataframe)
        ),

        "duplicates_removed": int(
            duplicates_removed
        ),

        "invalid_value_statistics": (
            invalid_stats
        ),

        "features": FEATURE_COLUMNS,

        "derived_features": [

            "temperature_difference"

        ],

        "source_columns": (
            SOURCE_COLUMN_MAPPING
        )

    }


    save_metadata(
        metadata
    )


    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print(
        f"\nProcessed rows: "
        f"{len(dataframe)}"
    )

    print(
        f"Duplicates removed: "
        f"{duplicates_removed}"
    )

    print(
        "\nFeatures:"
    )

    for feature in FEATURE_COLUMNS:

        print(
            f"  - {feature}"
        )

    print(
        "\nDerived feature:"
    )

    print(
        "  - temperature_difference"
    )

    print(
        f"\nSaved cleaned dataset:"
        f"\n{saved_file}"
    )

    print(
        f"\nSaved metadata:"
        f"\n{METADATA_FILE}"
    )

    print(
        "\nPreprocessing completed successfully."
    )


    return dataframe


# ============================================================
# COMMAND LINE ENTRY POINT
# ============================================================

if __name__ == "__main__":

    preprocess_dataset()