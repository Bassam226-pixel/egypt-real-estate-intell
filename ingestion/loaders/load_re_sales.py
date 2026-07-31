from pathlib import Path

from ingestion.loaders.s3_upload import upload_raw

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

FILES = [
    ("aqarmap", "aqarmap_data.json"),
    ("propertyfinder", "propertyfinder_data.json"),
    ("bayut", "bayut_data.json"),
]


def run() -> None:
    for folder, name in FILES:
        upload_raw(str(DATA_DIR / folder / "data.json"), name)


if __name__ == "__main__":
    run()
