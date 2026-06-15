#!/usr/bin/env python3
"""
AVANA Women Safety Dataset Builder
Sources: NCRB (2020-2022), Karnataka Police (2023-2025), OpenCity
Output: women_safety_dataset.csv
"""

import csv
import math
import os

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

# ── District geo coordinates (centroids) ──
DISTRICT_GEO = {
    "Bagalkote": (16.1800, 75.6960),
    "Ballari": (15.1500, 76.9150),
    "Belagavi": (15.8700, 74.5000),
    "Bengaluru Rural": (12.9500, 77.4500),
    "Bengaluru Urban": (12.9716, 77.5946),
    "Bidar": (17.9100, 77.5300),
    "Chamarajanagara": (11.9300, 76.9400),
    "Chikkaballapura": (13.4300, 77.7300),
    "Chikkamagaluru": (13.3200, 75.7700),
    "Chitradurga": (14.2300, 76.4000),
    "Dakshina Kannada": (12.8700, 74.8800),
    "Davanagere": (14.4700, 75.9200),
    "Dharwad": (15.4600, 75.0100),
    "Gadag": (15.4200, 75.6200),
    "Hassan": (13.0100, 76.1000),
    "Haveri": (14.8000, 75.4000),
    "Kalaburagi": (17.3300, 76.8300),
    "Kodagu": (12.4200, 75.7400),
    "Kolar": (13.1400, 78.1300),
    "Koppal": (15.3500, 76.1500),
    "Mandya": (12.5200, 76.9000),
    "Mysuru": (12.3000, 76.6400),
    "Raichur": (16.2100, 77.3600),
    "Ramanagara": (12.7200, 77.2800),
    "Shivamogga": (13.9300, 75.5700),
    "Tumakuru": (13.3400, 77.1000),
    "Udupi": (13.3400, 74.7500),
    "Uttara Kannada": (14.6000, 74.7000),
    "Vijayanagara": (15.1500, 76.9150),
    "Vijayapura": (16.8300, 75.7100),
    "Yadgir": (16.7700, 77.1400),
}

DISTRICT_NAME_MAP = {
    "Bagalkot": "Bagalkote",
    "Bagalkote": "Bagalkote",
    "Ballari": "Ballari",
    "Belagavi": "Belagavi",
    "Belagavi City": "Belagavi",
    "Belagavi District": "Belagavi",
    "Belagavi Dist": "Belagavi",
    "Bengaluru City": "Bengaluru Urban",
    "Bengaluru District": "Bengaluru Urban",
    "Bengaluru Dist": "Bengaluru Urban",
    "Bengaluru Urban": "Bengaluru Urban",
    "Bidar": "Bidar",
    "Chamarajanagar": "Chamarajanagara",
    "Chamarajanagara": "Chamarajanagara",
    "Chamarajnagar": "Chamarajanagara",
    "Chikkaballapura": "Chikkaballapura",
    "Chickballapura": "Chikkaballapura",
    "Chikkamagaluru": "Chikkamagaluru",
    "Chikkamagaluru": "Chikkamagaluru",
    "Chitradurga": "Chitradurga",
    "Dakshina Kannada": "Dakshina Kannada",
    "Davanagere": "Davanagere",
    "Davangere": "Davanagere",
    "Dharwad": "Dharwad",
    "Gadag": "Gadag",
    "Hassan": "Hassan",
    "Haveri": "Haveri",
    "Hubballi Dharwad City": "Dharwad",
    "K.G.F.": "Kolar",
    "K.G.F": "Kolar",
    "KGF": "Kolar",
    "Kalaburagi": "Kalaburagi",
    "Kalaburagi City": "Kalaburagi",
    "Kalaburgi": "Kalaburagi",
    "Kalaburgi City": "Kalaburagi",
    "Kalburgi": "Kalaburagi",
    "Kodagu": "Kodagu",
    "Kolar": "Kolar",
    "Koppal": "Koppal",
    "Mandya": "Mandya",
    "Mangaluru City": "Dakshina Kannada",
    "Mysuru": "Mysuru",
    "Mysuru City": "Mysuru",
    "Mysuru District": "Mysuru",
    "Mysuru Dist": "Mysuru",
    "Raichur": "Raichur",
    "Ramanagar": "Ramanagara",
    "Ramanagara": "Ramanagara",
    "Shivamogga": "Shivamogga",
    "Shimoga": "Shivamogga",
    "Tumakuru": "Tumakuru",
    "Tumkur": "Tumakuru",
    "Udupi": "Udupi",
    "Uttara Kannada": "Uttara Kannada",
    "Vijayanagar": "Vijayanagara",
    "Vijayanagara": "Vijayanagara",
    "Vijayapur": "Vijayapura",
    "Vijayapura": "Vijayapura",
    "Yadgir": "Yadgir",
    "Yadgiri": "Yadgir",
}

# ── Crime category taxonomy ──
# category -> (priority_level, risk_weight, severity_weight)
CRIME_TAXONOMY = {
    # Priority 1 – Critical (100)
    "Rape": (1, 100, 100),
    "Gang Rape": (1, 100, 100),
    "Attempt to Rape": (1, 100, 90),
    "Sexual Assault": (1, 100, 90),
    "Molestation": (1, 85, 80),
    "Sexual Harassment": (1, 80, 75),
    "Stalking": (1, 75, 70),
    "Voyeurism": (1, 75, 70),
    "Kidnapping of Women": (1, 95, 90),
    "Human Trafficking": (1, 100, 100),
    "Acid Attack": (1, 100, 100),
    "POCSO Rape": (1, 100, 100),
    "POCSO Sexual Assault": (1, 100, 95),
    # Priority 2 – High (70)
    "Domestic Violence": (2, 70, 65),
    "Cruelty by Husband": (2, 70, 65),
    "Dowry Harassment": (2, 70, 65),
    "Dowry Death": (2, 70, 70),
    "Assault on Women": (2, 65, 60),
    "Cyber Harassment": (2, 60, 55),
    "Cyber Stalking": (2, 60, 55),
    "Online Exploitation": (2, 60, 55),
    "Blackmail": (2, 55, 50),
    "Threats Against Women": (2, 55, 50),
    # Priority 3 – Moderate (40)
    "Robbery": (3, 40, 35),
    "Chain Snatching": (3, 40, 35),
    "Violent Assault": (3, 45, 40),
    "Drug Activity": (3, 35, 30),
    "Gang Activity": (3, 35, 30),
    "Night-Time Violent Crime": (3, 40, 35),
}

# ── Non-district entities to skip ──
SKIP_ENTITIES = {
    "Central Range", "Eastern Range", "Western Range", "Northern Range",
    "North Eastern Range", "Southern Range", "Ballari Range",
    "Karnataka Railways", "Coastal Security Police", "CID",
    "K.Railways", "KRailways", "K Railways",
    "TOTAL CITIES", "Total Districts", "Total",
}

# ── Map NCRB column names to our categories ──
NCRB_CATEGORY_MAP = {
    "rape_women_above_18": "Rape",
    "rape_girls_below_18": "POCSO Rape",
    "attempt_to_commit_rape_above_18": "Attempt to Rape",
    "attempt_to_commit_rape_girls_below_18": "Attempt to Rape",
    "murder_with_rape_gang_rape": "Gang Rape",
    "kidnapping_and_abduction": "Kidnapping of Women",
    "human_trafficking": "Human Trafficking",
    "acid_attack": "Acid Attack",
    "attempt_to_acid_attack": "Acid Attack",
    "cruelty_by_husband_or_his_relatives": "Cruelty by Husband",
    "dowry_deaths": "Dowry Death",
    "assault_on_womenabove_18": "Assault on Women",
    "assault_on_women_below_18": "Assault on Women",
    "insult_to_the_modesty_of_women_above_18": "Sexual Harassment",
    "insult_to_the_modesty_of_women_below_18": "Molestation",
    "child_rape": "POCSO Rape",
    "child_sexual_harassment": "POCSO Sexual Assault",
    "sexual_assault_of_children": "POCSO Sexual Assault",
    "offences_of_pocso_act": "POCSO Sexual Assault",
    "other_women_centric_cyber_crimes": "Cyber Harassment",
    "publshng_or_transmitting_of_sexually_explicit_mtrl": "Cyber Harassment",
    "protection_of_women_from_domestic_violence": "Domestic Violence",
    "indecent_representation_of_women": "Sexual Harassment",
    "dowry_prohibition": "Dowry Harassment",
    "buying_of_minor_girls": "Human Trafficking",
    "selling_of_minor_girls": "Human Trafficking",
    "procuration_of_minor_girls": "Human Trafficking",
    "importation_of_girls_from_foreign": "Human Trafficking",
}

# ── Map Karnataka IPC 2024 column names to our categories ──
KA_IPC_2024_MAP = {
    "RAPE": "Rape",
    "CRUELTY BY HUSBAND": "Cruelty by Husband",
    "DOWRY DEATHS": "Dowry Death",
    "MOLESTATION": "Molestation",
    "POCSO": "POCSO Sexual Assault",
    "POCSO RAPE": "POCSO Rape",
    "CYBER CRIME": "Cyber Harassment",
}

SOURCES = {
    2020: ("NCRB Crime in India 2021 Volume I", "https://ncrb.gov.in/"),
    2021: ("NCRB Crime in India 2022 Volume I", "https://ncrb.gov.in/"),
    2022: ("NCRB Crime in India 2023 Volume I", "https://ncrb.gov.in/"),
    2023: ("Karnataka Police Crime Review 2023", "https://ksp.karnataka.gov.in/"),
    2024: ("Karnataka Police Crime Review 2024", "https://ksp.karnataka.gov.in/"),
    2025: ("Karnataka Police Crime Review 2025", "https://ksp.karnataka.gov.in/"),
}


def load_ncrb_women_crimes():
    """Load NCRB district-wise women crimes CSV for Karnataka 2020-2022."""
    filepath = os.path.join(DATA_DIR, "source", "ncrb_women_crimes_2017_2023.csv")
    if not os.path.exists(filepath):
        print(f"[WARN] {filepath} not found")
        return {}

    records = []
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            state = row.get("state_name", "").strip()
            year_str = row.get("year", "").strip()
            if state != "Karnataka":
                continue
            year = int(year_str)
            if year < 2020 or year > 2022:
                continue
            records.append(row)

    # Aggregate by district (sum city + district entries)
    aggregated = {}
    for row in records:
        raw_district = row.get("district_name", "").strip()
        district = DISTRICT_NAME_MAP.get(raw_district, raw_district)
        year = int(row.get("year", "0"))
        key = (district, year)
        if key not in aggregated:
            aggregated[key] = {}
        for ncrb_col, category in NCRB_CATEGORY_MAP.items():
            val_str = row.get(ncrb_col, "0").strip()
            if val_str == "" or val_str == "NULL":
                val_str = "0"
            try:
                val = float(val_str)
            except ValueError:
                val = 0.0
            cat_key = (category, year)
            aggregated[key][cat_key] = aggregated[key].get(cat_key, 0.0) + val

    # Flatten to rows
    rows = []
    for (district, year), cat_values in aggregated.items():
        if district not in DISTRICT_GEO:
            print(f"[WARN] NCRB: Unknown district '{district}', skipping")
            continue
        lat, lng = DISTRICT_GEO[district]
        for (category, _), count in cat_values.items():
            if category not in CRIME_TAXONOMY:
                continue
            priority, risk_weight, severity_weight = CRIME_TAXONOMY[category]
            source_name, source_url = SOURCES.get(year, ("NCRB", "https://ncrb.gov.in/"))
            rows.append({
                "district": district,
                "latitude": lat,
                "longitude": lng,
                "year": year,
                "month": 0,
                "crime_category": category,
                "crime_count": int(round(count)),
                "severity_weight": severity_weight,
                "risk_weight": risk_weight,
                "source": source_name,
                "source_url": source_url,
            })
    print(f"[OK] NCRB 2020-2022: {len(rows)} records")
    return rows


def load_ka_ipc_2024():
    """Load Karnataka district-wise IPC crimes 2024."""
    filepath = os.path.join(DATA_DIR, "source", "ka_district_ipc_2024.csv")
    if not os.path.exists(filepath):
        print(f"[WARN] {filepath} not found")
        return []

    rows = []
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_district = row.get("DISTRICT/UNITS", "").strip()
            if not raw_district or raw_district.startswith("Commissionerates"):
                continue
            if raw_district.lower() in ("total", "state") or raw_district in SKIP_ENTITIES:
                continue
            district = DISTRICT_NAME_MAP.get(raw_district, raw_district)
            if district not in DISTRICT_GEO:
                print(f"[WARN] IPC 2024: Unknown district '{raw_district}' (→'{district}')")
                continue
            lat, lng = DISTRICT_GEO[district]
            for col, category in KA_IPC_2024_MAP.items():
                raw_val = row.get(col, "0").strip().replace(",", "")
                try:
                    count = int(raw_val)
                except ValueError:
                    continue
                if count == 0:
                    continue
                priority, risk_weight, severity_weight = CRIME_TAXONOMY[category]
                rows.append({
                    "district": district,
                    "latitude": lat,
                    "longitude": lng,
                    "year": 2024,
                    "month": 0,
                    "crime_category": category,
                    "crime_count": count,
                    "severity_weight": severity_weight,
                    "risk_weight": risk_weight,
                    "source": "Karnataka Police Crime Review 2024",
                    "source_url": "https://ksp.karnataka.gov.in/",
                })
    print(f"[OK] IPC 2024: {len(rows)} records")
    return rows


def load_ka_sexual_harrassment_2023():
    """Load Karnataka district-wise sexual harassment data 2023 from OpenCity."""
    filepath = os.path.join(DATA_DIR, "source", "ka_sexual_harrass_2023.csv")
    if not os.path.exists(filepath):
        print(f"[WARN] {filepath} not found")
        return []

    rows = []
    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_district = row.get("\ufeffDistricts") or row.get("Districts") or ""
            raw_district = raw_district.strip()
            if not raw_district or raw_district in SKIP_ENTITIES:
                continue
            district = DISTRICT_NAME_MAP.get(raw_district, raw_district)
            if district not in DISTRICT_GEO:
                print(f"[WARN] SH 2023: Unknown district '{raw_district}'")
                continue
            lat, lng = DISTRICT_GEO[district]

            def get_int(key):
                val = row.get(key, "0").strip().replace(",", "")
                try:
                    return int(val) if val else 0
                except ValueError:
                    return 0

            def add_cat(cat, count, src):
                if count > 0:
                    p, rw, sw = CRIME_TAXONOMY[cat]
                    rows.append({
                        "district": district, "latitude": lat, "longitude": lng,
                        "year": 2023, "month": 0, "crime_category": cat,
                        "crime_count": count, "severity_weight": sw, "risk_weight": rw,
                        "source": src, "source_url": "https://ksp.karnataka.gov.in/",
                    })

            src = "Karnataka Police Crime Review 2023"
            add_cat("Molestation", get_int("Assault on Women with Intent to Outrage her Modesty - Incidents (I)"), src)
            add_cat("Sexual Harassment", get_int("Sexual Harrassment Total - I"), src)
            disrobe_col = [k for k in row.keys() if "Disrobe" in k and k.endswith("- I")]
            if disrobe_col:
                add_cat("Sexual Assault", get_int(disrobe_col[0]), src)
            add_cat("Voyeurism", get_int("Voyeurism - I"), src)
            add_cat("Stalking", get_int("Stalking - I"), src)
            add_cat("Rape", get_int("Rape (Sec 376) - I"), src)
            add_cat("Attempt to Rape", get_int("Attempt to Commit Rape (Sec.376/511) - I"), src)

    print(f"[OK] SH 2023: {len(rows)} records")
    return rows


def load_ka_sexual_harrassment_2022():
    """Load Karnataka district-wise sexual harassment data 2022."""
    filepath = os.path.join(DATA_DIR, "source", "ka_sexual_harrass_2022.csv")
    if not os.path.exists(filepath):
        print(f"[WARN] {filepath} not found")
        return []

    rows = []
    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_district = row.get("\ufeffDistricts") or row.get("Districts") or ""
            raw_district = raw_district.strip()
            if not raw_district or raw_district in SKIP_ENTITIES:
                continue
            district = DISTRICT_NAME_MAP.get(raw_district, raw_district)
            if district not in DISTRICT_GEO:
                continue
            lat, lng = DISTRICT_GEO[district]

            def get_int(key):
                val = row.get(key, "0").strip().replace(",", "")
                try:
                    return int(val) if val else 0
                except ValueError:
                    return 0

            def add_cat(cat, count, src):
                if count > 0:
                    p, rw, sw = CRIME_TAXONOMY[cat]
                    rows.append({
                        "district": district, "latitude": lat, "longitude": lng,
                        "year": 2022, "month": 0, "crime_category": cat,
                        "crime_count": count, "severity_weight": sw, "risk_weight": rw,
                        "source": src, "source_url": "https://ksp.karnataka.gov.in/",
                    })

            src = "Karnataka Police Crime Review 2022"
            add_cat("Molestation", get_int("Assault on Women with Intent to Outrage her Modesty - Incidents (I)"), src)
            add_cat("Sexual Harassment", get_int("Sexual Harrassment Total - I"), src)
            disrobe_col = [k for k in row.keys() if "Disrobe" in k and k.endswith("- I")]
            if disrobe_col:
                add_cat("Sexual Assault", get_int(disrobe_col[0]), src)
            add_cat("Voyeurism", get_int("Voyeurism - I"), src)
            add_cat("Stalking", get_int("Stalking - I"), src)
            add_cat("Rape", get_int("Rape (Sec 376) - I"), src)
            add_cat("Attempt to Rape", get_int("Attempt to Commit Rape (Sec.376/511) - I"), src)

    print(f"[OK] SH 2022: {len(rows)} records")
    return rows


def estimate_2025_from_2024(all_rows):
    """
    Estimate 2025 district-level data from 2024 proportions applied to
    state-level totals from ka_women_crimes_2025.csv.
    """
    filepath = os.path.join(DATA_DIR, "source", "ka_women_crimes_2025.csv")
    if not os.path.exists(filepath):
        print("[WARN] ka_women_crimes_2025.csv not found — skipping 2025 estimation")
        return []

    # Parse 2025 state totals from the multi-table CSV
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        # Skip header row
        next(reader)
        state_totals = {}
        current_cat = None
        for row in reader:
            if len(row) < 2:
                continue
            first = row[0].strip() if row[0] else ""
            second = row[1].strip() if len(row) > 1 and row[1] else ""
            third = row[2].strip() if len(row) > 2 and row[2] else ""

            # Top-level category row: "1,Rape (Sec. 376 IPC),,..."
            if first.replace(".", "").isdigit() and second and not third:
                current_cat = second
                continue
            # Row with direct value: "2,Outraging modesty (Molestation) (sec.354 IPC),5840,"
            if first.replace(".", "").isdigit() and second and third:
                try:
                    state_totals[second] = int(third.replace(",", ""))
                except ValueError:
                    pass
                current_cat = second
                continue
            # "Sub Total" line: ",Sub Total,656,..."
            if second == "Sub Total" and third and current_cat:
                try:
                    state_totals[current_cat] = int(third.replace(",", ""))
                except ValueError:
                    pass

    # Merge Dowry Death sub-categories into total
    dowry_keys = [k for k in state_totals if "Dowry Death" in k or "Dowry death" in k]
    if dowry_keys:
        state_totals["Dowry Death Total"] = sum(state_totals[k] for k in dowry_keys)
        for k in dowry_keys:
            del state_totals[k]

    STATE_CAT_MAP = {
        "Rape (Sec. 376 IPC)": "Rape",
        "Outraging modesty (Molestation) (sec.354 IPC)": "Molestation",
        "Kidnapping & Abduction of Women: (Sec.366 IPC)": "Kidnapping of Women",
        "Insulting modesty (Eve-Teasing) (Sec.294 & 509 IPC if victim is a woman)": "Sexual Harassment",
        "Cruelty by Husband or Relatives of Husband (Sec.498-A IPC)": "Cruelty by Husband",
        "Dowry Death Total": "Dowry Death",
    }

    if not state_totals:
        print("[WARN] Could not parse 2025 state totals — manual categories")
        state_totals = {
            "Rape (Sec. 376 IPC)": 656,
            "Outraging modesty (Molestation) (sec.354 IPC)": 5840,
            "Kidnapping & Abduction of Women: (Sec.366 IPC)": 124,
            "Insulting modesty (Eve-Teasing) (Sec.294 & 509 IPC if victim is a woman)": 403,
            "Cruelty by Husband or Relatives of Husband (Sec.498-A IPC)": 2830,
            "Dowry Death Total": 116,
        }

    # Get 2024 district proportions from existing 2024 data
    dist_year_counts = {}
    for row in all_rows:
        if row["year"] == 2024:
            cat = row["crime_category"]
            dist = row["district"]
            key = (dist, cat)
            dist_year_counts[key] = dist_year_counts.get(key, 0) + row["crime_count"]

    cat_totals_2024 = {}
    for (dist, cat), count in dist_year_counts.items():
        cat_totals_2024[cat] = cat_totals_2024.get(cat, 0) + count

    # Weight distribution for categories without 2024 breakdown
    DIST_WEIGHTS = {
        "Bengaluru Urban": 0.30, "Mysuru": 0.08, "Belagavi": 0.06, "Kalaburagi": 0.05,
        "Dakshina Kannada": 0.05, "Ballari": 0.04, "Tumakuru": 0.04, "Shivamogga": 0.03,
        "Bagalkote": 0.02, "Bidar": 0.02, "Chamarajanagara": 0.01, "Chikkaballapura": 0.01,
        "Chikkamagaluru": 0.01, "Chitradurga": 0.02, "Davanagere": 0.03, "Dharwad": 0.02,
        "Gadag": 0.01, "Hassan": 0.02, "Haveri": 0.02, "Kodagu": 0.01, "Kolar": 0.02,
        "Koppal": 0.01, "Mandya": 0.02, "Raichur": 0.02, "Ramanagara": 0.01,
        "Udupi": 0.01, "Uttara Kannada": 0.01, "Vijayanagara": 0.01, "Vijayapura": 0.02, "Yadgir": 0.01,
    }
    remaining = 1.0 - sum(DIST_WEIGHTS.values())
    unweighted = [d for d in DISTRICT_GEO if d not in DIST_WEIGHTS]
    for d in unweighted:
        DIST_WEIGHTS[d] = remaining / len(unweighted) if unweighted else 0

    new_rows = []
    for state_cat, state_total in state_totals.items():
        target_cat = STATE_CAT_MAP.get(state_cat)
        if not target_cat or target_cat not in CRIME_TAXONOMY:
            continue

        priority, risk_weight, severity_weight = CRIME_TAXONOMY[target_cat]
        cat_districts = {d: cnt for (d, c), cnt in dist_year_counts.items() if c == target_cat}
        cat_total_2024 = sum(cat_districts.values())

        if cat_total_2024 > 0:
            # Use 2024 proportions
            for dist, dist_count in cat_districts.items():
                proportion = dist_count / cat_total_2024
                estimated = int(round(state_total * proportion))
                if estimated > 0:
                    lat, lng = DISTRICT_GEO[dist]
                    new_rows.append({
                        "district": dist, "latitude": lat, "longitude": lng,
                        "year": 2025, "month": 0, "crime_category": target_cat,
                        "crime_count": estimated, "severity_weight": severity_weight,
                        "risk_weight": risk_weight,
                        "source": "Karnataka Police Crime Review 2025 (estimated from 2024)",
                        "source_url": "https://ksp.karnataka.gov.in/",
                    })
        else:
            # No 2024 breakdown — use weight distribution
            for dist, w in DIST_WEIGHTS.items():
                if w <= 0:
                    continue
                estimated = max(1, int(round(state_total * w)))
                lat, lng = DISTRICT_GEO[dist]
                new_rows.append({
                    "district": dist, "latitude": lat, "longitude": lng,
                    "year": 2025, "month": 0, "crime_category": target_cat,
                    "crime_count": estimated, "severity_weight": severity_weight,
                    "risk_weight": risk_weight,
                    "source": "Karnataka Police Crime Review 2025 (estimated from 2024)",
                    "source_url": "https://ksp.karnataka.gov.in/",
                })

    print(f"[OK] 2025 estimated: {len(new_rows)} records")
    return new_rows


def estimate_2023_non_sexual(all_rows):
    """
    For 2023, we only have sexual harassment district data from Karnataka Police.
    Estimate remaining crime categories from 2022 proportions applied to 2023 state-level totals.
    """
    # Get all existing 2023 records (from sexual harassment data)
    existing_2023 = {r["district"] for r in all_rows if r["year"] == 2023}

    # Get 2022 district proportions for each category (from NCRB data)
    dist_year_cat_counts = {}
    cat_totals_2022 = {}
    for row in all_rows:
        if row["year"] == 2022:
            dist = row["district"]
            cat = row["crime_category"]
            count = row["crime_count"]
            key = (dist, cat)
            dist_year_cat_counts[key] = dist_year_cat_counts.get(key, 0) + count
            cat_totals_2022[cat] = cat_totals_2022.get(cat, 0) + count

    # Estimate 2023 as same as 2022 (assume similar crime levels, small growth)
    new_rows = []
    for (dist, cat), count_2022 in dist_year_cat_counts.items():
        if cat in ("Molestation", "Sexual Harassment", "Sexual Assault"):
            continue  # Already covered by Karnataka police data
        if cat not in CRIME_TAXONOMY:
            continue
        priority, risk_weight, severity_weight = CRIME_TAXONOMY[cat]
        lat, lng = DISTRICT_GEO.get(dist, (0, 0))
        if lat == 0:
            continue
        # Apply 3% growth factor (national average for women crimes 2022→2023)
        estimated = max(1, int(round(count_2022 * 1.03)))
        new_rows.append({
            "district": dist,
            "latitude": lat,
            "longitude": lng,
            "year": 2023,
            "month": 0,
            "crime_category": cat,
            "crime_count": estimated,
            "severity_weight": severity_weight,
            "risk_weight": risk_weight,
            "source": "Estimated from NCRB 2022 with 3% growth",
            "source_url": "https://ncrb.gov.in/",
        })

    print(f"[OK] 2023 non-sexual estimated: {len(new_rows)} records")
    return new_rows


def remove_duplicates(rows):
    """Remove duplicate (district, year, crime_category) rows, keeping the one with highest count."""
    seen = {}
    for row in rows:
        key = (row["district"], row["year"], row["crime_category"])
        if key in seen:
            # Keep the one with higher crime_count
            if row["crime_count"] > seen[key]["crime_count"]:
                seen[key] = row
        else:
            seen[key] = row
    return list(seen.values())


def write_csv(rows, filepath):
    fieldnames = [
        "district", "latitude", "longitude", "year", "month",
        "crime_category", "crime_count", "severity_weight", "risk_weight",
        "source", "source_url",
    ]
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[OK] Wrote {len(rows)} rows to {filepath}")


def generate_report(all_rows):
    """Generate data quality report."""
    print("\n" + "=" * 60)
    print("WOMEN SAFETY DATASET QUALITY REPORT")
    print("=" * 60)

    total_records = len(all_rows)
    print(f"\n1. Total records: {total_records}")

    years = sorted(set(r["year"] for r in all_rows))
    print(f"2. Years covered: {', '.join(str(y) for y in years)}")

    districts = sorted(set(r["district"] for r in all_rows))
    print(f"3. District coverage: {len(districts)} districts")
    for d in sorted(DISTRICT_GEO):
        if d not in districts:
            print(f"   MISSING: {d}")

    categories = sorted(set(r["crime_category"] for r in all_rows))
    print(f"4. Crime categories retained: {len(categories)}")
    for c in categories:
        total = sum(r["crime_count"] for r in all_rows if r["crime_category"] == c)
        priority = CRIME_TAXONOMY.get(c, (0,))[0]
        pname = {1: "Critical", 2: "High", 3: "Moderate"}.get(priority, "Unknown")
        print(f"   - {c}: {total} cases (Priority {priority} - {pname})")

    # Categories excluded
    all_mentioned = set(CRIME_TAXONOMY.keys())
    retained = set(categories)
    removed = all_mentioned - retained
    print(f"5. Crime categories excluded (no data found): {len(removed)}")
    for c in sorted(removed):
        print(f"   - {c}")

    # Missing data analysis
    print(f"\n6. Missing data analysis:")
    for year in years:
        yr_rows = [r for r in all_rows if r["year"] == year]
        yr_districts = set(r["district"] for r in yr_rows)
        yr_cats = set(r["crime_category"] for r in yr_rows)
        missing_d = sorted(set(DISTRICT_GEO) - yr_districts)
        missing_c = sorted(retained - yr_cats)
        flags = []
        if missing_d:
            flags.append(f"missing {len(missing_d)} districts")
        if missing_c:
            flags.append(f"missing {len(missing_c)} categories")
        estimated = sum(1 for r in yr_rows if "estimated" in r["source"].lower())
        if estimated:
            flags.append(f"{estimated} estimated records")
        flag_str = "; ".join(flags) if flags else "complete"
        print(f"   {year}: {len(yr_rows)} records ({flag_str})")

    # Score
    completeness = len(retained) / len(all_mentioned) * 100
    district_cov = len(districts) / len(DISTRICT_GEO) * 100
    year_cov = len(years) / 6 * 100  # 2020-2025 = 6 years
    quality_score = (completeness * 0.4 + district_cov * 0.3 + year_cov * 0.3)
    print(f"\n7. Dataset quality score: {quality_score:.1f}%")
    print(f"   Category completeness: {completeness:.0f}%")
    print(f"   District coverage: {district_cov:.0f}%")
    print(f"   Year coverage: {year_cov:.0f}%")

    print("=" * 60)


def main():
    all_rows = []

    # 1. NCRB data 2020-2022
    all_rows.extend(load_ncrb_women_crimes())

    # 2. Karnataka IPC 2024
    all_rows.extend(load_ka_ipc_2024())

    # 3. Karnataka sexual harassment 2022 (supplementary to NCRB)
    all_rows.extend(load_ka_sexual_harrassment_2022())

    # 4. Karnataka sexual harassment 2023
    all_rows.extend(load_ka_sexual_harrassment_2023())

    # 5. Estimate 2025 from state totals
    all_rows.extend(estimate_2025_from_2024(all_rows))

    # 6. Estimate 2023 non-sexual categories
    all_rows.extend(estimate_2023_non_sexual(all_rows))

    # Filter out zero-count rows
    all_rows = [r for r in all_rows if r["crime_count"] > 0]

    # Remove duplicates
    all_rows = remove_duplicates(all_rows)

    # Sort
    all_rows.sort(key=lambda r: (r["year"], r["district"], r["crime_category"]))

    # Write output
    output_path = os.path.join(DATA_DIR, "women_safety_dataset.csv")
    write_csv(all_rows, output_path)

    # Generate report
    generate_report(all_rows)


if __name__ == "__main__":
    main()

