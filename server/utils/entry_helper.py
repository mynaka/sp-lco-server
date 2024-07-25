def determine_database(code: str) -> str:
    """Determine the database based on the code prefix."""
    return code.split(":")[0].lower()