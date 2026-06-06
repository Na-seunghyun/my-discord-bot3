import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import random
import asyncio
import re

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

GUILD_ID = 1309433603331198977
GUILD_OBJ = discord.Object(id=GUILD_ID)

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ======================================================
# 🔥 권한 역할
# ======================================================
ALLOWED_ROLES = {
    1317699909536977038,
    1317699017056063610
}

# ======================================================
# 🚨 권한 체크
# ======================================================
async def check_permission(interaction: discord.Interaction) -> bool:
    user_roles = {r.id for r in interaction.user.roles}

    if user_roles & ALLOWED_ROLES:
        return True

    channel = interaction.guild.system_channel or interaction.channel

    await channel.send(
        f"🚨 누군가 월권을 시도하고있습니다. 토끼님 그를 처벌해주세요\n"
        f"👤 사용자: {interaction.user.mention} (`{interaction.user.id}`)"
    )
    return False


# ======================================================
# 🎯 음성 유저 가져오기
# ======================================================
def get_voice_members(interaction):
    voice = interaction.user.voice
    if not voice or not voice.channel:
        return None, None

    return [m for m in voice.channel.members if not m.bot], voice.channel


# ======================================================
# 🎯 팀 생성
# ======================================================
def create_teams(members, size):
    random.shuffle(members)
    return [members[i:i+size] for i in range(0, len(members), size)]


# ======================================================
# ⚡ 이동
# ======================================================
async def move_members_fast(members, target):
    async def move(m):
        if m and m.voice:
            try:
                await m.move_to(target)
            except:
                pass

    await asyncio.gather(*(move(m) for m in members))


# ======================================================
# 🎮 팀 이동
# ======================================================
class MoveTeamsView(discord.ui.View):
    def __init__(self, teams):
        super().__init__(timeout=300)
        self.teams = teams

    @discord.ui.button(label="팀 이동하기", style=discord.ButtonStyle.green)
    async def move(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.defer()

        for i, team in enumerate(self.teams):
            if i >= 10:
                break

            ch = interaction.guild.get_channel(VOICE_CHANNEL_IDS[i])
            if isinstance(ch, discord.VoiceChannel):
                await move_members_fast(team, ch)

        await interaction.followup.send("✅ 팀 이동 완료")


# ======================================================
# 📢 채널 선택 UI (안정 버전)
# ======================================================
class SummonChannelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.selected_channels = set()

        self.select = discord.ui.ChannelSelect(
            placeholder="음성채널 선택",
            min_values=1,
            max_values=10,
            channel_types=[discord.ChannelType.voice]
        )

        self.select.callback = self.on_select
        self.add_item(self.select)

    async def on_select(self, interaction: discord.Interaction):
        self.selected_channels = {c.id for c in self.select.values}
        await interaction.response.edit_message(
            content="✅ 채널 선택 완료",
            view=self
        )

    @discord.ui.button(label="전체 소환", style=discord.ButtonStyle.green)
    async def summon(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not await check_permission(interaction):
            return await interaction.response.send_message("❌ 권한 없음", ephemeral=True)

        if not interaction.user.voice:
            return await interaction.response.send_message("❌ 음성채널 없음", ephemeral=True)

        if not self.selected_channels:
            return await interaction.response.send_message("❌ 채널 선택 필요", ephemeral=True)

        await interaction.response.defer()

        target = interaction.user.voice.channel

        members = []
        for ch_id in self.selected_channels:
            ch = interaction.guild.get_channel(ch_id)
            if isinstance(ch, discord.VoiceChannel):
                members += [m for m in ch.members if not m.bot]

        await move_members_fast(members, target)

        await interaction.followup.send(f"⚡ {len(members)}명 소환 완료")


# ======================================================
# 👤 개별 소환 (음성 유저만 표시)
# ======================================================
class VoiceUserSelect(discord.ui.Select):
    def __init__(self, guild: discord.Guild):

        options = [
            discord.SelectOption(
                label=m.display_name,
                value=str(m.id)
            )
            for m in guild.members
            if m.voice and m.voice.channel and not m.bot
        ][:25]

        super().__init__(
            placeholder="음성채널 유저 선택",
            min_values=1,
            max_values=len(options),
            options=options
        )


class SummonUserView(discord.ui.View):
    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=120)
        self.selected = set()

        self.select = VoiceUserSelect(guild)

        async def callback(interaction: discord.Interaction):
            self.selected = {int(v) for v in self.select.values}
            await interaction.response.defer()

        self.select.callback = callback
        self.add_item(self.select)

    @discord.ui.button(label="즉시 소환", style=discord.ButtonStyle.green)
    async def summon(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not await check_permission(interaction):
            return await interaction.response.send_message("❌ 권한 없음", ephemeral=True)

        if not interaction.user.voice:
            return await interaction.response.send_message("❌ 음성채널 없음", ephemeral=True)

        if not self.selected:
            return await interaction.response.send_message("❌ 유저 선택 필요", ephemeral=True)

        await interaction.response.defer()

        target = interaction.user.voice.channel

        members = []
        for uid in self.selected:
            m = interaction.guild.get_member(uid)
            if m and m.voice:
                members.append(m)

        await move_members_fast(members, target)

        await interaction.followup.send(f"⚡ {len(members)}명 소환 완료")


# ======================================================
# 🔎 /검사 기능
# ======================================================
@bot.tree.command(name="검사", guild=GUILD_OBJ)
async def check_nicknames(interaction: discord.Interaction):

    if not await check_permission(interaction):
        return await interaction.response.send_message("❌ 권한 없음", ephemeral=True)

    pattern = re.compile(r".+\/.+\/\d{2}$")

    invalid = []

    for m in interaction.guild.members:
        if m.bot:
            continue

        if not m.nick:
            invalid.append(m)
            continue

        if not pattern.match(m.nick):
            invalid.append(m)

    if not invalid:
        return await interaction.response.send_message("✅ 모든 닉네임 정상입니다")

    msg = "⚠️ 닉네임 오류 사용자:\n\n"
    for m in invalid:
        msg += f"• {m.mention} ({m.nick})\n"

        try:
            await m.send("⚠️ 닉네임 형식이 올바르지 않습니다: 닉네임 / 게임아이디 / 년생(2자리)")
        except:
            pass

    await interaction.response.send_message(msg)


# ======================================================
# 🚀 실행
# ======================================================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.tree.sync(guild=GUILD_OBJ)
    print("Synced")


bot.run(TOKEN)
