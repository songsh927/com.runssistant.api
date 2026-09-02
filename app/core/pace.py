from datetime import date, timedelta


def format_pace(sec_per_km: int) -> str:
    minutes = sec_per_km // 60
    seconds = sec_per_km % 60
    return f"{minutes}:{seconds:02d}/km"


def get_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())
