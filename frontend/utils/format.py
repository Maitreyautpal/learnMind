LEVEL_COLORS = {"Weak": "#D64545", "Developing": "#E0A526", "Strong": "#2E9E5B"}
PRIORITY_COLORS = {"Critical": "#B3261E", "High": "#D64545", "Medium": "#E0A526", "Low": "#2E9E5B"}


def mmss(sec) -> str:
    sec = int(sec or 0)
    return f"{sec // 60:02d}:{sec % 60:02d}"


def pct(x) -> str:
    return "n/a" if x is None else f"{x * 100:.0f}%"
