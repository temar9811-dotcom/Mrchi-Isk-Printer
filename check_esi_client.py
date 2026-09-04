# FILE: check_esi_client.py
# VERSION: 1.0.0

import json
from pathlib import Path

from app.db.database import Database
from app.db.characters_repository import CharactersRepository
from app.logging_setup import setup_logging
from app.esi.esi_client import EsiClient


def main() -> None:
    logger = setup_logging()
    logger.info("Starting ESI client debug script")

    db_path = Path("data/eve_assistant.db")
    db = Database(db_path)

    try:
        db.connect()
        db.init_schema()

        repo = CharactersRepository(db)
        characters = repo.get_all_characters()

        if not characters:
            print("No characters found in database. Please run the app and log in first.")
            return

        print("Available characters:")
        for i, char in enumerate(characters):
            print(f"  {i + 1}. {char.character_name} ({char.character_id})")

        # For automation, just pick the first real character (skip test pilots if possible)
        real_chars = [c for c in characters if "Test Pilot" not in c.character_name]
        char_to_test = real_chars[0] if real_chars else characters[0]

        print(f"\nTesting ESI Client for: {char_to_test.character_name}")

        def save_on_refresh(c):
            print("[Callback] Token was refreshed! Saving to DB.")
            repo.add_character(c)

        client = EsiClient(char_to_test, on_token_refresh=save_on_refresh)

        print("\n1. Fetching Online Status...")
        online = client.get_character_online()
        print(json.dumps(online, indent=2))

        print("\n2. Fetching Location...")
        location = client.get_character_location()
        print(json.dumps(location, indent=2))

        print("\n3. Fetching Ship...")
        ship = client.get_character_ship()
        print(json.dumps(ship, indent=2))
        
        print("\n4. Fetching Skills (summary)...")
        skills = client.get_character_skills()
        print(f"Total Skill Points: {skills.get('total_sp', 0)}")
        print(f"Unallocated SP: {skills.get('unallocated_sp', 0)}")

        print("\nESI Client debug script completed successfully.")

    except Exception:
        logger.exception("ESI Client debug script failed")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()