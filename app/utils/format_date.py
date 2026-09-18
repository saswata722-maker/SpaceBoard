from datetime import datetime


def format_date(date_str, fmt="%B %d, %Y"):
    """Format an ISO date string into a human-readable form.

    Args:
        date_str: Date string in YYYY-MM-DD format.
        fmt: strftime-compatible format string.

    Returns:
        Formatted date string, or the original string if parsing fails.
    """
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime(fmt)
    except (ValueError, TypeError):
        return date_str
