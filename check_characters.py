# FILE: check_characters.py
# VERSION: 1.0.0

from pathlib import Path

from app.db.database import Database
from app.db.characters_repository import CharactersRepository
from app.logging_setup import setup_logging
from app.models.character import Character


def main() -> None:
    logger = setup_logging()
    logger.info("Starting character debug script")

    db_path = Path("data/eve_assistant.db")
    print(f"Database path: {db_path.resolve()}")

    db = Database(db_path)

    try:
        db.connect()
        db.init_schema()

        repo = CharactersRepository(db)

        characters = repo.get_all_characters()
        print(f"\nCharacters before check: {len(characters)}")

        if not characters:
            print("No characters found. Adding Test Pilot 1.")

            character = Character(
                character_id=1,
                character_name="Test Pilot 1",
                notes="Created by check_characters.py",
            )

            repo.add_character(character)

        characters = repo.get_all_characters()

        print(f"\nCharacters after check: {len(characters)}")

        for character in characters:
            print(
                f"id={character.character_id} "
                f"name={character.character_name} "
                f"added_at={character.added_at or 'UNKNOWN'} "
                f"notes={character.notes or 'NONE'}"
            )

        db.log_debug_event(
            "check_characters",
            "Character debug script ran successfully",
        )

        print("\nCharacter debug script completed successfully.")

    except Exception:
        logger.exception("Character debug script failed")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()