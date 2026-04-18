"""
Find comparable apartments to the subject property and estimate its market value.
"""
from config import APARTMENT


def _similarity_score(listing: dict, subject: dict) -> float:
    """Higher = more similar. Max ~1.0."""
    score = 0.0

    # Rooms must match exactly for 3-room
    rooms = listing.get("rooms")
    if rooms and abs(float(rooms) - subject["rooms"]) > 0.5:
        return -1.0  # exclude

    # sqm proximity (weight 0.4)
    sqm = listing.get("sqm")
    if sqm and subject.get("sqm"):
        diff = abs(float(sqm) - subject["sqm"])
        score += max(0, 0.4 - (diff / subject["sqm"]) * 0.4)

    # Floor proximity (weight 0.3)
    floor = listing.get("floor")
    if floor is not None and subject.get("floor") is not None:
        diff = abs(int(floor) - subject["floor"])
        score += max(0, 0.3 - diff * 0.1)
    else:
        score += 0.15  # partial credit if unknown

    # Elevator match (weight 0.3)
    elevator = listing.get("elevator")
    if elevator is not None:
        subject_elev = subject.get("has_elevator", False)
        score += 0.3 if bool(elevator) == subject_elev else 0.0
    else:
        score += 0.15

    return round(score, 3)


def find_comparables(listings: list[dict], top_n: int = 10) -> list[dict]:
    """Return top_n most similar listings to the subject apartment."""
    scored = []
    for listing in listings:
        score = _similarity_score(listing, APARTMENT)
        if score >= 0:
            scored.append({**listing, "_similarity": score})
    scored.sort(key=lambda x: x["_similarity"], reverse=True)
    return scored[:top_n]


def estimate_value(comparables: list[dict]) -> dict:
    """Estimate subject apartment value based on comparable price/sqm."""
    ppsqm_list = [
        float(c["price"]) / float(c["sqm"])
        for c in comparables
        if c.get("price") and c.get("sqm") and float(c["sqm"]) > 0
    ]
    if not ppsqm_list:
        return {"estimated_value": None, "note": "אין נתוני שטח מספיקים להערכה"}

    from statistics import mean, median
    avg_ppsqm = mean(ppsqm_list)
    med_ppsqm = median(ppsqm_list)
    subject_sqm = APARTMENT["sqm"]

    return {
        "subject_sqm": subject_sqm,
        "avg_price_per_sqm_comparables": round(avg_ppsqm),
        "median_price_per_sqm_comparables": round(med_ppsqm),
        "estimated_value_avg": round(avg_ppsqm * subject_sqm / 1000) * 1000,
        "estimated_value_median": round(med_ppsqm * subject_sqm / 1000) * 1000,
        "comparables_used": len(ppsqm_list),
    }
