"""部内向け自己紹介・認証Bot。python bot.py で起動。"""
import asyncio
import logging
import os
import signal
from dataclasses import dataclass, field
from pathlib import Path

import discord
from discord import app_commands
from dotenv import load_dotenv

from storage import Store

LOG = logging.getLogger(__name__)
BASE = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Config:
    token: str = field(repr=False)
    guild_id: int
    intro_channel_id: int
    welcome_channel_id: int
    participant_role_id: int
    database_path: Path

    @classmethod
    def load(cls):
        load_dotenv(BASE / '.env')
        token = os.getenv('DISCORD_TOKEN', '').strip()
        if not token or token == 'replace_with_bot_token':
            raise ValueError('DISCORD_TOKEN を .env または環境変数に設定してください。')
        ids = []
        for key in ('GUILD_ID', 'INTRO_CHANNEL_ID', 'WELCOME_CHANNEL_ID', 'PARTICIPANT_ROLE_ID'):
            value = os.getenv(key, '').strip()
            if not value.isascii() or not value.isdecimal() or int(value) <= 0:
                raise ValueError(f'{key} に正の数値IDを設定してください。')
            ids.append(int(value))
        path = Path(os.getenv('DATABASE_PATH', 'data/bot.sqlite3'))
        return cls(token, *ids, path if path.is_absolute() else BASE / path)


def is_introduction(message, config):
    return (message.guild is not None and message.guild.id == config.guild_id
            and message.channel.id == config.intro_channel_id
            and not message.author.bot and message.webhook_id is None
            and message.type in (discord.MessageType.default, discord.MessageType.reply))


class VerificationView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label='認証する', emoji='✅', style=discord.ButtonStyle.success,
                       custom_id='tournament:verify:v1')
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            result = await self.bot.verify(interaction)
        except discord.Forbidden:
            result = 'Botの権限が足りません。管理者にチャンネル権限とロールの順序を確認してもらってください。'
        except (discord.HTTPException, TimeoutError):
            LOG.warning('Discordへの確認が完了しませんでした。')
            result = '確認に時間がかかっているか、Discordとの通信に失敗しました。少し待って再度お試しください。'
        except Exception:
            LOG.exception('認証処理に失敗しました。')
            result = '認証処理に失敗しました。管理者にお知らせください。'
        await interaction.followup.send(result, ephemeral=True)


class TournamentBot(discord.Client):
    def __init__(self, config):
        # 本文や全メンバー一覧を読まないため、特権Intentは不要。
        super().__init__(intents=discord.Intents(guilds=True, guild_messages=True),
                         allowed_mentions=discord.AllowedMentions.none())
        self.config = config
        self.store = Store(config.database_path)
        self.tree = app_commands.CommandTree(self)
        self.tree.add_command(app_commands.Command(
            name='setup_verification', description='はじめにチャンネルへ認証ボタンを設置（管理者専用）',
            callback=self.setup_verification), guild=discord.Object(id=config.guild_id))

    async def setup_hook(self):
        await self.store.initialize()
        self.add_view(VerificationView(self))
        await self.tree.sync(guild=discord.Object(id=self.config.guild_id))

    async def on_ready(self):
        LOG.info('Bot接続完了: %s / サーバーID: %s', self.user, self.config.guild_id)
        if self.get_guild(self.config.guild_id) is None:
            LOG.error('指定したサーバーが見つかりません。招待とGUILD_IDを確認してください。')

    async def on_message(self, message):
        if is_introduction(message, self.config):
            await self.store.mark(message.guild.id, message.channel.id, message.author.id)

    async def introduced(self, guild, user_id):
        c = self.config
        if await self.store.has(guild.id, c.intro_channel_id, user_id):
            return True
        channel = guild.get_channel(c.intro_channel_id)
        if not isinstance(channel, discord.TextChannel):
            raise ValueError('自己紹介チャンネルが見つからないか通常のテキストチャンネルではありません。')
        # 導入前・停止中の投稿も対象。履歴確認の失敗を未投稿と扱わない。
        async with asyncio.timeout(45):
            async for message in channel.history(limit=None):
                if message.author.id == user_id and is_introduction(message, c):
                    await self.store.mark(guild.id, channel.id, user_id)
                    return True
        return False

    async def verify(self, interaction):
        c = self.config
        guild = interaction.guild
        if guild is None or guild.id != c.guild_id or interaction.channel_id != c.welcome_channel_id:
            return '指定されたサーバーの「はじめに」チャンネルで認証してください。'
        member = await guild.fetch_member(interaction.user.id)
        role = guild.get_role(c.participant_role_id)
        me = guild.me
        if (role is None or role.is_default() or role.managed or me is None
                or not me.guild_permissions.manage_roles or role >= me.top_role
                or role.permissions.administrator):
            return '参加者ロールの設定を確認してください。Botには「ロールの管理」権限と、参加者ロールより上のロールが必要です。参加者ロールに管理者権限は設定できません。'
        if role in member.roles:
            return 'すでに認証済みです。'
        if not await self.introduced(guild, member.id):
            return f'先に <#{c.intro_channel_id}> に自己紹介を投稿してから、もう一度押してください。'
        await member.add_roles(role, reason='自己紹介済みユーザーのボタン認証')
        return '認証が完了しました！ 大会参加者ロールを付与しました。'

    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def setup_verification(self, interaction: discord.Interaction):
        c = self.config
        if interaction.guild_id != c.guild_id or not interaction.permissions.administrator:
            await interaction.response.send_message('この操作は対象サーバーの管理者専用です。', ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        channel = interaction.guild.get_channel(c.welcome_channel_id)
        if not isinstance(channel, discord.TextChannel):
            await interaction.followup.send('WELCOME_CHANNEL_ID を確認してください。', ephemeral=True)
            return
        try:
            message = await channel.send(
                f'ようこそ！\n<#{c.intro_channel_id}> に自己紹介を投稿したら、下の「認証する」を押してください。\n'
                '自己紹介テンプレート：\n名前：\n学年：\nチーム名：', view=VerificationView(self))
        except discord.HTTPException:
            await interaction.followup.send('ボタンを設置できません。Botの閲覧・送信権限を確認してください。', ephemeral=True)
            return
        await interaction.followup.send(f'認証ボタンを設置しました：{message.jump_url}', ephemeral=True)


async def main(config):
    bot = TournamentBot(config)
    async with bot:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, lambda: asyncio.create_task(bot.close()))
            except NotImplementedError:
                pass
        await bot.start(config.token)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    try:
        config = Config.load()
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    try:
        asyncio.run(main(config))
    except discord.LoginFailure:
        raise SystemExit('Botトークンが無効です。DISCORD_TOKEN を確認してください。') from None
