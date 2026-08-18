from pathlib import Path

from ingestion.loaders.s3_upload import upload_raw

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "rental data"


def run() -> None:
    name = "rental_listings.csv"
    upload_raw(str(DATA_DIR / name), name)


if __name__ == "__main__":
    run()
