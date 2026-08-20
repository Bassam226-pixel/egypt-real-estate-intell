from typing import Any

import chromadb
from openai import OpenAI

from app.config import (
    CHROMA_URL,
    CHROMA_COLLECTION,
    NVIDIA_API_KEY,
    NVIDIA_BASE_URL,
    NVIDIA_CHAT_MODEL,
)


_chroma_client_singleton: Any | None = None
_llm_client_singleton: OpenAI | None = None


def _chroma_client() -> Any:
    global _chroma_client_singleton
    if _chroma_client_singleton is None:
        _chroma_client_singleton = chromadb.HttpClient(
            host=CHROMA_URL.replace("http://", "").split(":")[0],
            port=int(CHROMA_URL.split(":")[-1]),
        )
    return _chroma_client_singleton


def _llm_client() -> OpenAI:
    global _llm_client_singleton
    if _llm_client_singleton is None:
        _llm_client_singleton = OpenAI(base_url=NVIDIA_BASE_URL, api_key=NVIDIA_API_KEY, timeout=30.0)
    return _llm_client_singleton


def _build_recommendation_text(rec: Any) -> str:
    allocs = [f"{a.asset_class}: {a.weight_pct:.0f}%"
              for a in rec.allocations if a.weight_pct > 0.1]
    lines = [
        f"Investment amount: EGP {rec.amount:,.0f}",
        f"Risk level: {rec.risk_level}, Duration: {rec.duration}",
        f"Top pick: {rec.top_asset_class}",
        f"Expected return: {rec.portfolio_expected_return*100:.1f}%",
        f"Volatility: {rec.portfolio_volatility*100:.1f}%",
        f"Allocations: {', '.join(allocs)}",
    ]
    for dd in rec.drilldowns:
        lines.append(f"{dd.asset_class.title()}: {dd.rationale}")
        if dd.picks and dd.asset_class == "stocks":
            tickers = ", ".join(p.get("ticker", "") for p in dd.picks[:3])
            lines.append(f"  Recommended stocks: {tickers}")
        elif dd.picks and dd.asset_class == "real_estate":
            districts = ", ".join(p.get("district", "") for p in dd.picks[:5])
            lines.append(f"  Suggested districts: {districts}")
    return "\n".join(lines)


def answer_question(question: str, n_results: int = 5,
                    recommendation: Any = None) -> str:
    try:
        client = _chroma_client()
        collection = client.get_collection(CHROMA_COLLECTION)
        results = collection.query(query_texts=[question], n_results=n_results)
    except Exception:
        return "No investment data has been ingested yet, or ChromaDB is unreachable. Run a recommendation first."
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    if not documents:
        return "No relevant data found to answer your question."

    context_lines = []
    for doc, meta in zip(documents, metadatas):
        meta_str = ", ".join(f"{k}={v}" for k, v in meta.items())
        context_lines.append(f"[{meta_str}] {doc}")

    context = "\n".join(context_lines)

    rec_text = ""
    if recommendation is not None:
        rec_text = _build_recommendation_text(recommendation)

    system_prompt = (
        "You are an Egyptian investment advisor assistant. Answer the user's question "
        "based on the current recommendation and its retrieved context. "
        "The context comes from the user's portfolio recommendation: the chosen "
        "asset-class allocations, the top pick, and the specific recommended stocks "
        "and/or real estate listings. "
        "When the user refers to 'my portfolio' or 'my recommendation', use the "
        "recommendation context provided below. "
        "If the context doesn't contain enough information, say so clearly. "
        "Give concise, factual answers."
    )

    user_prompt = f"""Current Recommendation:
{rec_text}

Data Context:
{context}

Question: {question}

Answer:"""

    llm = _llm_client()
    try:
        resp = llm.chat.completions.create(
            model=NVIDIA_CHAT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=500,
        )
        return resp.choices[0].message.content or "No response from model."
    except Exception as e:
        return f"Error querying LLM: {e}"
