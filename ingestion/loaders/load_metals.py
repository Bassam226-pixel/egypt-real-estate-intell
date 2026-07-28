from pathlib import Path

from ingestion.loaders.s3_upload import upload_raw

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "Gold"

FILES = [
    "authority_prices.csv",
    "spot_prices.csv",
]


def run() -> None:
    for name in FILES:
        upload_raw(str(DATA_DIR / name), name)


if __name__ == "__main__":
    run()
