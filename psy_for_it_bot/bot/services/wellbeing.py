"""WHO-5: sum of five items 0–5 each → raw 0–25, percentage raw×4 (0–100)."""


def who5_raw_and_percent(answers: list[int]) -> tuple[int, int]:
    if len(answers) != 5:
        raise ValueError("WHO-5 requires exactly 5 answers")
    for a in answers:
        if a < 0 or a > 5:
            raise ValueError("each answer must be 0..5")
    raw = sum(answers)
    return raw, raw * 4


def who5_recommendation_key(percent: int) -> str:
    if percent <= 50:
        return "who5_rec_low"
    if percent <= 72:
        return "who5_rec_mid"
    return "who5_rec_high"
