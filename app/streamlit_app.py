import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from app.config import NVIDIA_API_KEY
from app.engine.data_provider import DremioDataProvider
from app.engine.recommender import Recommender, best_specific_pick
from app.engine.property_finder import PropertyFinder
from app.engine.schemas import UserProfile, RiskLevel, Duration
from app.rag.ingest import ingest_recommendation
from app.rag.query import answer_question

st.set_page_config(
    page_title="Egypt Investment Recommender",
    page_icon="",
    layout="wide",
)

st.title(" Egyptian Investment Recommender")
st.markdown("---")

RISK_LABELS = {"Low": RiskLevel.LOW, "Medium": RiskLevel.MEDIUM, "High": RiskLevel.HIGH}
DURATION_LABELS = {
    "Short (<1 yr)": Duration.SHORT,
    "Medium (1-5 yr)": Duration.MEDIUM,
    "Long (>5 yr)": Duration.LONG,
}


def _show_suggestion_buttons(rec) -> str | None:
    suggestions = []
    if rec and rec.allocations:
        top = rec.top_asset_class
        amount = rec.amount
        suggestions.append(f"Why did you recommend {top}?")
        suggestions.append(f"Explain the risk of {top}")
        suggestions.append(f"How should I invest EGP {amount:,.0f}?")
        for dd in rec.drilldowns:
            if dd.asset_class == "stocks" and dd.picks:
                ticker = dd.picks[0].get("ticker", "")
                if ticker:
                    suggestions.append(f"Tell me about {ticker} stock")
                break
        suggestions.append("Compare gold vs real estate")
    else:
        suggestions = ["What is the current market snapshot?", "Summarize the investment data"]

    cols = st.columns(len(suggestions))
    for i, sug in enumerate(suggestions):
        with cols[i]:
            if st.button(sug, key=f"sug_{i}", use_container_width=True):
                return sug
    return None


def _init_provider() -> DremioDataProvider:
    if "_dp" not in st.session_state:
        st.session_state["_dp"] = DremioDataProvider()
    return st.session_state["_dp"]


with st.sidebar:
    st.header("Investment Profile")
    amount = st.number_input("Amount (EGP)", min_value=1_000, value=100_000, step=10_000, format="%d")
    risk_str = st.radio("Risk Level", list(RISK_LABELS.keys()), index=1)
    dur_str = st.radio("Duration", list(DURATION_LABELS.keys()), index=1)

    recommend_btn = st.button("Get Recommendation", type="primary", use_container_width=True)

    st.divider()
    st.caption("Data source: Nessie Iceberg → Dremio (Gold layer)")

tab_rec, tab_prop, tab_rag = st.tabs(["Recommendation", "Property Finder", "Ask AI"])

with tab_rec:
    if recommend_btn:
        with st.spinner("Querying Gold layer and optimizing portfolio..."):
            try:
                dp = _init_provider()
                recommender = Recommender(dp)
                profile = UserProfile(
                    amount=amount,
                    risk_level=RISK_LABELS[risk_str],
                    duration=DURATION_LABELS[dur_str],
                )
                result = recommender.recommend(profile)
                st.session_state["_last_result"] = result
                try:
                    st.session_state["_ingested_count"] = ingest_recommendation(result)
                except Exception as e:
                    st.session_state["_ingested_count"] = None
                    st.session_state["_ingest_error"] = str(e)
            except Exception as e:
                st.error(f"Recommendation failed: {e}")

    if "_last_result" not in st.session_state:
        st.info("Enter your investment profile in the sidebar and click **Get Recommendation**.")
    else:
        result = st.session_state["_last_result"]

        if not result.allocations:
            st.warning(result.rationale)
        else:
            top = result.top_asset_class
            st.success(f"**You should invest in: {top.title()}**")

            best = best_specific_pick(result)
            if best is not None:
                if top == "stocks":
                    st.markdown(
                        f"**Best stock:** {best.get('ticker')} — composite score "
                        f"{best.get('composite_score'):.3f}, ROE {best.get('roe'):.4f}, "
                        f"dividend yield {best.get('dividend_yield'):.4f}, "
                        f"momentum 3m {best.get('momentum_3m'):.4f}."
                    )
                elif top == "real_estate":
                    st.markdown(
                        f"**Best property:** {best.get('district')} — {best.get('property_type')}, "
                        f"{best.get('area_sqm'):.0f} sqm, {best.get('bedrooms')} bd, "
                        f"EGP {best.get('price_egp'):,.0f} (EGP {best.get('price_per_sqm'):,.0f}/sqm)."
                    )
                elif top in ("gold", "silver"):
                    st.markdown(
                        f"**{top.title()} ROI:** 1yr {best.get('roi_1yr_egp'):.2f}%, "
                        f"3yr {best.get('roi_3yr_egp'):.2f}%, 5yr {best.get('roi_5yr_egp'):.2f}%."
                    )

            if st.session_state.get("_ingested_count"):
                st.caption(
                    f"Recommendation ingested into ChromaDB "
                    f"({st.session_state['_ingested_count']} docs) — Ask AI is ready."
                )
            elif st.session_state.get("_ingest_error"):
                st.caption(f"ChromaDB ingestion failed: {st.session_state['_ingest_error']}")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Top Pick", result.top_asset_class.title(),
                          f"{result.allocations[0].expected_return*100:.1f}% exp. return")
            with col2:
                st.metric("Portfolio Return (ann.)", f"{result.portfolio_expected_return*100:.2f}%")
            with col3:
                st.metric("Portfolio Volatility (ann.)", f"{result.portfolio_volatility*100:.2f}%")

            st.markdown("### Portfolio Allocation")
            alloc_df = pd.DataFrame([
                {
                    "Asset Class": a.asset_class.title(),
                    "Weight (%)": round(a.weight_pct, 1),
                    "Expected Return (%)": round(a.expected_return * 100, 2),
                    "Volatility (%)": round(a.volatility * 100, 2),
                    "Risk Contribution (%)": round(a.risk_contribution_pct, 1),
                }
                for a in result.allocations if a.weight_pct > 0.1
            ])

            col_pie, col_table = st.columns([1, 1.5])
            with col_pie:
                fig = px.pie(alloc_df, values="Weight (%)", names="Asset Class",
                             title="Allocation by Asset Class",
                             color_discrete_sequence=px.colors.qualitative.Set2)
                fig.update_traces(textinfo="label+percent")
                st.plotly_chart(fig, use_container_width=True)

            with col_table:
                st.dataframe(alloc_df.style.format({
                    "Weight (%)": "{:.1f}",
                    "Expected Return (%)": "{:.2f}",
                    "Volatility (%)": "{:.2f}",
                    "Risk Contribution (%)": "{:.1f}",
                }), hide_index=True, use_container_width=True)

            if result.drilldowns:
                st.markdown("### Detailed Picks")
                for dd in result.drilldowns:
                    with st.expander(f"{dd.asset_class.title()} — {dd.rationale}", expanded=True):
                        if not dd.picks:
                            st.caption("No specific picks available.")
                        elif dd.asset_class == "stocks":
                            df = pd.DataFrame(dd.picks)
                            st.dataframe(
                                df,
                                column_config={
                                    "ticker": "Ticker",
                                    "allocation_egp": st.column_config.NumberColumn(
                                        "Allocation (EGP)", format="EGP %d",
                                    ),
                                    "composite_score": st.column_config.NumberColumn("Score", format="%.3f"),
                                    "roe": st.column_config.NumberColumn("ROE", format="%.4f"),
                                    "dividend_yield": st.column_config.NumberColumn("Div Yield", format="%.4f"),
                                    "momentum_3m": st.column_config.NumberColumn("Mom 3m", format="%.4f"),
                                    "vol_90d": st.column_config.NumberColumn("Vol 90d", format="%.4f"),
                                },
                                hide_index=True, use_container_width=True,
                            )
                        elif dd.asset_class == "real_estate":
                            df = pd.DataFrame(dd.picks)
                            st.dataframe(
                                df,
                                column_config={
                                    "district": "District",
                                    "property_type": "Type",
                                    "area_sqm": st.column_config.NumberColumn("Area (sqm)", format="%.0f"),
                                    "price_egp": st.column_config.NumberColumn("Price (EGP)", format="EGP %d"),
                                    "price_per_sqm": st.column_config.NumberColumn("Price/sqm", format="EGP %d"),
                                    "bedrooms": "Bedrooms",
                                    "link": st.column_config.LinkColumn("Listing", display_text="View"),
                                },
                                hide_index=True, use_container_width=True,
                            )
                        elif dd.asset_class in ("gold", "silver"):
                            st.dataframe(pd.DataFrame(dd.picks), hide_index=True, use_container_width=True)
                            if dd.asset_class == "gold":
                                st.caption(
                                    "Gold volatility in EGP (~29%) reflects both gold price "
                                    "movements and EGP devaluation effects."
                                )
                        else:
                            st.dataframe(pd.DataFrame(dd.picks), hide_index=True, use_container_width=True)

            st.markdown("### Rationale")
            st.info(result.rationale)

with tab_prop:
    st.header("Property Finder")
    st.markdown("Find real estate properties within your budget from the Egyptian market.")

    dp = _init_provider()
    pf = PropertyFinder(dp)

    if "_pf_opts" in st.session_state:
        opts = st.session_state["_pf_opts"]
    else:
        with st.spinner("Loading filter options..."):
            try:
                opts = pf.get_filter_options()
                st.session_state["_pf_opts"] = opts
            except Exception as e:
                st.error(f"Failed to load options: {e}. Retrying on next interaction.")
                opts = {
                    "districts": [], "property_types": [], "bedrooms": [],
                    "area_min": 0, "area_max": 500,
                }

    with st.container():
        col1, col2 = st.columns(2)
        with col1:
            prop_budget = st.number_input(
                "Budget (EGP)", min_value=10_000, value=1_000_000,
                step=50_000, format="%d", key="prop_budget"
            )
            district_opts = ["All"] + list(opts["districts"])
            prop_district = st.selectbox(
                "District", district_opts, key="prop_district"
            )
            type_opts = ["All"] + list(opts["property_types"])
            prop_type = st.selectbox(
                "Property Type", type_opts, key="prop_type"
            )
        with col2:
            bed_opts = ["Any"] + [str(b) for b in opts["bedrooms"]] + ["5+"]
            prop_bedrooms = st.selectbox(
                "Bedrooms", bed_opts, key="prop_bedrooms"
            )
            area_min = float(opts.get("area_min", 0))
            area_max = min(float(opts.get("area_max", 500)), 500.0)
            if area_min >= area_max:
                area_max = area_min + 100
            prop_area = st.slider(
                "Area (sqm)", min_value=0.0, max_value=area_max,
                value=(area_min, max(area_min, min(300.0, area_max))), step=10.0, key="prop_area"
            )

    search_btn = st.button("Search Properties", type="primary", use_container_width=True)

    if search_btn:
        with st.spinner("Searching listings..."):
            try:
                result = pf.search(
                    budget=prop_budget,
                    district=None if prop_district == "All" else prop_district,
                    property_type=None if prop_type == "All" else prop_type,
                    bedrooms=None if prop_bedrooms == "Any" else prop_bedrooms,
                    min_area=prop_area[0],
                    max_area=prop_area[1],
                )
                st.session_state["_pf_result"] = result
            except Exception as e:
                st.error(f"Search failed: {e}")

    if "_pf_result" in st.session_state:
        result = st.session_state["_pf_result"]

        st.markdown("---")
        if result.relaxed:
            st.warning(
                "No exact matches with your filters. Showing all properties within budget instead."
            )
        st.metric("Matching Listings", result.total_matches)

        if result.listings:
            rows = []
            for p in result.listings:
                rows.append({
                    "District": p.district,
                    "Type": p.property_type.title(),
                    "Area (sqm)": p.area_sqm,
                    "Bedrooms": p.bedrooms,
                    "Bathrooms": p.bathrooms,
                    "Price (EGP)": f"{p.price_egp:,.0f}",
                    "Price/sqm": f"{p.price_per_sqm:,.0f}",
                    "Link": p.link,
                })
            df = pd.DataFrame(rows)
            st.dataframe(
                df,
                column_config={
                    "Link": st.column_config.LinkColumn(
                        "Listing",
                        display_text="View Listing",
                        width="small",
                    ),
                    "Price (EGP)": st.column_config.TextColumn("Price (EGP)", width="medium"),
                    "Price/sqm": st.column_config.TextColumn("Price/sqm", width="medium"),
                },
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.info("No properties found matching your criteria. Try increasing your budget or broadening the filters.")
    else:
        st.info("Set your filters above and click **Search Properties**.")

with tab_rag:
    if not NVIDIA_API_KEY:
        st.warning("NVIDIA_API_KEY not set. RAG is disabled. Set it in .env to enable AI explanations.")
    else:
        if st.button("Re-ingest Recommendation into ChromaDB"):
            with st.spinner("Ingesting recommendation..."):
                try:
                    rec = st.session_state.get("_last_result")
                    if rec is None:
                        st.warning("Run a recommendation first, then re-ingest it here.")
                    else:
                        count = ingest_recommendation(rec)
                        st.success(f"Ingested {count} recommendation documents into ChromaDB.")
                except Exception as e:
                    st.error(f"Ingestion failed: {e}")

        if "messages" not in st.session_state:
            st.session_state["messages"] = []

        rec = st.session_state.get("_last_result")

        sug_prompt = _show_suggestion_buttons(rec) if not st.session_state["messages"] else None

        for msg in st.session_state["messages"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        chat_prompt = st.chat_input("Ask about the investment data...")
        prompt = sug_prompt or chat_prompt

        if prompt:
            st.session_state["messages"].append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Querying RAG + LLM..."):
                    ans = answer_question(prompt, recommendation=rec)
                st.markdown(ans)
            st.session_state["messages"].append({"role": "assistant", "content": ans})
