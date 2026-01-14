import sys
import pandas as pd


def categorize_nps(score):
    """Return 'promoter', 'passive', or 'detractor' based on a 0–10 score."""
    if score >= 9:
        return "promoter"
    elif score >= 7:
        return "passive"
    else:
        return "detractor"


def main():
    if len(sys.argv) != 2:
        print("Usage: python nps_from_votes.py <excel_workbook_path>")
        sys.exit(1)

    workbook_path = sys.argv[1]

    # Read the Votes sheet
    try:
        df = pd.read_excel(workbook_path, sheet_name="Votes", header=None)
    except FileNotFoundError:
        print(f"Error: file not found: {workbook_path}")
        sys.exit(1)
    except ValueError as e:
        print(f"Error reading Excel file: {e}")
        sys.exit(1)

    # 5th column is index 4 (0-based)
    scores_series = df.iloc[:, 4]

    # Keep only numeric, drop NaNs
    scores = scores_series.dropna().astype(float).tolist()
    if not scores:
        print("No valid scores found in 5th column of 'Votes' sheet.")
        sys.exit(1)

    total = len(scores)
    promoters = sum(1 for s in scores if categorize_nps(s) == "promoter")
    detractors = sum(1 for s in scores if categorize_nps(s) == "detractor")

    promoters_pct = 100.0 * promoters / total
    detractors_pct = 100.0 * detractors / total
    nps = promoters_pct - detractors_pct

    print(f"Total responses: {total}")
    print(f"Promoters: {promoters} ({promoters_pct:.1f}%)")
    print(f"Detractors: {detractors} ({detractors_pct:.1f}%)")
    print(f"NPS: {nps:.1f}")


if __name__ == "__main__":
    main()
