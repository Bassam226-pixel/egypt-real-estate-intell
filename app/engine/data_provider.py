import time

import requests
import pandas as pd

from app.config import DREMIO_HOST, DREMIO_REST_PORT, DREMIO_USER, DREMIO_PASSWORD


def _sql_string_literal(value: str) -> str:
    """Quote a string for interpolation into Dremio SQL. Dremio's job-submission API
    (unlike JDBC) takes only a raw SQL string with no bind-parameter support, so string
    inputs must be escaped as SQL literals rather than concatenated verbatim."""
    return "'" + value.replace("'", "''") + "'"


class DremioDataProvider:
    def __init__(self) -> None:
        self._base = f"http://{DREMIO_HOST}:{DREMIO_REST_PORT}"
        self._token: str | None = None

    def _login(self) -> None:
        resp = requests.post(
            f"{self._base}/apiv2/login",
            json={"userName": DREMIO_USER, "password": DREMIO_PASSWORD},
            timeout=10,
        )
        resp.raise_for_status()
        self._token = resp.json()["token"]

    def _submit_sql(self, sql: str) -> str:
        if self._token is None:
            self._login()
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        resp = requests.post(
            f"{self._base}/api/v3/sql",
            json={"sql": sql},
            headers=headers,
            timeout=30,
        )
        if resp.status_code == 401:
            self._login()
            headers["Authorization"] = f"Bearer {self._token}"
            resp = requests.post(
                f"{self._base}/api/v3/sql",
                json={"sql": sql},
                headers=headers,
                timeout=30,
            )
        resp.raise_for_status()
        return resp.json()["id"]

    def _poll_job(self, job_id: str, poll_interval: float = 1.0, timeout: float = 60.0) -> None:
        headers = {"Authorization": f"Bearer {self._token}"}
        deadline = time.time() + timeout
        while time.time() < deadline:
            resp = requests.get(f"{self._base}/api/v3/job/{job_id}", headers=headers, timeout=10)
            resp.raise_for_status()
            state = resp.json().get("jobState")
            if state == "COMPLETED":
                return
            if state == "FAILED":
                msg = resp.json().get("errorMessage", "Unknown error")
                raise RuntimeError(f"Dremio query failed: {msg}")
            time.sleep(poll_interval)
        raise TimeoutError(f"Dremio query did not complete within {timeout}s")

    def _get_results(self, job_id: str) -> pd.DataFrame:
        headers = {"Authorization": f"Bearer {self._token}"}
        resp = requests.get(
            f"{self._base}/api/v3/job/{job_id}/results",
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
        rows = result.get("rows", [])
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows)

    def _query(self, sql: str) -> pd.DataFrame:
        job_id = self._submit_sql(sql)
        self._poll_job(job_id)
        return self._get_results(job_id)

    def get_asset_scores(self) -> pd.DataFrame:
        return self._query("SELECT * FROM nessie.gold.asset_scores")

    def get_stock_scores(self) -> pd.DataFrame:
        return self._query("SELECT * FROM nessie.gold.stock_scores")

    def get_re_sale_metrics(self) -> pd.DataFrame:
        return self._query("SELECT * FROM nessie.gold.re_sale_metrics")

    def get_gold_metal_roi(self) -> pd.DataFrame:
        return self._query("SELECT * FROM nessie.gold.gold_metal_roi")

    def get_stock_returns_vol(self) -> pd.DataFrame:
        return self._query("SELECT * FROM nessie.gold.stock_returns_vol")

    def get_re_district_metrics(self) -> pd.DataFrame:
        return self._query("SELECT * FROM nessie.gold.re_district_metrics")

    def get_market_snapshot(self) -> pd.DataFrame:
        return self._query("SELECT * FROM nessie.gold.market_snapshot")

    def get_fx_rates(self) -> pd.DataFrame:
        return self._query("SELECT * FROM nessie.silver.fx_rates")

    def get_re_filter_options(self) -> dict:
        districts_df = self._query(
            "SELECT DISTINCT district FROM nessie.silver.re_sales ORDER BY district"
        )
        types_df = self._query(
            "SELECT DISTINCT property_type FROM nessie.silver.re_sales ORDER BY property_type"
        )
        beds_df = self._query(
            "SELECT DISTINCT bedrooms FROM nessie.silver.re_sales WHERE bedrooms IS NOT NULL ORDER BY bedrooms"
        )
        area_df = self._query(
            "SELECT MIN(area_sqm) AS min_area, MAX(area_sqm) AS max_area FROM nessie.silver.re_sales"
        )
        raw_max = float(area_df["max_area"].iloc[0]) if not area_df.empty else 500.0
        return {
            "districts": districts_df["district"].dropna().unique().tolist(),
            "property_types": types_df["property_type"].dropna().unique().tolist(),
            "bedrooms": sorted(beds_df["bedrooms"].dropna().astype(int).unique().tolist()),
            "area_min": float(area_df["min_area"].iloc[0]) if not area_df.empty else 0.0,
            "area_max": min(raw_max, 500.0),
        }

    def search_re_listings(
        self,
        budget: float,
        district: str | None = None,
        property_type: str | None = None,
        bedrooms: str | None = None,
        min_area: float | None = None,
        max_area: float | None = None,
    ) -> pd.DataFrame:
        sql = """
            SELECT district, property_type, area_sqm, price_egp,
                   bedrooms, bathrooms, price_per_sqm_egp AS price_per_sqm, link
            FROM nessie.silver.re_sales
            WHERE price_egp <= {}
        """.format(float(budget))
        if district:
            sql += f" AND LOWER(district) = {_sql_string_literal(district.lower())}"
        if property_type:
            sql += f" AND LOWER(property_type) = {_sql_string_literal(property_type.lower())}"
        if bedrooms:
            if bedrooms == "5+":
                sql += " AND bedrooms >= 5"
            else:
                sql += f" AND bedrooms = {int(bedrooms)}"
        if min_area is not None:
            sql += f" AND area_sqm >= {float(min_area)}"
        if max_area is not None:
            sql += f" AND area_sqm <= {float(max_area)}"
        sql += " ORDER BY price_egp ASC"
        return self._query(sql)
