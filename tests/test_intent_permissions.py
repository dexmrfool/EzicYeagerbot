import unittest
from unittest.mock import MagicMock
from bot.butler.intent import intent_classifier
from bot.telegram.permissions import IsOwnerFilter
from bot.config import settings


class TestIntentAndPermissions(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        settings.BOT_NAME = "Butler"
        settings.OWNER_IDS = {5429173364}

    def test_intent_direct_address(self):
        should_respond, needs_search = intent_classifier.should_butler_respond("hey Butler how are you?")
        self.assertTrue(should_respond)
        self.assertFalse(needs_search)

        # Direct call by 'ezic'
        should_ezic, _ = intent_classifier.should_butler_respond("oi ezic how are you")
        self.assertTrue(should_ezic)

        # Direct call by 'yeager'
        should_yeager, _ = intent_classifier.should_butler_respond("oi yeager what's up")
        self.assertTrue(should_yeager)

    def test_intent_web_search_trigger(self):
        should_respond, needs_search = intent_classifier.should_butler_respond("what is the latest One Piece news?")
        self.assertTrue(should_respond)
        self.assertTrue(needs_search)

        # Release date question
        should_resp_2, needs_search_2 = intent_classifier.should_butler_respond("when will GTA 6 come out?")
        self.assertTrue(should_resp_2)
        self.assertTrue(needs_search_2)

    def test_intent_casual_ignore(self):
        # Conversation between other members should NOT trigger Butler response
        should_respond, _ = intent_classifier.should_butler_respond("I just had lunch guys, it was good")
        self.assertFalse(should_respond)

        should_respond, _ = intent_classifier.should_butler_respond("yeah man that was a great game")
        self.assertFalse(should_respond)

    def test_intent_reply_to_bot(self):
        should_respond, _ = intent_classifier.should_butler_respond(
            "why do you think that?",
            is_reply_to_bot=True
        )
        self.assertTrue(should_respond)

    async def test_owner_permissions_filter(self):
        filt = IsOwnerFilter()

        # Authorized owner
        msg_owner = MagicMock()
        msg_owner.from_user.id = 5429173364
        self.assertTrue(await filt(msg_owner))

        # Unauthorized user
        msg_unauth = MagicMock()
        msg_unauth.from_user.id = 999999999
        msg_unauth.text = "/ezicon"
        msg_unauth.chat.id = -100123456
        self.assertFalse(await filt(msg_unauth))

    async def test_stale_message_filter(self):
        from datetime import datetime, timezone, timedelta
        from bot.telegram.handlers import handle_natural_message, BOT_STARTUP_TIME

        mock_repo = MagicMock()

        # 1. Stale message (>120 seconds old)
        stale_msg = MagicMock()
        stale_msg.from_user.is_bot = False
        stale_msg.text = "Dilwa de"
        stale_msg.date = datetime.now(timezone.utc) - timedelta(seconds=180)
        await handle_natural_message(stale_msg, mock_repo)
        # Should not call repo because it was dropped early
        mock_repo.get_or_create_group.assert_not_called()

        # 2. Historical message from before startup (>120s buffer)
        old_msg = MagicMock()
        old_msg.from_user.is_bot = False
        old_msg.text = "Dilwa de"
        old_msg.date = BOT_STARTUP_TIME - timedelta(seconds=180)
        await handle_natural_message(old_msg, mock_repo)
        mock_repo.get_or_create_group.assert_not_called()


if __name__ == "__main__":
    unittest.main()
