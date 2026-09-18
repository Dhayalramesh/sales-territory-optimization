import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="Sales Force Sizing & Territory Optimization",
    page_icon="🗺️",
    layout="wide"
)

# ---------- Data loading ----------
@st.cache_data
def load_data():
    territories = pd.read_csv("data/territories.csv")
    reps = pd.read_csv("data/reps.csv")
    hcps = pd.read_csv("data/hcps.csv")
    territory_summary = pd.read_csv("data/territory_summary.csv")
    priority_list = pd.read_csv("data/priority_call_list.csv")
    return territories, reps, hcps, territory_summary, priority_list

territories, reps, hcps, territory_summary, priority_list = load_data()

# ---------- Header ----------
st.title("🗺️ Sales Force Sizing & Territory Optimization")
st.caption(
    "Synthetic pharma field-force dataset — 20 territories, 20 reps, 600 HCPs. "
    "Workload balancing, prescriber prioritization, and an interactive what-if reallocation tool."
)

# ---------- Top KPIs ----------
col1, col2, col3, col4 = st.columns(4)
col1.metric("Territories", f"{len(territory_summary)}")
col2.metric("Total HCPs", f"{len(hcps):,}")
col3.metric("Understaffed", f"{(territory_summary['sizing_recommendation'].str.contains('Understaffed')).sum()}")
col4.metric("Overstaffed", f"{(territory_summary['sizing_recommendation'].str.contains('Overstaffed')).sum()}")

st.markdown("---")

# ---------- Tabs ----------
tab1, tab2, tab3, tab4 = st.tabs(["📊 Territory Workload", "🎯 Priority Call List", "🔄 What-If Reallocation", "🔍 HCP Explorer"])

with tab1:
    st.subheader("Workload Ratio by Territory")
    st.caption("Potential score per unit of rep capacity — higher means more work relative to available call time.")

    df_sorted = territory_summary.sort_values("potential_per_capacity", ascending=False)
    fig = px.bar(
        df_sorted, x="territory_id", y="potential_per_capacity", color="sizing_recommendation",
        color_discrete_map={
            "Understaffed — consider adding capacity": "#d62728",
            "Balanced": "#2ca02c",
            "Overstaffed — consider reallocating": "#ff7f0e",
        },
        labels={"potential_per_capacity": "Potential per Capacity", "territory_id": "Territory"}
    )
    st.plotly_chart(fig, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Sizing Recommendation Breakdown")
        counts = territory_summary["sizing_recommendation"].value_counts().reset_index()
        counts.columns = ["Recommendation", "Count"]
        fig2 = px.pie(counts, names="Recommendation", values="Count", hole=0.4,
                      color="Recommendation",
                      color_discrete_map={
                          "Understaffed — consider adding capacity": "#d62728",
                          "Balanced": "#2ca02c",
                          "Overstaffed — consider reallocating": "#ff7f0e",
                      })
        st.plotly_chart(fig2, use_container_width=True)

    with c2:
        st.subheader("Region Rollup")
        region_summary = territory_summary.groupby("region").agg(
            territories=("territory_id", "count"),
            total_hcps=("hcp_count", "sum"),
            avg_workload=("potential_per_capacity", "mean")
        ).round(2).reset_index()
        st.dataframe(region_summary, use_container_width=True, height=280)

    st.subheader("Territory Detail Table")
    st.dataframe(
        territory_summary[["territory_id", "region", "rep_id", "tenure_years", "hcp_count",
                            "total_potential", "quarterly_capacity", "potential_per_capacity",
                            "calls_vs_capacity_pct", "sizing_recommendation"]]
        .sort_values("potential_per_capacity", ascending=False),
        use_container_width=True
    )

with tab2:
    st.subheader("High-Priority, Under-Called HCPs")
    st.caption("Prescribers in the top potential decile whose current call frequency lags well behind their expected level — the 'call these first' list.")

    st.metric("Priority HCPs flagged", f"{len(priority_list)}")

    region_filter = st.multiselect("Filter by region", sorted(priority_list["region"].unique()),
                                    default=sorted(priority_list["region"].unique()))
    filtered_priority = priority_list[priority_list["region"].isin(region_filter)].sort_values("call_gap", ascending=False)

    fig3 = px.bar(filtered_priority.head(20), x="hcp_id", y="call_gap", color="specialty",
                  labels={"call_gap": "Call Gap (expected - actual)", "hcp_id": "HCP"})
    fig3.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig3, use_container_width=True)

    st.dataframe(filtered_priority, use_container_width=True)

with tab3:
    st.subheader("What-If: Reallocate Rep Capacity")
    st.caption("Simulate shifting weekly call capacity between two territories and see the resulting workload balance.")

    col_a, col_b = st.columns(2)
    with col_a:
        from_territory = st.selectbox("Move capacity FROM", territory_summary["territory_id"].tolist())
    with col_b:
        to_territory = st.selectbox("Move capacity TO", territory_summary["territory_id"].tolist(), index=1)

    max_shift = int(territory_summary.loc[territory_summary["territory_id"] == from_territory, "weekly_call_capacity"].values[0] * 0.5)
    shift_amount = st.slider("Weekly calls to shift", 0, max_shift, min(5, max_shift))

    if from_territory == to_territory:
        st.warning("Select two different territories to simulate a reallocation.")
    else:
        sim = territory_summary.copy()
        sim.loc[sim["territory_id"] == from_territory, "weekly_call_capacity"] -= shift_amount
        sim.loc[sim["territory_id"] == to_territory, "weekly_call_capacity"] += shift_amount
        sim["quarterly_capacity"] = sim["weekly_call_capacity"] * 13
        sim["potential_per_capacity"] = (sim["total_potential"] / sim["quarterly_capacity"]).round(3)

        median_ratio = sim["potential_per_capacity"].median()
        def sizing_flag(ratio):
            if ratio > median_ratio * 1.3:
                return "Understaffed — consider adding capacity"
            elif ratio < median_ratio * 0.7:
                return "Overstaffed — consider reallocating"
            return "Balanced"
        sim["sizing_recommendation"] = sim["potential_per_capacity"].apply(sizing_flag)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Before — {from_territory}**")
            before = territory_summary[territory_summary["territory_id"] == from_territory][["weekly_call_capacity", "potential_per_capacity", "sizing_recommendation"]]
            st.dataframe(before, use_container_width=True, hide_index=True)
            st.markdown(f"**After — {from_territory}**")
            after = sim[sim["territory_id"] == from_territory][["weekly_call_capacity", "potential_per_capacity", "sizing_recommendation"]]
            st.dataframe(after, use_container_width=True, hide_index=True)

        with c2:
            st.markdown(f"**Before — {to_territory}**")
            before2 = territory_summary[territory_summary["territory_id"] == to_territory][["weekly_call_capacity", "potential_per_capacity", "sizing_recommendation"]]
            st.dataframe(before2, use_container_width=True, hide_index=True)
            st.markdown(f"**After — {to_territory}**")
            after2 = sim[sim["territory_id"] == to_territory][["weekly_call_capacity", "potential_per_capacity", "sizing_recommendation"]]
            st.dataframe(after2, use_container_width=True, hide_index=True)

        fig4 = go.Figure()
        fig4.add_trace(go.Bar(name="Before", x=territory_summary["territory_id"], y=territory_summary["potential_per_capacity"], marker_color="lightgray"))
        fig4.add_trace(go.Bar(name="After", x=sim["territory_id"], y=sim["potential_per_capacity"], marker_color="steelblue"))
        fig4.update_layout(barmode="group", title="Workload Ratio: All Territories, Before vs After Reallocation",
                            yaxis_title="Potential per Capacity")
        st.plotly_chart(fig4, use_container_width=True)

with tab4:
    st.subheader("HCP-Level Explorer")
    territory_filter = st.multiselect("Filter by territory", sorted(hcps["territory_id"].unique()),
                                       default=[])
    specialty_filter = st.multiselect("Filter by specialty", sorted(hcps["specialty"].unique()),
                                       default=sorted(hcps["specialty"].unique()))

    view = hcps.copy()
    if territory_filter:
        view = view[view["territory_id"].isin(territory_filter)]
    view = view[view["specialty"].isin(specialty_filter)]

    st.dataframe(view.sort_values("call_gap", ascending=False), use_container_width=True, height=500)
    st.caption(f"Showing {len(view):,} of {len(hcps):,} HCPs based on current filters.")

st.markdown("---")
st.caption("Synthetic dataset built for portfolio purposes. Sizing logic mirrors standard pharma sales-force effectiveness methodology.")
