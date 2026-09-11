import unittest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from bot.database.models import Base
from bot.database.repository import BotRepository
from bot.cache.manager import CacheManager


class TestDbAndCache(unittest.IsolatedAsyncioTestCase):

    def test_cache_deduplication(self):
        cm = CacheManager()
        chat_id = -100123
        msg_id = 456

        # First time seen: not duplicate
        self.assertFalse(cm.is_duplicate_message(chat_id, msg_id))

        # Second time seen: duplicate detected!
        self.assertTrue(cm.is_duplicate_message(chat_id, msg_id))

    def test_cache_translation_hashing(self):
        cm = CacheManager()
        text = "Hello brother"
        target = "fa"

        cm.set_cached_translation(text, target, "سلام برادر")
        self.assertEqual(cm.get_cached_translation(text, target), "سلام برادر")

    async def test_repository_group_default_state(self):
        # Create an in-memory SQLite engine
        test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

        async with session_factory() as session:
            repo = BotRepository(session)

            # Check new group creation: MUST HAVE butler_enabled = False by default!
            group = await repo.get_or_create_group(telegram_group_id=-100999888, title="Anime Chat")
            self.assertFalse(group.butler_enabled)
            self.assertTrue(group.translation_enabled)
            self.assertEqual(group.target_language, "en")

            # Enable Butler
            await repo.set_butler_state(telegram_group_id=-100999888, enabled=True)
            updated = await repo.get_or_create_group(telegram_group_id=-100999888)
            self.assertTrue(updated.butler_enabled)

            # Test Memory addition
            await repo.add_memory(group_id=-100999888, user_id=123, role="user", content="hello butler")
            memory = await repo.get_recent_memory(group_id=-100999888)
            self.assertEqual(len(memory), 1)
            self.assertEqual(memory[0].content, "hello butler")

        await test_engine.dispose()


if __name__ == "__main__":
    unittest.main()
