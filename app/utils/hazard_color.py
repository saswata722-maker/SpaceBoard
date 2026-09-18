def hazard_color(is_hazardous):
    """Return Tailwind CSS classes based on hazardous status.

    Args:
        is_hazardous: Boolean indicating if the NEO is potentially hazardous.

    Returns:
        A Tailwind CSS class string for the badge color.
    """
    if is_hazardous:
        return "bg-amber-500 text-white"
    return "bg-green-500 text-white"


def hazard_label(is_hazardous):
    """Return a human-readable label for hazardous status.

    Args:
        is_hazardous: Boolean indicating if the NEO is potentially hazardous.

    Returns:
        A label string for display.
    """
    return "Potentially Hazardous" if is_hazardous else "Safe"
