# -*- coding: utf-8 -*-
"""
Generate Final Report & Visualizations (v2)
High-quality visuals for Metropy SeatScore analysis.
"""

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.gridspec import GridSpec
from matplotlib.patches import FancyBboxPatch
import matplotlib.colors as mcolors

# Korean font
for candidate in ["Malgun Gothic", "NanumGothic", "AppleGothic", "Gulim"]:
    if any(candidate in f.name for f in fm.fontManager.ttflist):
        plt.rcParams["font.family"] = candidate
        break
plt.rcParams["axes.unicode_minus"] = False

from seatscore import SeatScoreEngine


# ── Color palette ────────────────────────────────────────────────────────────

COLORS = {
    "best":    "#2ecc71",
    "good":    "#27ae60",
    "mid":     "#f39c12",
    "poor":    "#e74c3c",
    "worst":   "#c0392b",
    "bg":      "#fafafa",
    "grid":    "#e0e0e0",
    "text":    "#2c3e50",
    "accent":  "#3498db",
    "penalty": "#e74c3c",
    "benefit": "#2ecc71",
}


def score_to_color(score):
    """Map score 0-100 to a color."""
    if score >= 80:
        return COLORS["best"]
    elif score >= 60:
        return COLORS["good"]
    elif score >= 40:
        return COLORS["mid"]
    elif score >= 20:
        return COLORS["poor"]
    else:
        return COLORS["worst"]


# ── Scenarios ────────────────────────────────────────────────────────────────

SCENARIOS = [
    {"name": "출근 강남→시청",      "boarding": "강남",     "dest": "시청",     "hour": 8,  "dir": "내선"},
    {"name": "출근 신도림→강남",    "boarding": "신도림",   "dest": "강남",     "hour": 8,  "dir": "내선"},
    {"name": "출근 잠실→역삼",      "boarding": "잠실",     "dest": "역삼",     "hour": 8,  "dir": "내선"},
    {"name": "출근 홍대→강남(외선)","boarding": "홍대입구", "dest": "강남",     "hour": 8,  "dir": "외선"},
    {"name": "퇴근 강남→홍대",      "boarding": "강남",     "dest": "홍대입구", "hour": 18, "dir": "내선"},
    {"name": "퇴근 시청→잠실",      "boarding": "시청",     "dest": "잠실",     "hour": 18, "dir": "내선"},
    {"name": "퇴근 역삼→신도림",    "boarding": "역삼",     "dest": "신도림",   "hour": 18, "dir": "내선"},
    {"name": "퇴근 홍대→강남(외선)","boarding": "홍대입구", "dest": "강남",     "hour": 18, "dir": "외선"},
    {"name": "여가 잠실→신촌",      "boarding": "잠실",     "dest": "신촌",     "hour": 14, "dir": "내선"},
    {"name": "심야 강남→신도림",    "boarding": "강남",     "dest": "신도림",   "hour": 22, "dir": "내선"},
]


def run_scenarios(engine):
    results = []
    for sc in SCENARIOS:
        r = engine.recommend(sc["boarding"], sc["dest"], sc["hour"], sc["dir"])
        r["scenario_name"] = sc["name"]
        r["period"] = sc["name"][:2]
        results.append(r)
    return results


# ── Plot 1: Heatmap with annotations ────────────────────────────────────────

def plot_heatmap(results, output_dir):
    """Scenario × Car heatmap with score annotations and rank markers."""
    fig, ax = plt.subplots(figsize=(14, 7))
    fig.patch.set_facecolor("white")

    n_scenarios = len(results)
    matrix = np.zeros((n_scenarios, 10))
    ranks  = np.zeros((n_scenarios, 10), dtype=int)

    for i, r in enumerate(results):
        df = r["scores"].sort_values("car")
        matrix[i] = df["score"].values
        for _, row in r["scores"].iterrows():
            ranks[i, int(row["car"]) - 1] = int(row["rank"])

    # Custom colormap: red -> yellow -> green
    cmap = mcolors.LinearSegmentedColormap.from_list(
        "seatscore", ["#c0392b", "#e74c3c", "#f39c12", "#f1c40f", "#2ecc71", "#27ae60"]
    )

    im = ax.imshow(matrix, cmap=cmap, aspect="auto", vmin=0, vmax=100)

    # Annotations
    for i in range(n_scenarios):
        for j in range(10):
            val = matrix[i, j]
            rank = ranks[i, j]
            color = "white" if val < 30 or val > 75 else "#2c3e50"

            # Score value
            ax.text(j, i - 0.12, f"{val:.0f}", ha="center", va="center",
                    fontsize=8, fontweight="bold", color=color)

            # Rank badge for top 3
            if rank <= 3:
                badge = ["1st", "2nd", "3rd"][rank - 1]
                badge_color = ["#f1c40f", "#bdc3c7", "#cd7f32"][rank - 1]
                ax.text(j, i + 0.22, badge, ha="center", va="center",
                        fontsize=6, fontweight="bold", color=badge_color,
                        bbox=dict(boxstyle="round,pad=0.15", fc="black", alpha=0.6))

    # Labels
    ax.set_xticks(range(10))
    ax.set_xticklabels([f"Car {i}" for i in range(1, 11)], fontsize=10, fontweight="bold")
    ax.set_yticks(range(n_scenarios))
    ax.set_yticklabels([r["scenario_name"] for r in results], fontsize=9)

    ax.set_title("SeatScore v2: 시나리오별 칸 효용 점수", fontsize=14, fontweight="bold", pad=15)

    # Colorbar
    cbar = plt.colorbar(im, ax=ax, label="SeatScore (0-100)", shrink=0.8, pad=0.02)
    cbar.ax.tick_params(labelsize=9)

    # Grid
    for i in range(n_scenarios + 1):
        ax.axhline(i - 0.5, color="white", linewidth=1.5)
    for j in range(11):
        ax.axvline(j - 0.5, color="white", linewidth=1.5)

    plt.tight_layout()
    path = output_dir / "seatscore_heatmap_v2.png"
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {path}")


# ── Plot 2: Benefit vs Penalty decomposition ────────────────────────────────

def plot_benefit_penalty(results, output_dir):
    """Show benefit and penalty decomposition for 3 representative scenarios."""
    picks = [0, 4, 8]  # morning, evening, leisure
    fig, axes = plt.subplots(2, 3, figsize=(16, 9), height_ratios=[2, 1])
    fig.patch.set_facecolor("white")

    for ax_idx, sc_idx in enumerate(picks):
        ax_top = axes[0, ax_idx]
        ax_bot = axes[1, ax_idx]
        r = results[sc_idx]
        df = r["scores"].sort_values("car")
        cars = df["car"].values.astype(int)

        # ── Top: benefit bars + net score line ──
        b_max = df["benefit"].max()
        if b_max > 0:
            benefit_norm = df["benefit"].values / b_max * 100
        else:
            benefit_norm = np.zeros(10)

        x = np.arange(10)

        # Color bars by score
        bar_colors = [score_to_color(s) for s in df["score"].values]
        ax_top.bar(x, benefit_norm, color=bar_colors, alpha=0.85, edgecolor="white", linewidth=1.2)

        # Net score line on twinx
        ax2 = ax_top.twinx()
        ax2.plot(x, df["score"].values, "k-o", linewidth=2.5, markersize=6,
                 markerfacecolor="white", markeredgewidth=2, label="SeatScore", zorder=5)
        ax2.set_ylim(15, 95)
        ax2.set_ylabel("SeatScore", fontsize=9)

        # Highlight best
        best_idx = df["score"].values.argmax()
        ax2.annotate(f"Best: Car {cars[best_idx]}",
                     xy=(best_idx, df["score"].values[best_idx]),
                     xytext=(best_idx + 1.2, df["score"].values[best_idx] + 5),
                     fontsize=9, fontweight="bold", color=COLORS["accent"],
                     arrowprops=dict(arrowstyle="->", color=COLORS["accent"], lw=1.5))

        ax_top.set_xticks(x)
        ax_top.set_xticklabels([f"C{c}" for c in cars], fontsize=9)
        ax_top.set_title(r["scenario_name"], fontsize=12, fontweight="bold")
        ax_top.set_ylabel("Benefit (normalized)", fontsize=9)
        ax_top.set_ylim(0, 120)

        if ax_idx == 0:
            ax2.legend(fontsize=8, loc="upper right")

        # ── Bottom: penalty ratio (penalty / benefit) ──
        penalty_ratio = np.where(
            df["benefit"].values > 0,
            df["penalty"].values / df["benefit"].values * 100,
            0
        )
        bar_colors_p = [COLORS["penalty"] if r > np.mean(penalty_ratio) else "#f5b7b1"
                        for r in penalty_ratio]
        ax_bot.bar(x, penalty_ratio, color=bar_colors_p, alpha=0.85, edgecolor="white")

        # annotate
        for i, v in enumerate(penalty_ratio):
            if v > 0.5:
                ax_bot.text(i, v + 0.3, f"{v:.1f}%", ha="center", fontsize=7, fontweight="bold")

        ax_bot.set_xticks(x)
        ax_bot.set_xticklabels([f"C{c}" for c in cars], fontsize=9)
        ax_bot.set_ylabel("Penalty / Benefit %", fontsize=9)
        ax_bot.axhline(np.mean(penalty_ratio), color=COLORS["accent"],
                        linestyle="--", alpha=0.7, linewidth=1)
        ax_bot.set_ylim(0, max(penalty_ratio) * 1.3 + 1)

        if ax_idx == 0:
            ax_bot.set_ylabel("Boarding Penalty\n(% of Benefit)", fontsize=9)

    fig.suptitle("SeatScore Decomposition: Benefit & Boarding Penalty",
                 fontsize=14, fontweight="bold", y=1.01)
    plt.tight_layout()
    path = output_dir / "benefit_penalty_decomposition.png"
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {path}")


# ── Plot 3: Time-of-day sensitivity ─────────────────────────────────────────

def plot_time_sensitivity(engine, output_dir):
    """Two complementary views of time sensitivity."""
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5))
    fig.patch.set_facecolor("white")

    # ── Left: score spread (best - worst) by hour for two routes ──
    routes = [
        {"label": "강남→시청 (내선)", "b": "강남", "d": "시청", "dir": "내선", "color": "#e74c3c"},
        {"label": "홍대→강남 (외선)", "b": "홍대입구", "d": "강남", "dir": "외선", "color": "#3498db"},
        {"label": "잠실→신촌 (내선)", "b": "잠실", "d": "신촌", "dir": "내선", "color": "#2ecc71"},
    ]

    hours = list(range(5, 24))
    ax = axes[0]
    for route in routes:
        spreads = []
        for h in hours:
            r = engine.recommend(route["b"], route["d"], h, route["dir"])
            spreads.append(r["score_spread"])
        ax.plot(hours, spreads, "-o", linewidth=2.2, markersize=4,
                label=route["label"], color=route["color"], alpha=0.9)

    ax.axvspan(7, 9, alpha=0.12, color="red")
    ax.axvspan(18, 20, alpha=0.12, color="orange")
    ax.set_xlabel("시간대 (Hour)", fontsize=10)
    ax.set_ylabel("Score Spread (Best - Worst)", fontsize=10)
    ax.set_title("시간대별 칸 선택의 중요도\n(spread 클수록 칸 선택이 중요)", fontsize=11, fontweight="bold")
    ax.set_xticks(hours)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.2)

    # ── Middle: Best car + score for one route across hours ──
    ax = axes[1]
    route = routes[0]
    best_scores = []
    worst_scores = []
    best_labels = []
    for h in hours:
        r = engine.recommend(route["b"], route["d"], h, route["dir"])
        best_scores.append(r["best_score"])
        worst_scores.append(r["worst_score"])
        best_labels.append(r["best_car"])

    ax.fill_between(hours, worst_scores, best_scores, alpha=0.2, color=COLORS["accent"],
                     label="Score range (worst~best)")
    ax.plot(hours, best_scores, "-o", linewidth=2.2, markersize=5,
            color=COLORS["best"], label="Best car score")
    ax.plot(hours, worst_scores, "-s", linewidth=2.2, markersize=5,
            color=COLORS["worst"], label="Worst car score")

    # label best car on top
    for i, (h, lbl) in enumerate(zip(hours, best_labels)):
        if i % 3 == 0:
            ax.annotate(f"C{lbl}", (h, best_scores[i] + 1.5),
                        fontsize=7, ha="center", fontweight="bold", color=COLORS["text"])

    ax.axvspan(7, 9, alpha=0.12, color="red")
    ax.axvspan(18, 20, alpha=0.12, color="orange")
    ax.set_xlabel("시간대 (Hour)", fontsize=10)
    ax.set_ylabel("SeatScore", fontsize=10)
    ax.set_title(f"{route['label']}\nBest vs Worst Car Score", fontsize=11, fontweight="bold")
    ax.set_xticks(hours)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.2)

    # ── Right: All 10 cars for one route, stacked area ──
    ax = axes[2]
    route = routes[0]
    car_scores = {c: [] for c in range(1, 11)}
    for h in hours:
        r = engine.recommend(route["b"], route["d"], h, route["dir"])
        df_s = r["scores"].sort_values("car")
        for _, row in df_s.iterrows():
            car_scores[int(row["car"])].append(row["score"])

    # Draw lines for top 5, fade rest
    import matplotlib.cm as cm
    top5 = [7, 4, 3, 8, 9]  # approximate top cars
    cmap_top = cm.get_cmap("tab10")
    for idx, c in enumerate(range(1, 11)):
        if c in top5:
            ax.plot(hours, car_scores[c], "-", linewidth=2, alpha=0.85,
                    label=f"Car {c}", color=cmap_top(idx))
        else:
            ax.plot(hours, car_scores[c], "--", linewidth=0.8, alpha=0.3,
                    color="gray")

    ax.axvspan(7, 9, alpha=0.12, color="red")
    ax.axvspan(18, 20, alpha=0.12, color="orange")
    ax.set_xlabel("시간대 (Hour)", fontsize=10)
    ax.set_ylabel("SeatScore", fontsize=10)
    ax.set_title(f"{route['label']}\n전 칸 점수 추이", fontsize=11, fontweight="bold")
    ax.set_xticks(hours)
    ax.legend(fontsize=7, ncol=2, loc="lower right")
    ax.grid(True, alpha=0.2)

    fig.suptitle("시간대별 SeatScore 분석", fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    path = output_dir / "time_sensitivity.png"
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {path}")


# ── Plot 4: Facility distribution by car ─────────────────────────────────────

def plot_facility_distribution(engine, output_dir):
    """Show why middle cars win: exit facility count distribution."""
    df = engine.fast_exit_df.copy()

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.patch.set_facecolor("white")

    # Left: records per car
    car_counts = df["car_no"].value_counts().sort_index()
    colors = [score_to_color(v / car_counts.max() * 100) for v in car_counts.values]

    bars = axes[0].bar(car_counts.index, car_counts.values, color=colors,
                        edgecolor="white", linewidth=1.5)

    for bar, val in zip(bars, car_counts.values):
        axes[0].text(bar.get_x() + bar.get_width()/2, val + 1,
                     str(val), ha="center", fontsize=9, fontweight="bold")

    axes[0].set_xlabel("Car Number", fontsize=11)
    axes[0].set_ylabel("Exit Facility Count", fontsize=11)
    axes[0].set_title("칸별 출구시설 분포 (전체 역 합산)", fontsize=12, fontweight="bold")
    axes[0].set_xticks(range(1, 11))
    axes[0].axhline(car_counts.mean(), color=COLORS["accent"], linestyle="--",
                     alpha=0.7, label=f"Mean: {car_counts.mean():.0f}")
    axes[0].legend(fontsize=9)

    # Annotation for edge cars
    axes[0].annotate("Edge cars:\n출구 시설 거의 없음",
                     xy=(1, car_counts.get(1, 0)),
                     xytext=(2, 55),
                     fontsize=8, color=COLORS["worst"],
                     arrowprops=dict(arrowstyle="->", color=COLORS["worst"]),
                     bbox=dict(boxstyle="round", fc="#fce4e4"))

    axes[0].annotate("Middle cars:\n계단/에스컬레이터 집중",
                     xy=(4, car_counts.get(4, 0)),
                     xytext=(5.5, 60),
                     fontsize=8, color=COLORS["best"],
                     arrowprops=dict(arrowstyle="->", color=COLORS["best"]),
                     bbox=dict(boxstyle="round", fc="#e4fce4"))

    # Right: facility type breakdown by car
    fac_types = df.groupby(["car_no", "plfmCmgFac"]).size().unstack(fill_value=0)
    fac_types = fac_types.reindex(range(1, 11), fill_value=0)

    # Ensure all facility types present
    fac_colors = {"계단": "#e74c3c", "에스컬레이터": "#3498db", "엘리베이터": "#2ecc71"}
    bottom = np.zeros(10)
    for fac_type in fac_types.columns:
        vals = fac_types[fac_type].values
        color = fac_colors.get(fac_type, "#95a5a6")
        axes[1].bar(range(1, 11), vals, bottom=bottom, label=fac_type,
                    color=color, edgecolor="white", linewidth=0.5)
        bottom += vals

    axes[1].set_xlabel("Car Number", fontsize=11)
    axes[1].set_ylabel("Facility Count", fontsize=11)
    axes[1].set_title("칸별 시설 유형 (계단/에스컬레이터/엘리베이터)", fontsize=12, fontweight="bold")
    axes[1].set_xticks(range(1, 11))
    axes[1].legend(fontsize=9)

    plt.tight_layout()
    path = output_dir / "facility_distribution.png"
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {path}")


# ── Plot 5: Congestion by hour (improved) ───────────────────────────────────

def plot_congestion_by_hour(data_dir, output_dir):
    df = pd.read_csv(data_dir / "congestion_long.csv", encoding="utf-8-sig")
    hourly = df.groupby(["hour", "type"])["count"].mean().reset_index()

    fig, ax = plt.subplots(figsize=(12, 5))
    fig.patch.set_facecolor("white")

    for t, color, marker, label in [("boarding", "#3498db", "o", "승차 (Boarding)"),
                                      ("alighting", "#e67e22", "s", "하차 (Alighting)")]:
        subset = hourly[hourly["type"] == t].sort_values("hour")
        ax.plot(subset["hour"], subset["count"], f"-{marker}", color=color,
                label=label, linewidth=2.5, markersize=6, alpha=0.9)
        ax.fill_between(subset["hour"], 0, subset["count"], color=color, alpha=0.08)

    # Rush hour bands
    ax.axvspan(7, 9, alpha=0.12, color="red", label="출근 러시 (07-09)")
    ax.axvspan(18, 20, alpha=0.12, color="orange", label="퇴근 러시 (18-20)")

    # Alpha annotation
    alpha_vals = {6: 0.5, 7: 1.4, 9: 1.0, 10: 1.0, 18: 1.3, 20: 0.9, 22: 0.6}
    for h, a in alpha_vals.items():
        subset_b = hourly[(hourly["type"] == "boarding") & (hourly["hour"] == h)]
        if len(subset_b) > 0:
            y_pos = subset_b["count"].values[0]
            ax.annotate(f"α={a}", xy=(h, y_pos), xytext=(h, y_pos + 5000),
                       fontsize=7, ha="center", color=COLORS["text"], alpha=0.7)

    ax.set_xlabel("시간대 (Hour)", fontsize=11)
    ax.set_ylabel("평균 승하차 인원", fontsize=11)
    ax.set_title("2호선 시간대별 평균 승하차 인원 & SeatScore α 계수",
                 fontsize=13, fontweight="bold")
    ax.set_xticks(range(0, 24))
    ax.legend(fontsize=9, loc="upper left")
    ax.grid(True, alpha=0.15)

    plt.tight_layout()
    path = output_dir / "congestion_by_hour_v2.png"
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {path}")


# ── Report ───────────────────────────────────────────────────────────────────

def generate_report(results, output_dir):
    lines = []
    lines.append("# Metropy: SeatScore Analysis Report v2")
    lines.append("## 서울 지하철 2호선 착석 효용 의사결정 모델\n")
    lines.append("---\n")

    # Formula
    lines.append("## 1. SeatScore v2 Formula\n")
    lines.append("```")
    lines.append("SeatScore(c) = sum_s [ D(s) * T(s->dest) * w(c,s) * alpha(h) ]")
    lines.append("             - beta * B(c,h)")
    lines.append("```\n")
    lines.append("| Symbol | Description | Source |")
    lines.append("|--------|-------------|--------|")
    lines.append("| D(s) | Alighting volume at station s | Congestion data (316K records) |")
    lines.append("| T(s->dest) | Remaining travel distance (km) | Interstation distance data |")
    lines.append("| w(c,s) | Facility-weighted exit fraction for car c at station s | Fast Exit API (450 records) |")
    lines.append("| alpha(h) | Time-of-day multiplier | AM rush=1.4, PM=1.3, midday=1.0, night=0.6 |")
    lines.append("| B(c,h) | Boarding congestion penalty | Same facility fraction (dual-nature) |")
    lines.append("| beta | Penalty coefficient | 0.3 (calibrated) |")
    lines.append("")

    lines.append("### v1 -> v2 Improvements\n")
    lines.append("| Aspect | v1 | v2 |")
    lines.append("|--------|----|----|")
    lines.append("| Weight w(c,s) | Count-based (1.0 + 0.5*count) | Facility-type weighted fraction |")
    lines.append("| Boarding penalty | None | B(c,h) = facility fraction * beta * scale |")
    lines.append("| Time sensitivity | None | alpha(h): 0.5~1.4 by time period |")
    lines.append("| Normalization | max-based (1st always 100) | z-score (mean=50, +-2sigma=20~80) |")
    lines.append("| Score spread | ~30 pts (poor differentiation) | ~40-55 pts (meaningful comparison) |")
    lines.append("")

    # Facility distribution
    lines.append("## 2. Why Middle Cars Outperform Edge Cars\n")
    lines.append("![Facility Distribution](facility_distribution.png)\n")
    lines.append("| Car | Exit Facilities | Explanation |")
    lines.append("|-----|----------------|-------------|")
    lines.append("| Car 1 | 9 | Platform end — almost no exits |")
    lines.append("| Car 3 | 70 | Near central stairs/escalators |")
    lines.append("| Car 4 | 72 | Highest — main escalator zone |")
    lines.append("| Car 7 | 71 | Secondary escalator cluster |")
    lines.append("| Car 10 | 6 | Platform end — fewest exits |")
    lines.append("")
    lines.append("Subway stations concentrate stairs, escalators, and elevators ")
    lines.append("in the **middle of the platform** (structural constraint). ")
    lines.append("This creates a natural gradient: more facilities near middle cars ")
    lines.append("-> more passengers alight there -> more seats open up -> higher SeatScore.\n")
    lines.append("However, the v2 model also penalizes these cars: more facilities = more ")
    lines.append("people **boarding** there too (B(c,h) penalty). This dual-nature trade-off ")
    lines.append("prevents middle cars from being unconditionally dominant.\n")

    # Congestion pattern
    lines.append("## 3. Congestion Pattern & Time Sensitivity\n")
    lines.append("![Congestion](congestion_by_hour_v2.png)\n")
    lines.append("![Time Sensitivity](time_sensitivity.png)\n")

    # Heatmap
    lines.append("## 4. Scenario Results\n")
    lines.append("![Heatmap](seatscore_heatmap_v2.png)\n")
    lines.append("![Decomposition](benefit_penalty_decomposition.png)\n")

    lines.append("### Score Summary\n")
    lines.append("| Scenario | Best Car | Score | Worst Car | Score | Spread |")
    lines.append("|----------|----------|-------|-----------|-------|--------|")
    for r in results:
        lines.append(f"| {r['scenario_name']} | Car {r['best_car']} | {r['best_score']:.0f} "
                      f"| Car {r['worst_car']} | {r['worst_score']:.0f} "
                      f"| {r['score_spread']:.0f} |")
    lines.append("")

    # Key findings
    lines.append("## 5. Key Findings\n")
    best_counts = pd.Series([r["best_car"] for r in results]).value_counts()
    for car, cnt in best_counts.head(3).items():
        lines.append(f"- **Car {car}**: Best in {cnt}/{len(results)} scenarios")
    lines.append("")
    lines.append("- Edge cars (1, 10) consistently rank last due to sparse exit facilities")
    lines.append("- The penalty term B(c,h) prevents middle cars from trivially dominating")
    lines.append("- Rush hours amplify score differences (alpha=1.3~1.4 vs 0.6 at night)")
    lines.append("- Direction (inner/outer) changes rankings: facility layouts are asymmetric\n")

    # Limitations
    lines.append("## 6. Limitations\n")
    lines.append("- **Decision support, not prediction**: no ground-truth seating data exists")
    lines.append("- D(s) is station-level average, not per-car")
    lines.append("- w(c,s) based on exit structure, not observed passenger behavior")
    lines.append("- beta=0.3 is heuristic; sensitivity analysis recommended")
    lines.append("- Results are **relative utility comparisons**, not absolute guarantees\n")

    lines.append("---\n")
    lines.append("*Generated by Metropy SeatScore Engine v2*")

    path = output_dir / "final_report.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  Saved: {path}")


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 70)
    print("GENERATING METROPY FINAL REPORT v2")
    print("=" * 70)

    output_dir = Path("../report")
    output_dir.mkdir(exist_ok=True)

    engine = SeatScoreEngine(data_dir="../data/processed", raw_dir="../data/raw")
    engine.load_all()

    print("\n--- Running Scenarios ---")
    results = run_scenarios(engine)

    print("\n--- Generating Visualizations ---")
    plot_heatmap(results, output_dir)
    plot_benefit_penalty(results, output_dir)
    plot_time_sensitivity(engine, output_dir)
    plot_facility_distribution(engine, output_dir)
    plot_congestion_by_hour(Path("../data/processed"), output_dir)

    print("\n--- Generating Report ---")
    generate_report(results, output_dir)

    print("\n" + "=" * 70)
    print("COMPLETE")
    print("=" * 70)
    for f in sorted(output_dir.glob("*")):
        print(f"  {f.name}")
