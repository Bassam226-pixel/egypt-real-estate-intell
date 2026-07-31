from pathlib import Path

from ingestion.loaders.s3_upload import upload_raw

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "Egx Stocks data"

FILES = [
    "batch_eod_all_stocks.csv",
    "fundamentals_all.csv",
    "live_quotes_all.csv",
]


def run() -> None:
    for name in FILES:
        upload_raw(str(DATA_DIR / name), name)


if __name__ == "__main__":
    run()
