from typing import Any

import chromadb

from app.config import CHROMA_URL, CHROMA_COLLECTION


def _chroma_client() -> Any:
    return chromadb.HttpClient(host=CHROMA_URL.replace("http://", "").split(":")[0],
                                port=int(CHROMA_URL.split(":")[-1]))


def _reset_collection(client: Any) -> None:
    try:
        client.delete_collection(CHROMA_COLLECTION)
    except Exception:
        pass
    client.create_collection(CHROMA_COLLECTION)


def _text_from_recommendation(rec: Any) -> list[dict]:
    allocs = [f"{a.asset_class}: {a.weight_pct:.0f}%"
              for a in rec.allocations if a.weight_pct > 0.1]
    summary = (
        f"Portfolio recommendation. Investment amount: EGP {rec.amount:,.0f}. "
        f"Risk level: {rec.risk_level}, Duration: {rec.duration}. "
        f"Top pick: {rec.top_asset_class}. "
        f"Expected return: {rec.portfolio_expected_return*100:.1f}%, "
        f"volatility: {rec.portfolio_volatility*100:.1f}%, "
        f"sharpe ratio: {rec.portfolio_sharpe_ratio:.2f}. "
        f"Allocations: {', '.join(allocs)}. Rationale: {rec.rationale}."
    )
    docs = [{
        "text": summary,
        "metadata": {"type": "recommendation", "scope": "portfolio"},
    }]

    for dd in rec.drilldowns:
        if dd.asset_class == "stocks":
            picks_text = "; ".join(
                f"{p.get('ticker')} (score {p.get('composite_score')}, "
                f"roe {p.get('roe')}, dividend_yield {p.get('dividend_yield')}, "
                f"momentum_3m {p.get('momentum_3m')}, vol_90d {p.get('vol_90d')})"
                for p in dd.picks
            )
            text = f"Recommended stocks: {picks_text}. Rationale: {dd.rationale}."
            docs.append({"text": text, "metadata": {"type": "recommendation", "scope": "stocks"}})
        elif dd.asset_class == "real_estate":
            picks_text = "; ".join(
                f"{p.get('district')} — {p.get('property_type')}, {p.get('area_sqm')} sqm, "
                f"{p.get('bedrooms')} bedrooms, EGP {p.get('price_egp'):,.0f}, "
                f"EGP {p.get('price_per_sqm'):,.0f}/sqm"
                for p in dd.picks
            )
            text = f"Recommended real estate: {picks_text}. Rationale: {dd.rationale}."
            docs.append({"text": text, "metadata": {"type": "recommendation", "scope": "real_estate"}})
        elif dd.asset_class in ("gold", "silver"):
            picks_text = "; ".join(
                f"roi_1yr_egp {p.get('roi_1yr_egp')}%, roi_3yr_egp {p.get('roi_3yr_egp')}%, "
                f"roi_5yr_egp {p.get('roi_5yr_egp')}%, latest_price_egp {p.get('latest_price_egp')}"
                for p in dd.picks
            )
            text = f"Recommended {dd.asset_class}: {picks_text}. Rationale: {dd.rationale}."
            docs.append({"text": text, "metadata": {"type": "recommendation", "scope": dd.asset_class}})

    return docs


def ingest_recommendation(rec: Any, client: Any = None) -> int:
    if rec is None or not rec.allocations:
        return 0

    docs = _text_from_recommendation(rec)
    if not docs:
        return 0

    client = client or _chroma_client()
    _reset_collection(client)
    collection = client.get_collection(CHROMA_COLLECTION)

    texts = [d["text"] for d in docs]
    metadatas = [d["metadata"] for d in docs]
    ids = [f"rec_{i}" for i in range(len(docs))]

    collection.add(documents=texts, metadatas=metadatas, ids=ids)
    return len(docs)
