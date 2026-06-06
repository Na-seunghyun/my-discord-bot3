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

# ---------------------------
# 🎯 유저 가져오기
# ---------------------------
def get_same_voice_members(interaction: discord.Interaction):
    voice = interaction.user.voice

    if voice is None or voice.channel is None:
        return None, None

    return [m for m in voice.channel.members if not m.bot], voice.channel


# ---------------------------
# 🎯 팀 생성
# ---------------------------
def create_teams(members, size: int):
    random.shuffle(members)
    return [members[i:i + size] for i in range(0, len(members), size)]


# ---------------------------
# ⚡ SAFE + FAST 이동 (핵심 개선)
# ---------------------------
async def move_members_fast(members, target_channel):

    async def move(member):
        if member.voice is None:
            return
        try:
            await member.move_to(target_channel)
        except:
            pass

    # 🔥 5명씩 나눠서 안전 + 빠름
    batch_size = 5

    for i in range(0, len(members), batch_size):
        batch = members[i:i+batch_size]
        await asyncio.gather(*[move(m) for m in batch])
        await asyncio.sleep(0.05)


# ---------------------------
# 🎮 팀 이동 버튼
# ---------------------------
class MoveTeamsView(discord.ui.View):
    def __init__(self, teams):
        super().__init__(timeout=300)
        self.teams = teams

    @discord.ui.button(label="팀 이동하기", style=discord.ButtonStyle.green)
    async def move(self, interaction: discord.Interaction, button: discord.ui.Button):

        guild = interaction.guild

        for i, team in enumerate(self.teams):

            if i >= len(VOICE_CHANNEL_IDS):
                break

            channel = guild.get_channel(VOICE_CHANNEL_IDS[i])

            if not isinstance(channel, discord.VoiceChannel):
                continue

            await move_members_fast(team, channel)

        await interaction.response.send_message("✅ 팀 이동 완료!", ephemeral=False)


# ======================================================
# 👤 개별 소환
# ======================================================
class SummonUserView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

        self.user_select = discord.ui.UserSelect(
            placeholder="소환할 유저 선택",
            min_values=1,
            max_values=25
        )

        self.add_item(self.user_select)

    @discord.ui.button(label="즉시 소환", style=discord.ButtonStyle.green)
    async def summon(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not interaction.user.voice:
            await interaction.response.send_message("❌ 음성채널 없음")
            return

        target = interaction.user.voice.channel

        members = [u for u in self.user_select.values if u.voice]

        await move_members_fast(members, target)

        await interaction.response.send_message(f"⚡ {len(members)}명 즉시 소환 완료")


# ======================================================
# 📢 채널 소환
# ======================================================
class SummonChannelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

        self.channel_select = discord.ui.ChannelSelect(
            placeholder="소환할 음성채널 선택",
            min_values=1,
            max_values=10
        )

        self.add_item(self.channel_select)

    @discord.ui.button(label="즉시 전체 소환", style=discord.ButtonStyle.green)
    async def summon(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not interaction.user.voice:
            await interaction.response.send_message("❌ 음성채널 없음")
            return

        target = interaction.user.voice.channel

        members = []

        for ch in self.channel_select.values:
            for m in ch.members:
                if not m.bot and m.voice:
                    members.append(m)

        await move_members_fast(members, target)

        await interaction.response.send_message(f"⚡ {len(members)}명 즉시 소환 완료")


# ---------------------------
# 🤖 팀짜기
# ---------------------------
@bot.tree.command(name="팀짜기", description="같은 음성채널 기준 팀 생성", guild=GUILD_OBJ)
async def team(interaction: discord.Interaction, size: int):

    members, voice_channel = get_same_voice_members(interaction)

    if len(members) == 0:
        await interaction.response.send_message("❌ 음성채널에 사람이 없습니다.")
        return

    if size not in [2, 3, 4]:
        await interaction.response.send_message("❌ 팀 크기는 2, 3, 4만 가능합니다.")
        return

    teams = create_teams(members, size)

    msg = f"🎯 **팀 결과 (채널: {voice_channel.name})**\n\n"

    for i, t in enumerate(teams, 1):
        names = ", ".join([m.display_name for m in t])
        msg += f"**팀 {i} ({len(t)}명)**: {names}\n"

    await interaction.response.send_message(msg, view=MoveTeamsView(teams))


# ---------------------------
# 👤 개별소환
# ---------------------------
@bot.tree.command(name="개별소환", description="유저 선택 소환", guild=GUILD_OBJ)
async def summon_user(interaction: discord.Interaction):
    await interaction.response.send_message(
        "👤 소환할 유저 선택",
        view=SummonUserView(),
        ephemeral=True
    )


# ---------------------------
# 📢 채널소환
# ---------------------------
@bot.tree.command(name="채널소환", description="채널 전체 소환", guild=GUILD_OBJ)
async def summon_channel(interaction: discord.Interaction):
    await interaction.response.send_message(
        "📢 소환할 채널 선택",
        view=SummonChannelView(),
        ephemeral=True
    )


# ---------------------------
# 🤖 봇 시작
# ---------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

    await bot.tree.sync(guild=GUILD_OBJ)
    print("Synced commands")


# ---------------------------
# RUN
# ---------------------------
bot.run(TOKEN)
