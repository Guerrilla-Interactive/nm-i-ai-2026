#!/usr/bin/env python3
"""Analyze NorgesGruppen COCO dataset and generate DATA-ANALYSIS.md report."""

import json
from pathlib import Path
from collections import Counter

DATA_DIR = Path("/Users/pelle/Documents/github/nm-i-ai-2026/norgesgruppen/data")
OUTPUT = Path("/Users/pelle/Documents/github/nm-i-ai-2026/norgesgruppen/DATA-ANALYSIS.md")

def main():
    ann_path = DATA_DIR / "annotations.json"
    if not ann_path.exists():
        print(f"ERROR: {ann_path} not found. Download and extract the dataset first.")
        return

    with open(ann_path) as f:
        coco = json.load(f)

    images = coco["images"]
    annotations = coco["annotations"]
    categories = coco["categories"]

    # Basic counts
    n_images = len(images)
    n_annotations = len(annotations)
    n_categories = len(categories)

    # Category map
    cat_map = {c["id"]: c["name"] for c in categories}
    cat_ids = sorted(cat_map.keys())

    # Annotations per category
    cat_counts = Counter(a["category_id"] for a in annotations)

    # Annotations per image
    img_ann_counts = Counter(a["image_id"] for a in annotations)
    avg_anns_per_img = n_annotations / n_images if n_images else 0
    min_anns = min(img_ann_counts.values()) if img_ann_counts else 0
    max_anns = max(img_ann_counts.values()) if img_ann_counts else 0

    # Image dimensions
    dims = Counter((img["width"], img["height"]) for img in images)

    # Top 20 most common categories
    top20 = cat_counts.most_common(20)

    # Bottom 20 least common
    all_cat_counts = [(cid, cat_counts.get(cid, 0)) for cid in cat_ids]
    all_cat_counts.sort(key=lambda x: x[1])
    bottom20 = all_cat_counts[:20]

    # Categories with 0 annotations
    zero_cats = [cid for cid, cnt in all_cat_counts if cnt == 0]

    # Categories with < 5 annotations
    rare_cats = [(cid, cnt) for cid, cnt in all_cat_counts if 0 < cnt < 5]

    # iscrowd stats
    crowd_count = sum(1 for a in annotations if a.get("iscrowd", 0))

    # corrected field stats
    corrected_count = sum(1 for a in annotations if a.get("corrected", False))

    # Bbox stats
    widths = [a["bbox"][2] for a in annotations]
    heights = [a["bbox"][3] for a in annotations]
    areas = [a.get("area", a["bbox"][2] * a["bbox"][3]) for a in annotations]

    # Store sections (from file_name patterns)
    sections = Counter()
    for img in images:
        fn = img["file_name"]
        # Try to extract section from filename
        parts = fn.replace("/", "_").split("_")
        sections[fn.split("/")[0] if "/" in fn else "root"] += 1

    # Generate report
    lines = []
    lines.append("# NorgesGruppen Dataset Analysis")
    lines.append("")
    lines.append(f"> Generated from `annotations.json` ({ann_path})")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| Total images | {n_images} |")
    lines.append(f"| Total annotations | {n_annotations} |")
    lines.append(f"| Total categories | {n_categories} |")
    lines.append(f"| Category ID range | {min(cat_ids)}–{max(cat_ids)} |")
    lines.append(f"| Avg annotations/image | {avg_anns_per_img:.1f} |")
    lines.append(f"| Min annotations/image | {min_anns} |")
    lines.append(f"| Max annotations/image | {max_anns} |")
    lines.append(f"| iscrowd annotations | {crowd_count} |")
    lines.append(f"| corrected annotations | {corrected_count} |")
    lines.append("")

    lines.append("## Image Dimensions")
    lines.append("")
    for (w, h), count in dims.most_common():
        lines.append(f"- {w}x{h}: {count} images ({100*count/n_images:.1f}%)")
    lines.append("")

    lines.append("## Bounding Box Statistics")
    lines.append("")
    lines.append(f"| Metric | Width (px) | Height (px) | Area (px²) |")
    lines.append(f"|---|---|---|---|")
    lines.append(f"| Min | {min(widths):.1f} | {min(heights):.1f} | {min(areas):.0f} |")
    lines.append(f"| Max | {max(widths):.1f} | {max(heights):.1f} | {max(areas):.0f} |")
    lines.append(f"| Mean | {sum(widths)/len(widths):.1f} | {sum(heights)/len(heights):.1f} | {sum(areas)/len(areas):.0f} |")
    lines.append(f"| Median | {sorted(widths)[len(widths)//2]:.1f} | {sorted(heights)[len(heights)//2]:.1f} | {sorted(areas)[len(areas)//2]:.0f} |")
    lines.append("")

    if zero_cats:
        lines.append(f"## Categories with ZERO annotations ({len(zero_cats)})")
        lines.append("")
        for cid in zero_cats:
            lines.append(f"- ID {cid}: {cat_map.get(cid, '???')}")
        lines.append("")

    if rare_cats:
        lines.append(f"## Rare Categories (<5 annotations) ({len(rare_cats)})")
        lines.append("")
        lines.append("| ID | Name | Count |")
        lines.append("|---|---|---|")
        for cid, cnt in rare_cats:
            lines.append(f"| {cid} | {cat_map.get(cid, '???')} | {cnt} |")
        lines.append("")

    lines.append("## Top 20 Most Common Categories")
    lines.append("")
    lines.append("| Rank | ID | Name | Count | % of Total |")
    lines.append("|---|---|---|---|---|")
    for i, (cid, cnt) in enumerate(top20, 1):
        lines.append(f"| {i} | {cid} | {cat_map.get(cid, '???')} | {cnt} | {100*cnt/n_annotations:.1f}% |")
    lines.append("")

    lines.append("## Bottom 20 Least Common Categories (with >0)")
    lines.append("")
    lines.append("| ID | Name | Count |")
    lines.append("|---|---|---|")
    non_zero_bottom = [(cid, cnt) for cid, cnt in all_cat_counts if cnt > 0][:20]
    for cid, cnt in non_zero_bottom:
        lines.append(f"| {cid} | {cat_map.get(cid, '???')} | {cnt} |")
    lines.append("")

    lines.append("## Full Category Distribution")
    lines.append("")
    lines.append("| ID | Name | Count |")
    lines.append("|---|---|---|")
    for cid in cat_ids:
        cnt = cat_counts.get(cid, 0)
        lines.append(f"| {cid} | {cat_map.get(cid, '???')} | {cnt} |")
    lines.append("")

    # File sections
    lines.append("## Image File Sections")
    lines.append("")
    for section, count in sections.most_common():
        lines.append(f"- `{section}`: {count} images")
    lines.append("")

    report = "\n".join(lines)
    OUTPUT.write_text(report)
    print(f"Analysis saved to {OUTPUT}")
    print(f"\nQuick summary: {n_images} images, {n_annotations} annotations, {n_categories} categories")
    print(f"Avg {avg_anns_per_img:.1f} annotations/image, range [{min_anns}, {max_anns}]")
    if zero_cats:
        print(f"WARNING: {len(zero_cats)} categories have ZERO annotations")
    if rare_cats:
        print(f"WARNING: {len(rare_cats)} categories have <5 annotations")

    # Also save category names for YAML generation
    names_path = DATA_DIR / "category_names.json"
    names_list = [cat_map.get(i, f"class_{i}") for i in range(n_categories)]
    with open(names_path, "w") as f:
        json.dump(names_list, f)
    print(f"Category names saved to {names_path}")


if __name__ == "__main__":
    main()
