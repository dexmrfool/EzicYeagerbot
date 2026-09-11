import json
import os
from sqlalchemy import select
from bot.database.session import engine, async_session_factory
from bot.database.models import Base, TranslationGlossary
from bot.utils.logging import logger


async def init_db() -> None:
    """Creates all database tables if they do not exist and seeds default glossaries."""
    logger.info("Initializing database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized successfully.")

    await seed_glossaries()


async def seed_glossaries() -> None:
    """Reads JSON glossary files from data/ directory and loads them into database."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_dir = os.path.join(base_dir, "data")

    if not os.path.exists(data_dir):
        return

    json_files = [f for f in os.listdir(data_dir) if f.startswith("glossary_") and f.endswith(".json")]

    async with async_session_factory() as session:
        for fname in json_files:
            fpath = os.path.join(data_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = json.load(f)

                lang = content.get("language", "general")
                entries = content.get("entries", [])

                for item in entries:
                    src = item.get("source", "").strip()
                    tgt = item.get("target", "").strip()
                    cat = item.get("category", "slang")
                    if not src or not tgt:
                        continue

                    # Check if already seeded
                    stmt = select(TranslationGlossary).where(
                        TranslationGlossary.language == lang,
                        TranslationGlossary.source_text == src
                    )
                    res = await session.execute(stmt)
                    if not res.scalar_one_or_none():
                        glossary_entry = TranslationGlossary(
                            language=lang,
                            source_text=src,
                            target_text=tgt,
                            category=cat,
                            priority=item.get("priority", 1)
                        )
                        session.add(glossary_entry)

                await session.commit()
            except Exception as e:
                logger.error(f"Failed to seed glossary file {fname}: {e}")
