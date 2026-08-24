import re
from datetime import date, datetime, time, timedelta

import dateparser


NUMBER_WORDS: dict[str, int] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "fourteen": 14,
}


MONTH_NAMES = (
    "january|february|march|april|may|june|"
    "july|august|september|october|november|december|"
    "jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec"
)


def clean_date_text(value: str) -> str:
    """
    Remove ordinal suffixes and unnecessary booking words.

    Examples:
        "the 10th of September" -> "10 September"
        "check-in on 12th May"  -> "12 May"
    """
    cleaned = value.strip().lower()

    cleaned = re.sub(
        r"\b(\d{1,2})(st|nd|rd|th)\b",
        r"\1",
        cleaned,
    )

    cleaned = re.sub(
        r"\b(?:check[- ]?in|check[- ]?out|stay|on|the)\b",
        " ",
        cleaned,
    )

    cleaned = re.sub(
        r"\s+",
        " ",
        cleaned,
    )

    return cleaned.strip()


def parse_single_date(
    value: str,
    today: date | None = None,
) -> date | None:
    """
    Convert a date phrase into a Python date.

    The parser prefers future dates and assumes day-month-year
    ordering, which is suitable for Indian date formats.
    """
    today = today or date.today()
    cleaned = clean_date_text(value)

    if not cleaned:
        return None

    parsed = dateparser.parse(
        cleaned,
        settings={
            "RELATIVE_BASE": datetime.combine(
                today,
                time.min,
            ),
            "PREFER_DATES_FROM": "future",
            "DATE_ORDER": "DMY",
            "RETURN_AS_TIMEZONE_AWARE": False,
            "STRICT_PARSING": False,
        },
    )

    if parsed is None:
        return None

    parsed_date = parsed.date()

    # If no year was supplied and the parser still returned a
    # past date, move it to the following year.
    year_was_provided = bool(
        re.search(r"\b\d{4}\b", cleaned)
    )

    if (
        not year_was_provided
        and parsed_date < today
    ):
        try:
            parsed_date = parsed_date.replace(
                year=parsed_date.year + 1
            )
        except ValueError:
            # Handles 29 February when the following year is
            # not a leap year.
            parsed_date = parsed_date.replace(
                year=parsed_date.year + 1,
                day=28,
            )

    return parsed_date


def extract_number_of_nights(
    message: str,
) -> int | None:
    """
    Extract the number of nights from the guest message.

    Supported:
        "for 3 nights"
        "stay 2 nights"
        "for three nights"
    """
    normalized = message.casefold()

    digit_match = re.search(
        r"\b(?:for|stay(?:ing)?(?: for)?)\s+"
        r"(\d{1,2})\s+nights?\b",
        normalized,
    )

    if digit_match:
        nights = int(digit_match.group(1))

        return nights if nights > 0 else None

    word_pattern = "|".join(NUMBER_WORDS.keys())

    word_match = re.search(
        rf"\b(?:for|stay(?:ing)?(?: for)?)\s+"
        rf"({word_pattern})\s+nights?\b",
        normalized,
    )

    if word_match:
        return NUMBER_WORDS[word_match.group(1)]

    return None


def this_weekend(
    today: date,
) -> tuple[date, date]:
    """
    Return Saturday check-in and Monday checkout for the
    nearest upcoming weekend.

    If today is already Saturday or Sunday, the following
    Saturday is used. This avoids silently selecting a weekend
    that has already started.
    """
    days_until_saturday = (
        5 - today.weekday()
    ) % 7

    if days_until_saturday == 0:
        days_until_saturday = 7

    if today.weekday() == 6:
        days_until_saturday = 6

    check_in = today + timedelta(
        days=days_until_saturday
    )
    check_out = check_in + timedelta(days=2)

    return check_in, check_out


def next_weekend(
    today: date,
) -> tuple[date, date]:
    """
    Return Saturday check-in and Monday checkout for the
    weekend after the nearest upcoming weekend.
    """
    upcoming_check_in, _ = this_weekend(today)

    check_in = upcoming_check_in + timedelta(days=7)
    check_out = check_in + timedelta(days=2)

    return check_in, check_out


def parse_named_month_range(
    message: str,
    today: date,
) -> tuple[date | None, date | None]:
    """
    Parse date ranges containing month names.

    Examples:
        "10 September to 13 September"
        "Sep 10 to Sep 13"
        "from 10th Sep to 13th Sep 2026"
        "September 10 - September 13"
    """
    day_first_pattern = re.search(
        rf"(?:from\s+)?"
        rf"(\d{{1,2}}(?:st|nd|rd|th)?\s+"
        rf"(?:{MONTH_NAMES})(?:\s+\d{{4}})?)"
        rf"\s*(?:to|until|till|through|-)\s*"
        rf"(\d{{1,2}}(?:st|nd|rd|th)?"
        rf"(?:\s+(?:{MONTH_NAMES}))?"
        rf"(?:\s+\d{{4}})?)",
        message,
        flags=re.IGNORECASE,
    )

    if day_first_pattern:
        check_in_text = day_first_pattern.group(1)
        check_out_text = day_first_pattern.group(2)

        check_in = parse_single_date(
            check_in_text,
            today,
        )

        # "10 September to 13" means checkout on
        # 13 September.
        if (
            check_in
            and not re.search(
                MONTH_NAMES,
                check_out_text,
                flags=re.IGNORECASE,
            )
        ):
            day_match = re.search(
                r"\d{1,2}",
                check_out_text,
            )

            if day_match:
                checkout_day = int(
                    day_match.group()
                )

                try:
                    check_out = date(
                        check_in.year,
                        check_in.month,
                        checkout_day,
                    )
                except ValueError:
                    return check_in, None

                if check_out <= check_in:
                    if check_in.month == 12:
                        next_month = 1
                        next_year = check_in.year + 1
                    else:
                        next_month = (
                            check_in.month + 1
                        )
                        next_year = check_in.year

                    try:
                        check_out = date(
                            next_year,
                            next_month,
                            checkout_day,
                        )
                    except ValueError:
                        return check_in, None

                return check_in, check_out

        check_out = parse_single_date(
            check_out_text,
            today,
        )

        return check_in, check_out

    month_first_pattern = re.search(
        rf"(?:from\s+)?"
        rf"((?:{MONTH_NAMES})\s+\d{{1,2}}"
        rf"(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?)"
        rf"\s*(?:to|until|till|through|-)\s*"
        rf"((?:(?:{MONTH_NAMES})\s+)?"
        rf"\d{{1,2}}(?:st|nd|rd|th)?"
        rf"(?:,?\s+\d{{4}})?)",
        message,
        flags=re.IGNORECASE,
    )

    if not month_first_pattern:
        return None, None

    check_in_text = month_first_pattern.group(1)
    check_out_text = month_first_pattern.group(2)

    check_in = parse_single_date(
        check_in_text,
        today,
    )

    if (
        check_in
        and not re.search(
            MONTH_NAMES,
            check_out_text,
            flags=re.IGNORECASE,
        )
    ):
        checkout_day_match = re.search(
            r"\d{1,2}",
            check_out_text,
        )

        if not checkout_day_match:
            return check_in, None

        checkout_day = int(
            checkout_day_match.group()
        )

        try:
            check_out = date(
                check_in.year,
                check_in.month,
                checkout_day,
            )
        except ValueError:
            return check_in, None

        if check_out <= check_in:
            if check_in.month == 12:
                next_month = 1
                next_year = check_in.year + 1
            else:
                next_month = check_in.month + 1
                next_year = check_in.year

            try:
                check_out = date(
                    next_year,
                    next_month,
                    checkout_day,
                )
            except ValueError:
                return check_in, None

        return check_in, check_out

    check_out = parse_single_date(
        check_out_text,
        today,
    )

    return check_in, check_out


def parse_numeric_date_range(
    message: str,
    today: date,
) -> tuple[date | None, date | None]:
    """
    Parse common numeric date ranges.

    Examples:
        "10/09/2026 to 13/09/2026"
        "10-09-2026 - 13-09-2026"
    """
    match = re.search(
        r"(?:from\s+)?"
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"
        r"\s*(?:to|until|till|through|-)\s*"
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        message,
        flags=re.IGNORECASE,
    )

    if not match:
        return None, None

    check_in = parse_single_date(
        match.group(1),
        today,
    )
    check_out = parse_single_date(
        match.group(2),
        today,
    )

    return check_in, check_out


def parse_tomorrow(
    message: str,
    today: date,
) -> tuple[date | None, date | None]:
    """
    Parse bookings starting tomorrow.

    Examples:
        "tomorrow"
        "tomorrow for 3 nights"
    """
    if "tomorrow" not in message.casefold():
        return None, None

    check_in = today + timedelta(days=1)
    nights = extract_number_of_nights(message) or 1
    check_out = check_in + timedelta(days=nights)

    return check_in, check_out


def parse_single_check_in_with_nights(
    message: str,
    today: date,
) -> tuple[date | None, date | None]:
    """
    Parse a single check-in date combined with a stay length.

    Examples:
        "Check in on 10 September for 3 nights"
        "Stay from Sep 10 for two nights"
    """
    nights = extract_number_of_nights(message)

    if nights is None:
        return None, None

    date_patterns = [
        rf"(?:check[- ]?in(?:\s+on)?|from)\s+"
        rf"(\d{{1,2}}(?:st|nd|rd|th)?\s+"
        rf"(?:{MONTH_NAMES})(?:\s+\d{{4}})?)",

        rf"(?:check[- ]?in(?:\s+on)?|from)\s+"
        rf"((?:{MONTH_NAMES})\s+\d{{1,2}}"
        rf"(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?)",

        r"(?:check[- ]?in(?:\s+on)?|from)\s+"
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
    ]

    for pattern in date_patterns:
        match = re.search(
            pattern,
            message,
            flags=re.IGNORECASE,
        )

        if match:
            check_in = parse_single_date(
                match.group(1),
                today,
            )

            if check_in:
                return (
                    check_in,
                    check_in + timedelta(days=nights),
                )

    return None, None


def parse_checkout_change(
    message: str,
    current_check_in: date | None,
    current_check_out: date | None,
) -> tuple[date | None, date | None]:
    """
    Parse a date update using the existing conversation dates.

    Examples:
        "Stay one more night"
        "Make it two more nights"
        "Stay till the 13th"

    This function is useful when the guest changes an existing
    booking request.
    """
    normalized = message.casefold()

    more_nights_digit = re.search(
        r"\b(\d{1,2})\s+more\s+nights?\b",
        normalized,
    )

    if more_nights_digit and current_check_out:
        additional_nights = int(
            more_nights_digit.group(1)
        )

        return (
            current_check_in,
            current_check_out
            + timedelta(days=additional_nights),
        )

    more_nights_word = re.search(
        rf"\b({'|'.join(NUMBER_WORDS.keys())})"
        rf"\s+more\s+nights?\b",
        normalized,
    )

    if more_nights_word and current_check_out:
        additional_nights = NUMBER_WORDS[
            more_nights_word.group(1)
        ]

        return (
            current_check_in,
            current_check_out
            + timedelta(days=additional_nights),
        )

    checkout_day_match = re.search(
        r"\b(?:stay\s+)?"
        r"(?:until|till|through)\s+(?:the\s+)?"
        r"(\d{1,2})(?:st|nd|rd|th)?\b",
        normalized,
    )

    if checkout_day_match and current_check_in:
        checkout_day = int(
            checkout_day_match.group(1)
        )

        try:
            new_checkout = date(
                current_check_in.year,
                current_check_in.month,
                checkout_day,
            )
        except ValueError:
            return current_check_in, None

        if new_checkout <= current_check_in:
            if current_check_in.month == 12:
                new_month = 1
                new_year = (
                    current_check_in.year + 1
                )
            else:
                new_month = (
                    current_check_in.month + 1
                )
                new_year = current_check_in.year

            try:
                new_checkout = date(
                    new_year,
                    new_month,
                    checkout_day,
                )
            except ValueError:
                return current_check_in, None

        return current_check_in, new_checkout

    return None, None


def validate_date_range(
    check_in: date | None,
    check_out: date | None,
    today: date,
) -> tuple[date | None, date | None]:
    """
    Validate parsed booking dates.

    Invalid or incomplete ranges return None values so that the
    orchestrator asks the guest for clarification.
    """
    if check_in is None and check_out is None:
        return None, None

    if check_in is None or check_out is None:
        return check_in, check_out

    if check_in < today:
        return None, None

    if check_out <= check_in:
        return check_in, None

    return check_in, check_out


def extract_relative_dates(
    message: str,
    today: date | None = None,
    current_check_in: date | None = None,
    current_check_out: date | None = None,
) -> tuple[date | None, date | None]:
    """
    Main date-parsing function called by extractor.py.

    Parsing order:
        1. Changes to existing dates
        2. Next weekend
        3. This weekend
        4. Tomorrow
        5. Numeric ranges
        6. Month-name ranges
        7. Check-in date with number of nights

    Returns:
        (check_in, check_out)

    When dates cannot be understood safely:
        (None, None)
    """
    today = today or date.today()
    normalized = message.casefold().strip()

    changed_check_in, changed_check_out = (
        parse_checkout_change(
            message=message,
            current_check_in=current_check_in,
            current_check_out=current_check_out,
        )
    )

    if changed_check_in or changed_check_out:
        return validate_date_range(
            changed_check_in,
            changed_check_out,
            today,
        )

    if "next weekend" in normalized:
        check_in, check_out = next_weekend(today)

        return validate_date_range(
            check_in,
            check_out,
            today,
        )

    if "this weekend" in normalized:
        check_in, check_out = this_weekend(today)

        return validate_date_range(
            check_in,
            check_out,
            today,
        )

    check_in, check_out = parse_tomorrow(
        message,
        today,
    )

    if check_in or check_out:
        return validate_date_range(
            check_in,
            check_out,
            today,
        )

    check_in, check_out = parse_numeric_date_range(
        message,
        today,
    )

    if check_in or check_out:
        return validate_date_range(
            check_in,
            check_out,
            today,
        )

    check_in, check_out = parse_named_month_range(
        message,
        today,
    )

    if check_in or check_out:
        return validate_date_range(
            check_in,
            check_out,
            today,
        )

    check_in, check_out = (
        parse_single_check_in_with_nights(
            message,
            today,
        )
    )

    if check_in or check_out:
        return validate_date_range(
            check_in,
            check_out,
            today,
        )

    return None, None