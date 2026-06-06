import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import random
import asyncio

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

GUILD_ID = 1309433603331198977
GUILD_OBJ = discord.Object(id=GUILD_ID)

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

VOICE_CHANNEL_IDS = [
    1309433603331198982,
    1309750071918723092,
    1310095200487604264,
    1310095226366595093,
    1309433603331198983,
    1313114837764669510,
    1482445089312870490,
    1482445011659395275,
    1483413953844482168,
    1483414016314314888
]


# ======================================================
# 🎯 유저 가져오기
# ======================================================
def get_same_voice_members(interaction):
    voice = interaction.user.voice
    if not voice or not voice.channel:
        return None, None

    return [m for m in voice.channel.members if not m.bot], voice.channel


# ======================================================
# 🎯 팀 생성
# ======================================================
def create_teams(members, size):
    random.shuffle(members)
    return [members[i:i + size] for i in range(0, len(members), size)]


# ======================================================
# ⚡ 초고속 이동 (안정 버전)
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
# 🎮 팀 이동 UI
# ======================================================
class MoveTeamsView(discord.ui.View):
    def __init__(self, teams):
        super().__init__(timeout=300)
        self.teams = teams

    @discord.ui.button(label="팀 이동하기", style=discord.ButtonStyle.green)
    async def move(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.defer()

        guild = interaction.guild

        for i, team in enumerate(self.teams):

            if i >= len(VOICE_CHANNEL_IDS):
                break

            ch = guild.get_channel(VOICE_CHANNEL_IDS[i])

            if isinstance(ch, discord.VoiceChannel):
                await move_members_fast(team, ch)

        await interaction.followup.send("✅ 팀 이동 완료")


# ======================================================
# 👤 개별 소환 (완전 안정)
# ======================================================
class SummonUserView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

        # 🔥 ID만 저장 (핵심)
        self.selected_users = set()

        self.select = discord.ui.UserSelect(
            placeholder="소환할 유저 선택",
            min_values=1,
            max_values=25
        )

        async def select_callback(interaction: discord.Interaction):
            # 🔥 객체 저장 금지 → ID만 저장
            self.selected_users = {u.id for u in self.select.values}
            await interaction.response.defer()

        self.select.callback = select_callback
        self.add_item(self.select)

    @discord.ui.button(label="즉시 소환", style=discord.ButtonStyle.green)
    async def summon(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not interaction.user.voice:
            await interaction.response.send_message("❌ 음성채널 없음", ephemeral=True)
            return

        if not self.selected_users:
            await interaction.response.send_message("❌ 유저 선택 필요", ephemeral=True)
            return

        await interaction.response.defer()

        target = interaction.user.voice.channel

        members = []

        for uid in self.selected_users:
            m = interaction.guild.get_member(uid)
            if m and m.voice:
                members.append(m)

        await move_members_fast(members, target)

        await interaction.followup.send(f"⚡ {len(members)}명 소환 완료")


# ======================================================
# 📢 채널 소환 (🔥 핵심 안정 버전)
# ======================================================
class SummonChannelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

        # 🔥 채널 ID만 저장 (핵심)
        self.selected_channels = set()

        self.select = discord.ui.ChannelSelect(
            placeholder="음성채널 선택",
            min_values=1,
            max_values=10,
            channel_types=[discord.ChannelType.voice]
        )

        async def select_callback(interaction: discord.Interaction):
            # 🔥 객체 저장 금지 → ID만 저장
            self.selected_channels = {ch.id for ch in self.select.values}
            await interaction.response.defer()

        self.select.callback = select_callback
        self.add_item(self.select)

    @discord.ui.button(label="즉시 전체 소환", style=discord.ButtonStyle.green)
    async def summon(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not interaction.user.voice:
            await interaction.response.send_message("❌ 음성채널 없음", ephemeral=True)
            return

        if not self.selected_channels:
            await interaction.response.send_message("❌ 채널 선택 필요", ephemeral=True)
            return

        await interaction.response.defer()

        target = interaction.user.voice.channel

        members = []

        for ch_id in self.selected_channels:
            ch = interaction.guild.get_channel(ch_id)

            if isinstance(ch, discord.VoiceChannel):
                members.extend([m for m in ch.members if not m.bot])

        await move_members_fast(members, target)

        await interaction.followup.send(f"⚡ {len(members)}명 소환 완료")


# ======================================================
# 🤖 팀짜기
# ======================================================
@bot.tree.command(name="팀짜기", guild=GUILD_OBJ)
async def team(interaction: discord.Interaction, size: int):

    members, vc = get_same_voice_members(interaction)

    if not members:
        await interaction.response.send_message("❌ 음성채널 없음")
        return

    if size not in [2, 3, 4]:
        await interaction.response.send_message("❌ 2~4만 가능")
        return

    teams = create_teams(members, size)

    msg = f"🎯 팀 결과 ({vc.name})\n\n"

    for i, t in enumerate(teams, 1):
        msg += f"팀 {i}: " + ", ".join(m.display_name for m in t) + "\n"

    await interaction.response.send_message(msg, view=MoveTeamsView(teams))


# ======================================================
# 👤 개별소환
# ======================================================
@bot.tree.command(name="개별소환", guild=GUILD_OBJ)
async def summon_user(interaction: discord.Interaction):
    await interaction.response.send_message(
        "유저 선택",
        view=SummonUserView(),
        ephemeral=True
    )


# ======================================================
# 📢 채널소환
# ======================================================
@bot.tree.command(name="채널소환", guild=GUILD_OBJ)
async def summon_channel(interaction: discord.Interaction):
    await interaction.response.send_message(
        "채널 선택",
        view=SummonChannelView(),
        ephemeral=True
    )


# ======================================================
# 🚀 봇 시작
# ======================================================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.tree.sync(guild=GUILD_OBJ)
    print("Synced")


bot.run(TOKEN)
