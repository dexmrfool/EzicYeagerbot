import datetime
from typing import List, Optional
from sqlalchemy import select, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models import (
    GroupConfig,
    UserProfile,
    ConversationMemory,
    TranslationGlossary,
    TranslationCache,
    GroupMember
)
from bot.config import settings
from bot.utils.logging import logger


class BotRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_group(self, telegram_group_id: int, title: Optional[str] = None) -> GroupConfig:
        """Retrieves group config or initializes a new group with default settings."""
        stmt = select(GroupConfig).where(GroupConfig.telegram_group_id == telegram_group_id)
        result = await self.session.execute(stmt)
        group = result.scalar_one_or_none()

        if not group:
            # Crucial requirement: New groups ALWAYS start with butler_enabled=False!
            group = GroupConfig(
                telegram_group_id=telegram_group_id,
                title=title,
                target_language=settings.DEFAULT_TARGET_LANGUAGE,
                translation_enabled=True,
                butler_enabled=False,
                translation_model=settings.DEFAULT_TRANSLATION_MODEL,
                profanity_preservation=True,
                slang_preservation=True
            )
            self.session.add(group)
            await self.session.commit()
            await self.session.refresh(group)
            logger.info(f"Initialized new group config in DB: id={telegram_group_id}, title='{title}' (Butler: OFF)")
        elif title and group.title != title:
            group.title = title
            await self.session.commit()

        return group

    async def set_butler_state(self, telegram_group_id: int, enabled: bool) -> bool:
        """Silently enables or disables Butler AI for the group."""
        group = await self.get_or_create_group(telegram_group_id)
        group.butler_enabled = enabled
        await self.session.commit()
        logger.info(f"Updated group {telegram_group_id} Butler AI state: enabled={enabled}")
        return True

    async def set_target_language(self, telegram_group_id: int, target_lang: str) -> bool:
        """Updates the group's target language."""
        group = await self.get_or_create_group(telegram_group_id)
        group.target_language = target_lang.lower().strip()
        await self.session.commit()
        return True

    async def add_memory(self, group_id: int, user_id: int, role: str, content: str) -> None:
        """Saves a conversation turn and prunes expired/excess memory."""
        record = ConversationMemory(
            group_id=group_id,
            user_id=user_id,
            role=role,
            content=content,
            timestamp=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        )
        self.session.add(record)
        await self.session.commit()

        # Prune memory older than TTL
        cutoff = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(
            minutes=settings.MEMORY_TTL_MINUTES
        )
        prune_stmt = delete(ConversationMemory).where(
            ConversationMemory.group_id == group_id,
            ConversationMemory.timestamp < cutoff
        )
        await self.session.execute(prune_stmt)
        await self.session.commit()

    async def get_recent_memory(self, group_id: int, limit: Optional[int] = None) -> List[ConversationMemory]:
        """Fetches chronologically sorted recent dialogue history for the Butler."""
        max_msgs = limit or settings.MEMORY_MAX_MESSAGES
        stmt = (
            select(ConversationMemory)
            .where(ConversationMemory.group_id == group_id)
            .order_by(desc(ConversationMemory.timestamp))
            .limit(max_msgs)
        )
        result = await self.session.execute(stmt)
        records = list(result.scalars().all())
        # Return in chronological order (oldest first)
        records.reverse()
        return records

    async def get_cached_translation(self, hash_key: str) -> Optional[str]:
        """Retrieves cached translation if not expired."""
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        stmt = select(TranslationCache).where(
            TranslationCache.hash_key == hash_key,
            TranslationCache.expires_at > now
        )
        result = await self.session.execute(stmt)
        cache_item = result.scalar_one_or_none()
        return cache_item.translated_text if cache_item else None

    async def set_cached_translation(
        self,
        hash_key: str,
        source_text: str,
        target_language: str,
        translated_text: str,
        ttl_seconds: Optional[int] = None
    ) -> None:
        """Saves or updates cached translation."""
        ttl = ttl_seconds or settings.TRANSLATION_CACHE_TTL_SECONDS
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        expires_at = now + datetime.timedelta(seconds=ttl)

        stmt = select(TranslationCache).where(TranslationCache.hash_key == hash_key)
        res = await self.session.execute(stmt)
        existing = res.scalar_one_or_none()

        if existing:
            existing.translated_text = translated_text
            existing.expires_at = expires_at
        else:
            cache_entry = TranslationCache(
                hash_key=hash_key,
                source_text=source_text,
                target_language=target_language,
                translated_text=translated_text,
                expires_at=expires_at
            )
            self.session.add(cache_entry)

        await self.session.commit()

    async def get_glossary_by_language(self, language: str) -> List[TranslationGlossary]:
        """Returns registered glossary entries for a specific language."""
        stmt = (
            select(TranslationGlossary)
            .where(TranslationGlossary.language == language)
            .order_by(desc(TranslationGlossary.priority))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def upsert_group_member(
        self,
        telegram_group_id: int,
        telegram_user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None
    ) -> None:
        """Records or updates a user's active presence in a group for @all mentions."""
        clean_first_name = first_name or "Member"
        clean_username = username.lstrip("@") if username else None

        stmt = select(GroupMember).where(
            GroupMember.telegram_group_id == telegram_group_id,
            GroupMember.telegram_user_id == telegram_user_id
        )
        result = await self.session.execute(stmt)
        member = result.scalar_one_or_none()

        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        if member:
            member.username = clean_username
            member.first_name = clean_first_name
            member.last_seen = now
        else:
            member = GroupMember(
                telegram_group_id=telegram_group_id,
                telegram_user_id=telegram_user_id,
                username=clean_username,
                first_name=clean_first_name,
                last_seen=now
            )
            self.session.add(member)

        await self.session.commit()

    async def get_group_members(self, telegram_group_id: int) -> List[GroupMember]:
        """Fetches all known active members of a specific group."""
        stmt = (
            select(GroupMember)
            .where(GroupMember.telegram_group_id == telegram_group_id)
            .order_by(desc(GroupMember.last_seen))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

