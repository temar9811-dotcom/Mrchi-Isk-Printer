# FILE: check_scopes.py
# VERSION: 1.0.0

from app.esi.scopes import (
    DEFAULT_SCOPES_PATH,
    load_scopes,
    load_scopes_file,
    get_scope_list_string,
    validate_scopes,
)
from app.logging_setup import setup_logging


def main() -> None:
    logger = setup_logging()
    logger.info("Starting ESI scope debug script")

    print(f"ESI scope file: {DEFAULT_SCOPES_PATH}")

    try:
        raw_data = load_scopes_file()
        print(f"JSON version: {raw_data.get('version', 'UNKNOWN')}")

        scopes = load_scopes()
        print(f"Loaded scopes: {len(scopes)}")

        warnings = validate_scopes(scopes)

        if warnings:
            print(f"\nWarnings: {len(warnings)}")

            for warning in warnings:
                print(f"  {warning}")
        else:
            print("\nNo scope validation warnings.")

        scope_string = get_scope_list_string(scopes)

        print("\nSpace-separated scope string:")
        print(scope_string)

        print("\nScope debug script completed successfully.")

    except Exception:
        logger.exception("Scope debug script failed")
        raise


if __name__ == "__main__":
    main()