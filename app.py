import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from io import BytesIO

st.set_page_config(page_title="Monthly Attendance Dashboard", layout="wide", page_icon="📅")

st.title("📅 Dashboard 3 — Monthly Attendance Trends")
st.markdown("Track attendance trends across teams, spot seasonal patterns, and follow individual rider journeys.")

uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx", "xls"])

ATTEND_STATUSES = ["P", "p", "Present", "PRESENT", "1"]
ABSENT_STATUSES = ["A", "a", "Absent", "ABSENT", "0"]
WEEKOFF_STATUSES = ["WO", "wo", "W/O", "Week Off", "WEEKOFF", "H", "Holiday"]

def parse_attendance_sheet(df):
    df = df.dropna(how="all").reset_index(drop=True)
    name_col = df.columns[0]
    date_cols = df.columns[1:]
    records = []
    for _, row in df.iterrows():
        name = str(row[name_col]).strip()
        if not name or name.lower() in ["nan", "name", "rider", "employee", "staff"]:
            continue
        present = sum(1 for c in date_cols if str(row[c]).strip() in ATTEND_STATUSES)
        absent = sum(1 for c in date_cols if str(row[c]).strip() in ABSENT_STATUSES)
        working_days = present + absent
        if working_days == 0:
            continue
        pct = round((present / working_days) * 100, 1)
        records.append({"Rider": name, "Present": present, "Absent": absent,
                        "WorkingDays": working_days, "AttendancePct": pct})
    return pd.DataFrame(records)

if uploaded_file:
    xl = pd.ExcelFile(uploaded_file)
    sheets = xl.sheet_names
    st.success(f"✅ File loaded. Sheets found: {', '.join(sheets)}")

    attend_sheets = st.multiselect(
        "Select attendance sheets (each = one team or month):",
        sheets,
        default=[s for s in sheets if any(k in s.upper() for k in ["NIM", "NF", "SM", "ATTEND"])]
    )

    month_labels = st.text_input(
        "Label each sheet (comma-separated). Use Month-Team format e.g. 'Apr-NIM, Apr-NF, May-NIM':",
        value=", ".join(attend_sheets)
    )
    month_names = [m.strip() for m in month_labels.split(",")]

    if attend_sheets and st.button("🚀 Generate Dashboard"):

        all_data = {}
        for i, sheet in enumerate(attend_sheets):
            raw = xl.parse(sheet, header=0)
            parsed = parse_attendance_sheet(raw)
            label = month_names[i] if i < len(month_names) else sheet
            parsed["Label"] = label
            # Try to extract team and month from label
            parts = label.split("-")
            parsed["Month"] = parts[0].strip() if len(parts) >= 1 else label
            parsed["Team"] = parts[1].strip() if len(parts) >= 2 else label
            all_data[label] = parsed

        combined = pd.concat(all_data.values(), ignore_index=True)

        st.markdown("---")

        # ── SECTION 1: Overall Monthly Trend ─────────────────────────────
        st.subheader("📈 Overall Attendance Trend Across Periods")

        monthly_avg = combined.groupby("Label")["AttendancePct"].mean().reset_index()
        monthly_avg.columns = ["Period", "AvgAttendance"]

        fig_trend = px.line(monthly_avg, x="Period", y="AvgAttendance",
                            markers=True,
                            title="Average Attendance % Across Periods",
                            color_discrete_sequence=["#2980b9"])
        fig_trend.add_hline(y=75, line_dash="dash", line_color="orange",
                            annotation_text="75% Target")
        fig_trend.add_hline(y=90, line_dash="dot", line_color="green",
                            annotation_text="90% Excellence")
        fig_trend.update_traces(line_width=3, marker_size=10)
        fig_trend.update_yaxes(range=[0, 105])
        st.plotly_chart(fig_trend, use_container_width=True)

        # ── SECTION 2: Cross-Team Comparison ────────────────────────────
        if "Team" in combined.columns and combined["Team"].nunique() > 1:
            st.subheader("🔀 Cross-Team Attendance Comparison")

            team_monthly = combined.groupby(["Month", "Team"])["AttendancePct"].mean().reset_index()

            fig_cross = px.line(team_monthly, x="Month", y="AttendancePct",
                                color="Team", markers=True,
                                title="Attendance by Team per Month",
                                color_discrete_sequence=px.colors.qualitative.Set1)
            fig_cross.add_hline(y=75, line_dash="dash", line_color="orange",
                                annotation_text="75% Target")
            fig_cross.update_traces(line_width=2, marker_size=8)
            fig_cross.update_yaxes(range=[0, 105])
            st.plotly_chart(fig_cross, use_container_width=True)

            # Side-by-side bar
            team_avg = combined.groupby("Team")["AttendancePct"].mean().reset_index()
            team_avg.columns = ["Team", "AvgAttendance"]
            team_avg["AvgAttendance"] = team_avg["AvgAttendance"].round(1)

            fig_bar = px.bar(team_avg, x="Team", y="AvgAttendance",
                             color="AvgAttendance",
                             color_continuous_scale="RdYlGn",
                             title="Overall Avg Attendance by Team",
                             text="AvgAttendance")
            fig_bar.update_traces(texttemplate="%{text}%", textposition="outside")
            fig_bar.update_layout(coloraxis_showscale=False)
            st.plotly_chart(fig_bar, use_container_width=True)

        # ── SECTION 3: Month-over-Month Delta ────────────────────────────
        st.subheader("📊 Period-over-Period Change")

        if len(monthly_avg) >= 2:
            monthly_avg["PrevAttendance"] = monthly_avg["AvgAttendance"].shift(1)
            monthly_avg["Delta"] = (monthly_avg["AvgAttendance"] - monthly_avg["PrevAttendance"]).round(1)
            monthly_avg["Direction"] = monthly_avg["Delta"].apply(
                lambda x: "⬆️ Improved" if x > 0 else ("⬇️ Declined" if x < 0 else "➡️ Same"))

            delta_display = monthly_avg.dropna(subset=["Delta"]).copy()
            delta_display["AvgAttendance"] = delta_display["AvgAttendance"].map(lambda x: f"{x:.1f}%")
            delta_display["PrevAttendance"] = delta_display["PrevAttendance"].map(lambda x: f"{x:.1f}%")
            delta_display["Delta"] = delta_display["Delta"].map(lambda x: f"{'+' if x>0 else ''}{x}%")
            st.dataframe(delta_display[["Period", "PrevAttendance", "AvgAttendance", "Delta", "Direction"]],
                         use_container_width=True)
        else:
            st.info("Need at least 2 periods for delta analysis.")

        # ── SECTION 4: Best & Worst Periods ──────────────────────────────
        st.subheader("🏆 Best & Worst Performing Periods")
        col1, col2 = st.columns(2)
        with col1:
            best = monthly_avg.sort_values("AvgAttendance", ascending=False).iloc[0]
            st.success(f"🏆 **Best:** {best['Period']} — {best['AvgAttendance']:.1f}%")
        with col2:
            worst = monthly_avg.sort_values("AvgAttendance").iloc[0]
            st.error(f"⚠️ **Worst:** {worst['Period']} — {worst['AvgAttendance']:.1f}%")

        # ── SECTION 5: Seasonal Pattern Detection ────────────────────────
        st.subheader("🌡️ Seasonal / Holiday Pattern Detection")
        st.info("""
        **Known seasonal dips to watch for:**
        - **Ramadan** (Mar/Apr): Attendance often drops 5–10%
        - **Summer** (Jun–Aug): Heat-related absences increase
        - **Eid breaks**: Short spike in absences before/after

        Compare your data above against these known patterns.
        """)

        # ── SECTION 6: Individual Rider Journey ──────────────────────────
        st.subheader("👤 Individual Rider Attendance Journey")

        all_riders = sorted(combined["Rider"].unique())
        selected_rider = st.selectbox("Select a rider to track:", all_riders)

        rider_data = combined[combined["Rider"] == selected_rider][["Label", "AttendancePct", "Present", "Absent", "WorkingDays"]]

        if not rider_data.empty:
            fig_rider = px.bar(rider_data, x="Label", y="AttendancePct",
                               color="AttendancePct",
                               color_continuous_scale="RdYlGn",
                               title=f"Attendance Journey: {selected_rider}",
                               text="AttendancePct",
                               hover_data=["Present", "Absent", "WorkingDays"])
            fig_rider.update_traces(texttemplate="%{text}%", textposition="outside")
            fig_rider.add_hline(y=75, line_dash="dash", line_color="orange",
                                annotation_text="75% Target")
            fig_rider.update_layout(coloraxis_showscale=False)
            fig_rider.update_yaxes(range=[0, 110])
            st.plotly_chart(fig_rider, use_container_width=True)

            avg = rider_data["AttendancePct"].mean()
            if avg >= 90:
                st.success(f"⭐ {selected_rider} averages {avg:.1f}% — Star Performer")
            elif avg >= 75:
                st.info(f"✅ {selected_rider} averages {avg:.1f}% — On Target")
            elif avg >= 60:
                st.warning(f"⚠️ {selected_rider} averages {avg:.1f}% — Needs Improvement")
            else:
                st.error(f"🚨 {selected_rider} averages {avg:.1f}% — Urgent Intervention Required")

        # ── SECTION 7: Attendance Heatmap ────────────────────────────────
        st.subheader("🗺️ Attendance Heatmap — All Riders × All Periods")
        heatmap_data = combined.pivot_table(index="Rider", columns="Label",
                                             values="AttendancePct", aggfunc="mean")
        if not heatmap_data.empty and len(heatmap_data) <= 60:
            fig_heat = px.imshow(heatmap_data,
                                 color_continuous_scale="RdYlGn",
                                 title="Attendance % Heatmap (Rider × Period)",
                                 aspect="auto",
                                 zmin=0, zmax=100)
            fig_heat.update_layout(height=max(400, len(heatmap_data) * 20))
            st.plotly_chart(fig_heat, use_container_width=True)
        elif len(heatmap_data) > 60:
            st.info("Too many riders for heatmap — showing top 40 by avg attendance.")
            top40 = heatmap_data.mean(axis=1).nlargest(40).index
            fig_heat = px.imshow(heatmap_data.loc[top40],
                                 color_continuous_scale="RdYlGn",
                                 title="Attendance % Heatmap — Top 40 Riders",
                                 aspect="auto", zmin=0, zmax=100)
            fig_heat.update_layout(height=800)
            st.plotly_chart(fig_heat, use_container_width=True)

        # ── KPI Summary ──────────────────────────────────────────────────
        st.markdown("---")
        st.subheader("📋 Summary")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Riders", combined["Rider"].nunique())
        c2.metric("Overall Avg Attendance", f"{combined['AttendancePct'].mean():.1f}%")
        c3.metric("Periods Analyzed", combined["Label"].nunique())
        above_target = (combined.groupby("Rider")["AttendancePct"].mean() >= 75).sum()
        c4.metric("Riders Above 75% Target", above_target)

        # ── Export ───────────────────────────────────────────────────────
        st.subheader("⬇️ Export Report")
        out = BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            combined.to_excel(writer, sheet_name="All Data", index=False)
            monthly_avg.to_excel(writer, sheet_name="Period Summary", index=False)
            heatmap_data.to_excel(writer, sheet_name="Heatmap")
        st.download_button("Download Excel Report", out.getvalue(),
                           file_name="monthly_attendance_report.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

else:
    st.info("👆 Please upload the noon operational Excel file to get started.")
    with st.expander("ℹ️ Expected Data Format"):
        st.markdown("""
        **Attendance sheets (NIM / NF / SM):**
        - Column 1: Rider Name
        - Remaining columns: Daily attendance (P / A / WO / H)

        **Labelling tip:** Label sheets as `Month-Team` (e.g. `Apr-NIM`, `May-NF`) for full cross-team comparison.
        """)
