from pathlib import Path

from ingestion.loaders.s3_upload import upload_raw

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def run() -> None:
    upload_raw(str(DATA_DIR / "Gold" / "currency_rates.csv"), "currency_rates.csv")


if __name__ == "__main__":
    run()
