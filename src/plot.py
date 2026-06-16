#!/usr/bin/env python3
import os
import sys
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns

AUDIT_DIR = "outputs/audit"
TERM_DIR = "outputs/term_coverage"
OUT_DIR = "outputs/plot"

sns.set_theme(style="whitegrid", palette="muted")
plt.rcParams.update({
    "figure.dpi": 150,
    "savefig.dpi": 150,
    "savefig.bbox": "tight",
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.labelsize": 10,
})

os.makedirs(OUT_DIR, exist_ok=True)


def _load(path):
    return pd.read_csv(path) if os.path.exists(path) else pd.DataFrame()


def plot_split_stats():
    df = _load(f"{AUDIT_DIR}/split_stats.csv")
    if df.empty:
        return
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    for ax, col, title, color in zip(
        axes,
        ["row_count", "duration_seconds", "cs_term_occurrences"],
        ["Số dòng", "Thời lượng (giây)", "Số lần CS term"],
        ["#4c72b0", "#55a868", "#c44e52"],
    ):
        bars = ax.bar(df["split"], df[col], color=color, edgecolor="white")
        ax.set_title(title)
        ax.set_xlabel("Split")
        for b in bars:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.5,
                    str(int(b.get_height())), ha="center", va="bottom", fontsize=8)
    fig.suptitle("Thống kê theo Split", fontweight="bold")
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/split_stats.png")
    plt.close(fig)


def plot_topic_stats():
    df = _load(f"{AUDIT_DIR}/topic_stats.csv")
    if df.empty:
        return
    top = df.nlargest(15, "row_count")
    fig, axes = plt.subplots(1, 2, figsize=(16, 5))
    colors = sns.color_palette("viridis", len(top))
    axes[0].barh(top["topic"], top["row_count"], color=colors, edgecolor="white")
    axes[0].set_title("Số dòng theo chủ đề (Top 15)")
    axes[0].set_xlabel("Row count")
    axes[0].invert_yaxis()
    axes[1].pie(top["row_count"], labels=top["topic"], autopct="%1.1f%%",
                colors=colors, textprops={"fontsize": 7})
    axes[1].set_title("Tỉ lệ chủ đề")
    fig.suptitle("Phân bố Chủ đề", fontweight="bold")
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/topic_stats.png")
    plt.close(fig)


def plot_duration_stats():
    df = _load(f"{AUDIT_DIR}/duration_stats.csv")
    if df.empty:
        return
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    df_plot = df.set_index("split")
    df_plot[["min_duration", "mean_duration", "max_duration"]].plot(
        kind="bar", ax=axes[0], color=["#4c72b0", "#55a868", "#c44e52"], edgecolor="white"
    )
    axes[0].set_title("Min / Mean / Max Duration (giây)")
    axes[0].set_ylabel("Giây")
    axes[0].tick_params(axis="x", rotation=0)
    axes[1].bar(df["split"], df["total_duration"], color="#8172b2", edgecolor="white")
    axes[1].set_title("Tổng thời lượng (giây)")
    axes[1].set_ylabel("Giây")
    for i, v in enumerate(df["total_duration"]):
        axes[1].text(i, v + 5, str(v), ha="center", fontsize=8)
    fig.suptitle("Thống kê Thời lượng", fontweight="bold")
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/duration_stats.png")
    plt.close(fig)


def plot_quality_issues():
    df = _load(f"{AUDIT_DIR}/data_quality_issues.csv")
    if df.empty:
        return
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    counts = df["issue_type"].value_counts()
    bars = axes[0].bar(counts.index, counts.values,
                       color=sns.color_palette("Set2", len(counts)), edgecolor="white")
    axes[0].set_title("Số lượng theo loại lỗi")
    axes[0].set_ylabel("Count")
    axes[0].tick_params(axis="x", rotation=25)
    for b in bars:
        axes[0].text(b.get_x() + b.get_width() / 2, b.get_height() + 0.5,
                     str(int(b.get_height())), ha="center", fontsize=8)
    sc = df.groupby("split")["issue_type"].count()
    axes[1].bar(sc.index, sc.values, color="#d46a6a", edgecolor="white")
    axes[1].set_title("Số lượng lỗi theo Split")
    axes[1].set_ylabel("Count")
    for i, v in enumerate(sc.values):
        axes[1].text(i, v + 0.5, str(v), ha="center", fontsize=8)
    fig.suptitle("Vấn đề Chất lượng Dữ liệu", fontweight="bold")
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/data_quality_issues.png")
    plt.close(fig)


def plot_inventory():
    df = _load(f"{TERM_DIR}/cs_terms_inventory.csv")
    if df.empty:
        return
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # Occurrence histogram (log scale)
    occ = df["occurrence_count"]
    axes[0].hist(np.log10(occ[occ > 0]), bins=50, color="#4c72b0", edgecolor="white")
    axes[0].set_title("Phân bố Log10(Occurrence Count)")
    axes[0].set_xlabel("log10(count)")
    axes[0].set_ylabel("Số term")

    # Frequency bucket
    bucket_order = ["singleton", "rare", "medium", "common", "unknown"]
    bucket_counts = df["frequency_bucket"].value_counts().reindex(bucket_order, fill_value=0)
    bars = axes[1].bar(bucket_counts.index, bucket_counts.values,
                       color=sns.color_palette("Set2", len(bucket_counts)), edgecolor="white")
    axes[1].set_title("Phân bố Frequency Bucket")
    axes[1].tick_params(axis="x", rotation=25)
    for b in bars:
        axes[1].text(b.get_x() + b.get_width() / 2, b.get_height() + 0.5,
                     str(int(b.get_height())), ha="center", fontsize=8)

    # Common vs rare pie
    counts = [df["is_common_term"].sum(), (~df["is_common_term"]).sum()]
    axes[2].pie(counts, labels=["Common (≥20)", "Không common"],
                autopct="%1.1f%%", colors=["#55a868", "#c44e52"], startangle=90)
    axes[2].set_title("Common vs Không Common")

    fig.suptitle("CS Terms Inventory", fontweight="bold")
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/cs_terms_inventory.png")
    plt.close(fig)

    # Top 20 terms
    top20 = df.head(20)
    fig2, ax2 = plt.subplots(figsize=(12, 6))
    bars = ax2.barh(top20["normalized_term"][::-1], top20["occurrence_count"][::-1],
                    color=sns.color_palette("viridis", 20)[::-1], edgecolor="white")
    ax2.set_title("Top 20 CS Terms theo Occurrence Count", fontweight="bold")
    ax2.set_xlabel("Count")
    for b in bars:
        ax2.text(b.get_width() + 1, b.get_y() + b.get_height() / 2,
                 str(int(b.get_width())), va="center", fontsize=8)
    fig2.tight_layout()
    fig2.savefig(f"{OUT_DIR}/cs_terms_top20.png")
    plt.close(fig2)


def plot_by_split():
    df = _load(f"{TERM_DIR}/cs_terms_by_split.csv")
    if df.empty:
        return
    top = df.nlargest(30, "occurrence_count")
    pivot = top.pivot_table(index="normalized_term", columns="split",
                            values="occurrence_count", fill_value=0)
    fig, ax = plt.subplots(figsize=(14, 8))
    pivot.plot(kind="barh", stacked=True, ax=ax,
               color=sns.color_palette("Set2", len(pivot.columns)), edgecolor="white")
    ax.set_title("Top 30 Terms phân bố theo Split", fontweight="bold")
    ax.set_xlabel("Occurrence count")
    ax.invert_yaxis()
    ax.legend(title="Split", bbox_to_anchor=(1.02, 1), loc="upper left")
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/cs_terms_by_split.png")
    plt.close(fig)


def plot_by_topic():
    df = _load(f"{TERM_DIR}/cs_terms_by_topic.csv")
    if df.empty:
        return
    topic_totals = df.groupby("topic")["occurrence_count"].sum().nlargest(12)
    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.barh(topic_totals.index[::-1], topic_totals.values[::-1],
                   color=sns.color_palette("viridis", len(topic_totals))[::-1], edgecolor="white")
    ax.set_title("Tổng Occurrences theo Chủ đề (Top 12)", fontweight="bold")
    ax.set_xlabel("Count")
    for b in bars:
        ax.text(b.get_width() + 1, b.get_y() + b.get_height() / 2,
                str(int(b.get_width())), va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/cs_terms_by_topic.png")
    plt.close(fig)


def plot_split_overlap():
    rare = _load(f"{TERM_DIR}/rare_terms.csv")
    common = _load(f"{TERM_DIR}/common_terms.csv")
    hard_only = _load(f"{TERM_DIR}/hard_only_terms.csv")
    train_hard = _load(f"{TERM_DIR}/train_seen_hard_terms.csv")
    unseen = _load(f"{TERM_DIR}/unseen_in_train_terms.csv")

    groups = [
        ("Common\n(≥20)", len(common)),
        ("Rare\n(<5)", len(rare)),
        ("Hard-only", len(hard_only)),
        ("Train-seen\nHard", len(train_hard)),
        ("Unseen\nin Train", len(unseen)),
    ]
    labels, values = zip(*groups)
    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(labels, values, color=sns.color_palette("Set2", len(labels)), edgecolor="white")
    ax.set_title("Phân tích Chồng lấn Term giữa các Split", fontweight="bold")
    ax.set_ylabel("Số term unique")
    for b in bars:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.5,
                str(int(b.get_height())), ha="center", fontsize=10)
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/split_overlap.png")
    plt.close(fig)


def plot_abbreviation():
    df = _load(f"{TERM_DIR}/cs_terms_inventory.csv")
    if df.empty:
        return
    cross = pd.crosstab(df["frequency_bucket"], df["is_abbreviation"])
    cross = cross.reindex(["singleton", "rare", "medium", "common"], fill_value=0)
    fig, ax = plt.subplots(figsize=(10, 5))
    cross.plot(kind="bar", stacked=True, ax=ax,
               color=["#4c72b0", "#c44e52"], edgecolor="white")
    ax.set_title("Phân bố Từ viết tắt theo Frequency Bucket", fontweight="bold")
    ax.set_xlabel("Frequency bucket")
    ax.set_ylabel("Số term")
    ax.legend(["Không viết tắt", "Viết tắt"])
    ax.tick_params(axis="x", rotation=0)
    for c in ax.containers:
        ax.bar_label(c, label_type="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/abbreviation_dist.png")
    plt.close(fig)


def plot_overall_summary(stats):
    """Composite summary figure combining key metrics."""
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.axis("off")
    lines = [
        "=== ViMedCSS Eval Pipeline Summary ===",
        "",
        "[Audit]",
    ]
    if stats.get("total_rows"):
        lines.append(f"  Total rows:        {stats['total_rows']:,}")
        lines.append(f"  Total duration:    {stats.get('total_duration_hours', 0)} hours")
        lines.append(f"  Duplicate seg_ids: {stats.get('duplicate_segment_id_count', 0)}")
        lines.append(f"  Missing transcripts: {stats.get('missing_transcript_count', 0)}")
        lines.append(f"  Missing cs_terms:   {stats.get('missing_cs_terms_count', 0)}")
    lines.append("")
    lines.append("[Term Coverage]")
    if stats.get("total_unique_normalized_terms"):
        lines.append(f"  Total raw occurrences:    {stats.get('total_raw_term_occurrences', 0):,}")
        lines.append(f"  Total unique terms:       {stats.get('total_unique_normalized_terms', 0):,}")
        lines.append(f"  Common terms (>=20):      {stats.get('common_terms_count', 0):,}")
        lines.append(f"  Rare terms (<5):          {stats.get('rare_terms_count', 0):,}")
        lines.append(f"  Hard-only terms:          {stats.get('hard_only_terms_count', 0):,}")
        lines.append(f"  Train-seen hard terms:    {stats.get('train_seen_hard_terms_count', 0):,}")
        lines.append(f"  Unseen-in-train terms:    {stats.get('unseen_in_train_terms_count', 0):,}")
    text = "\n".join(lines)
    ax.text(0.05, 0.95, text, transform=ax.transAxes, fontfamily="monospace",
            fontsize=11, va="top", ha="left")
    fig.savefig(f"{OUT_DIR}/pipeline_summary.png")
    plt.close(fig)


def plot_dashboard():
    """Single dashboard combining all key charts into one figure."""
    import json
    # Load data
    split_df = _load(f"{AUDIT_DIR}/split_stats.csv")
    topic_df = _load(f"{AUDIT_DIR}/topic_stats.csv")
    duration_df = _load(f"{AUDIT_DIR}/duration_stats.csv")
    quality_df = _load(f"{AUDIT_DIR}/data_quality_issues.csv")
    inventory_df = _load(f"{TERM_DIR}/cs_terms_inventory.csv")
    split_term_df = _load(f"{TERM_DIR}/cs_terms_by_split.csv")
    hard_only_df = _load(f"{TERM_DIR}/hard_only_terms.csv")
    unseen_df = _load(f"{TERM_DIR}/unseen_in_train_terms.csv")

    fig = plt.figure(figsize=(22, 16))
    gs = fig.add_gridspec(3, 4, hspace=0.35, wspace=0.35)

    # (0,0): Split stats bar
    ax1 = fig.add_subplot(gs[0, 0])
    if not split_df.empty:
        x = range(len(split_df))
        w = 0.25
        ax1.bar([i - w for i in x], split_df["row_count"], w, label="Row", color="#4c72b0", edgecolor="white")
        ax1.bar(x, split_df["cs_term_occurrences"], w, label="CS Term", color="#c44e52", edgecolor="white")
        ax1.set_xticks(x)
        ax1.set_xticklabels(split_df["split"])
        ax1.set_title("Split: Row vs CS Term")
        ax1.legend(fontsize=7)

    # (0,1): Topic top 10
    ax2 = fig.add_subplot(gs[0, 1])
    if not topic_df.empty:
        top = topic_df.nlargest(10, "row_count")
        ax2.barh(top["topic"][::-1], top["row_count"][::-1], color="#55a868", edgecolor="white")
        ax2.set_title("Top 10 Chủ đề")
        ax2.invert_yaxis()
        ax2.tick_params(labelsize=7)

    # (0,2): Duration
    ax3 = fig.add_subplot(gs[0, 2])
    if not duration_df.empty:
        ax3.bar(duration_df["split"], duration_df["mean_duration"],
                color="#8172b2", edgecolor="white")
        ax3.set_title("Mean Duration (giây)")
        ax3.tick_params(axis="x", rotation=30, labelsize=7)

    # (0,3): Quality issues
    ax4 = fig.add_subplot(gs[0, 3])
    if not quality_df.empty:
        qc = quality_df["issue_type"].value_counts()
        ax4.pie(qc.values, labels=qc.index, autopct="%1.1f%%",
                colors=sns.color_palette("Set2", len(qc)), textprops={"fontsize": 7})
        ax4.set_title("Data Quality Issues")

    # (1,0): Inventory - frequency bucket
    ax5 = fig.add_subplot(gs[1, 0])
    if not inventory_df.empty:
        b_order = ["singleton", "rare", "medium", "common"]
        b_counts = inventory_df["frequency_bucket"].value_counts().reindex(b_order, fill_value=0)
        ax5.bar(b_counts.index, b_counts.values,
                color=sns.color_palette("Set2", len(b_counts)), edgecolor="white")
        ax5.set_title("Frequency Bucket")
        ax5.tick_params(axis="x", rotation=25, labelsize=7)

    # (1,1): Top 10 terms
    ax6 = fig.add_subplot(gs[1, 1])
    if not inventory_df.empty:
        top10 = inventory_df.head(10)
        ax6.barh(top10["normalized_term"][::-1], top10["occurrence_count"][::-1],
                 color=sns.color_palette("viridis", 10)[::-1], edgecolor="white")
        ax6.set_title("Top 10 CS Terms")
        ax6.tick_params(labelsize=7)

    # (1,2): Split term distribution top 15
    ax7 = fig.add_subplot(gs[1, 2])
    if not split_term_df.empty:
        top = split_term_df.nlargest(15, "occurrence_count")
        pivot = top.pivot_table(index="normalized_term", columns="split",
                                values="occurrence_count", fill_value=0)
        pivot.plot(kind="barh", stacked=True, ax=ax7, legend=False,
                   color=sns.color_palette("Set2", len(pivot.columns)), edgecolor="white")
        ax7.set_title("Terms by Split (Top 15)")
        ax7.invert_yaxis()
        ax7.tick_params(labelsize=7)

    # (1,3): Hard-only vs Unseen
    ax8 = fig.add_subplot(gs[1, 3])
    vals = [len(hard_only_df), len(unseen_df)]
    labels = ["Hard-only", "Unseen-in-Train"]
    ax8.bar(labels, vals, color=["#c44e52", "#8172b2"], edgecolor="white")
    ax8.set_title("Split Overlap")
    for i, v in enumerate(vals):
        ax8.text(i, v + 0.5, str(v), ha="center", fontsize=9)

    # (2,0:): Abbreviation cross-tab
    ax9 = fig.add_subplot(gs[2, 0])
    if not inventory_df.empty:
        cross = pd.crosstab(inventory_df["frequency_bucket"], inventory_df["is_abbreviation"])
        cross = cross.reindex(["singleton", "rare", "medium", "common"], fill_value=0)
        cross.plot(kind="bar", stacked=True, ax=ax9,
                   color=["#4c72b0", "#c44e52"], edgecolor="white", legend=False)
        ax9.set_title("Abbreviation by Bucket")
        ax9.tick_params(axis="x", rotation=25, labelsize=7)

    # (2,1): Occurrence histogram
    ax10 = fig.add_subplot(gs[2, 1])
    if not inventory_df.empty:
        occ = inventory_df["occurrence_count"]
        ax10.hist(np.log10(occ[occ > 0]), bins=40, color="#55a868", edgecolor="white")
        ax10.set_title("Log10(Occurrence) Histogram")
        ax10.set_xlabel("log10")
        ax10.tick_params(labelsize=7)

    # (2,2): Term availability across splits (histogram of how many splits a term appears in)
    ax11 = fig.add_subplot(gs[2, 2])
    if not inventory_df.empty:
        splits_per_term = inventory_df["splits_present"].dropna().apply(
            lambda s: len(s.split(";")) if isinstance(s, str) else 0
        )
        counts = splits_per_term.value_counts().sort_index()
        ax11.bar(counts.index.astype(str), counts.values,
                 color="#4c72b0", edgecolor="white")
        ax11.set_title("Terms by # of Splits")
        ax11.set_xlabel("Số splits")
        ax11.tick_params(labelsize=7)

    # (2,3): Topic-wise total term occurrences
    ax12 = fig.add_subplot(gs[2, 3])
    by_topic = _load(f"{TERM_DIR}/cs_terms_by_topic.csv")
    if not by_topic.empty:
        tt = by_topic.groupby("topic")["occurrence_count"].sum().nlargest(8)
        ax12.barh(tt.index[::-1], tt.values[::-1],
                  color=sns.color_palette("mako", len(tt))[::-1], edgecolor="white")
        ax12.set_title("Term Occurrences by Topic")
        ax12.tick_params(labelsize=7)

    fig.suptitle("ViMedCSS Eval Pipeline Dashboard", fontweight="bold", fontsize=16, y=0.98)
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/dashboard.png", facecolor="white")
    plt.close(fig)


def collect_stats():
    """Collect summary stats from existing output files for the summary plot."""
    import json
    stats = {}
    try:
        with open(f"{AUDIT_DIR}/local_dataset_stats.json") as f:
            s = json.load(f)
            stats.update(s)
    except Exception:
        pass

    df = _load(f"{TERM_DIR}/cs_terms_inventory.csv")
    if not df.empty:
        stats["total_unique_normalized_terms"] = len(df)
        stats["common_terms_count"] = int(df["is_common_term"].sum())
        stats["rare_terms_count"] = len(df[df["frequency_bucket"].isin(["rare", "singleton"])])
        stats["hard_only_terms_count"] = len(_load(f"{TERM_DIR}/hard_only_terms.csv"))
        stats["train_seen_hard_terms_count"] = len(_load(f"{TERM_DIR}/train_seen_hard_terms.csv"))
        stats["unseen_in_train_terms_count"] = len(_load(f"{TERM_DIR}/unseen_in_train_terms.csv"))
    return stats


def main():
    print("Generating audit plots...")
    plot_split_stats()
    plot_topic_stats()
    plot_duration_stats()
    plot_quality_issues()

    print("Generating term coverage plots...")
    plot_inventory()
    plot_by_split()
    plot_by_topic()
    plot_split_overlap()
    plot_abbreviation()

    print("Generating dashboard...")
    plot_dashboard()

    stats = collect_stats()
    plot_overall_summary(stats)

    print(f"\nAll plots saved to {OUT_DIR}/:")
    for f in sorted(os.listdir(OUT_DIR)):
        print(f"  {f}")


if __name__ == "__main__":
    main()
