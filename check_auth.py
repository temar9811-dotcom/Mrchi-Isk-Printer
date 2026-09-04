# FILE: check_auth.py
# VERSION: 1.0.0

from app.logging_setup import setup_logging
from app.esi.auth_flow import perform_login_flow


def main() -> None:
    logger = setup_logging()
    logger.info("Starting auth debug script")

    print("Opening browser for EVE SSO login...")
    print("Please log in and authorize the app.")
    print("Waiting for callback on http://127.0.0.1:8635/callback")

    try:
        result = perform_login_flow()
        
        print("\n=== LOGIN SUCCESSFUL ===")
        print(f"Character Name: {result['character_name']}")
        print(f"Character ID:   {result['character_id']}")
        print(f"Access Token:   {result['access_token'][:20]}...")
        print(f"Refresh Token:  {result['refresh_token'][:20]}...")
        
    except Exception as exc:
        print(f"\n=== LOGIN FAILED ===")
        print(f"Error: {exc}")
        logger.exception("Auth debug script failed")


if __name__ == "__main__":
    main()