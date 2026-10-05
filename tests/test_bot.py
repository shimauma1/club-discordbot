import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from bot import Config, TournamentBot, VerificationView, is_introduction
from storage import Store


class BotTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = Config('test-secret', 1, 2, 3, 4, Path(self.temp.name) / 'bot.sqlite3')
        self.bot = TournamentBot(self.config)
        await self.bot.store.initialize()
        self.role = MagicMock()
        self.role.is_default.return_value = False
        self.role.managed = False
        self.role.permissions.administrator = False
        self.role.__ge__.return_value = False
        self.member = NS(id=10, roles=[], add_roles=AsyncMock())
        self.guild = MagicMock()
        self.guild.id = 1
        self.guild.fetch_member = AsyncMock(return_value=self.member)
        self.guild.get_role.return_value = self.role
        self.guild.me.guild_permissions.manage_roles = True
        self.interaction = NS(guild=self.guild, channel_id=3, user=NS(id=10))

    async def test_persistence_and_scope(self):
        await self.bot.store.mark(1, 2, 10)
        await self.bot.store.mark(1, 2, 10)
        reopened = Store(self.config.database_path)
        await reopened.initialize()
        self.assertTrue(await reopened.has(1, 2, 10))
        for ids in [(9, 2, 10), (1, 9, 10), (1, 2, 99)]:
            self.assertFalse(await reopened.has(*ids))

    async def test_post_filter(self):
        msg = NS(guild=NS(id=1), channel=NS(id=2), author=NS(id=10, bot=False),
                 webhook_id=None, type=discord.MessageType.default)
        await self.bot.on_message(msg)
        self.assertTrue(await self.bot.store.has(1, 2, 10))
        msg.author.bot = True
        self.assertFalse(is_introduction(msg, self.config))
        msg.author.bot = False
        msg.channel.id = 99
        self.assertFalse(is_introduction(msg, self.config))
        msg.channel.id = 2
        msg.type = discord.MessageType.new_member
        self.assertFalse(is_introduction(msg, self.config))
        msg.guild = None
        self.assertFalse(is_introduction(msg, self.config))

    async def test_verification_requires_intro(self):
        self.bot.introduced = AsyncMock(return_value=False)
        self.assertIn('先に', await self.bot.verify(self.interaction))
        self.member.add_roles.assert_not_awaited()
        self.bot.introduced.return_value = True
        self.assertIn('完了', await self.bot.verify(self.interaction))
        self.member.add_roles.assert_awaited_once_with(self.role, reason='自己紹介済みユーザーのボタン認証')

    async def test_existing_member_and_wrong_guild(self):
        self.member.roles = [self.role]
        self.assertIn('すでに', await self.bot.verify(self.interaction))
        self.guild.id = 99
        self.assertIn('指定された', await self.bot.verify(self.interaction))
        self.member.add_roles.assert_not_awaited()

    async def test_bad_role_rejected(self):
        self.role.__ge__.return_value = True
        self.assertIn('設定を確認', await self.bot.verify(self.interaction))
        self.member.add_roles.assert_not_awaited()

    async def test_history_recovers_offline_post(self):
        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 2
        msg = NS(guild=NS(id=1), channel=channel, author=NS(id=10, bot=False),
                 webhook_id=None, type=discord.MessageType.reply)
        async def history(**kwargs):
            yield msg
        channel.history = history
        self.guild.get_channel.return_value = channel
        self.assertTrue(await self.bot.introduced(self.guild, 10))
        self.assertTrue(await self.bot.store.has(1, 2, 10))

    async def test_history_failure_never_grants_role(self):
        self.bot.introduced = AsyncMock(side_effect=TimeoutError)
        with self.assertRaises(TimeoutError):
            await self.bot.verify(self.interaction)
        self.member.add_roles.assert_not_awaited()

    async def test_persistent_view(self):
        view = VerificationView(self.bot)
        self.assertTrue(view.is_persistent())
        self.assertEqual(view.children[0].custom_id, 'tournament:verify:v1')

    async def test_setup_denied_to_non_admin(self):
        interaction = NS(guild_id=1, permissions=NS(administrator=False),
                         response=NS(send_message=AsyncMock()))
        await self.bot.setup_verification(interaction)
        interaction.response.send_message.assert_awaited_once()
        self.assertTrue(interaction.response.send_message.call_args.kwargs['ephemeral'])

    async def test_config_hides_token_and_validates_ids(self):
        self.assertNotIn('test-secret', repr(self.config))
        with patch('bot.load_dotenv'), patch.dict('os.environ', {
            'DISCORD_TOKEN': 'test-secret', 'GUILD_ID': 'oops'}, clear=True):
            with self.assertRaisesRegex(ValueError, 'GUILD_ID'):
                Config.load()


if __name__ == '__main__':
    unittest.main()
