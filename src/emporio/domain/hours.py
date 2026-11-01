from datetime import date, datetime, time, timedelta

OPENING = {
    0: (time(9), time(18)),
    1: (time(9), time(18)),
    2: (time(9), time(18)),
    3: (time(9), time(18)),
    4: (time(9), time(18)),
    5: (time(9), time(13)),
}
FIXED_HOLIDAYS = {(1, 1), (4, 21), (5, 1), (9, 7), (10, 12), (11, 2), (11, 15), (11, 20), (12, 25)}
WEEKDAYS = {
    "pt": ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"),
    "en": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
}
OPENING_TEXT = {
    "pt": {"today": "hoje", "tomorrow": "amanhã", "format": "{when}, {date}, às {time}"},
    "en": {"today": "today", "tomorrow": "tomorrow", "format": "{when}, {date}, at {time}"},
}


def _easter(year: int) -> date:
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (a + 11 * h + 22 * m) // 451
    month, day = divmod(h + m - 7 * n + 114, 31)
    return date(year, month, day + 1)


def is_holiday(day: date) -> bool:
    return (day.month, day.day) in FIXED_HOLIDAYS or day == _easter(day.year) - timedelta(days=2)


def _window(day: date) -> tuple[time, time] | None:
    if is_holiday(day):
        return None
    return OPENING.get(day.weekday())


def is_open(now: datetime) -> bool:
    window = _window(now.date())
    return window is not None and window[0] <= now.time() < window[1]


def next_opening(now: datetime) -> datetime:
    window = _window(now.date())
    if window is not None and now.time() < window[0]:
        return datetime.combine(now.date(), window[0], now.tzinfo)

    day = now.date() + timedelta(days=1)
    while (window := _window(day)) is None:
        day += timedelta(days=1)
    return datetime.combine(day, window[0], now.tzinfo)


def weekday_name(moment: datetime, lang: str = "pt") -> str:
    return WEEKDAYS[lang][moment.weekday()]


def describe_opening(moment: datetime, now: datetime, lang: str = "pt") -> str:
    words = OPENING_TEXT[lang]
    if moment.date() == now.date():
        when = words["today"]
    elif moment.date() == now.date() + timedelta(days=1):
        when = words["tomorrow"]
    else:
        when = weekday_name(moment, lang)
    day = moment.strftime("%d/%m" if lang == "pt" else "%b %d")
    return words["format"].format(when=when, date=day, time=moment.strftime("%H:%M"))
