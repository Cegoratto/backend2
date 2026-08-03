def get_card_status_for_column(column_title: str) -> str:
    normalized = column_title.lower()

    if "done" in normalized:
        return "done"

    if any(keyword in normalized for keyword in ("progress", "review", "testing")):
        return "in_progress"

    return "todo"
