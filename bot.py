import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import random

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

# 🔥 서버 ID
GUILD_ID = 1309433603331198977
GUILD_OBJ = discord.Object(id=GUILD_ID)

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# 🔥 음성채널 순서 (고정 이동 배열)
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
# 🎯 같은 음성채널 유저 가져오기
# ---------------------------
def get_same_voice_members(interaction: discord.Interaction):
    voice = interaction.user.voice

    if voice is None or voice.channel is None:
        return None, None

    channel = voice.channel

    members = [m for m in channel.members if not m.bot]

    return members, channel


# ---------------------------
# 🎯 팀 생성
# ---------------------------
def create_teams(members, size: int):
    random.shuffle(members)
    return [members[i:i + size] for i in range(0, len(members), size)]


# ---------------------------
# 🎮 팀 이동 버튼 (FIXED)
# ---------------------------
class MoveTeamsView(discord.ui.View):
    def __init__(self, teams):
        super().__init__(timeout=300)
        self.teams = teams

    @discord.ui.button(label="팀 이동하기", style=discord.ButtonStyle.green)
    async def move(self, interaction: discord.Interaction, button: discord.ui.Button):

        guild = interaction.guild

        for i, team in enumerate(self.teams):

            # 🔥 무조건 순서대로 배치
            if i >= len(VOICE_CHANNEL_IDS):
                break

            target_channel = guild.get_channel(VOICE_CHANNEL_IDS[i])

            if not isinstance(target_channel, discord.VoiceChannel):
                continue

            for member in team:
                try:
                    await member.move_to(target_channel)
                except:
                    pass

        await interaction.response.send_message("✅ 팀 이동 완료!", ephemeral=False)


# ---------------------------
# 🤖 슬래시 커맨드 (서버 전용)
# ---------------------------
@bot.tree.command(name="팀짜기", description="같은 음성채널 기준 팀 생성", guild=GUILD_OBJ)
async def team(interaction: discord.Interaction, size: int):

    result = get_same_voice_members(interaction)

    if result == (None, None):
        await interaction.response.send_message("❌ 음성채널에 들어가 있어야 합니다.")
        return

    members, voice_channel = result

    if len(members) == 0:
        await interaction.response.send_message("❌ 음성채널에 사람이 없습니다.")
        return

    if size not in [2, 3, 4]:
        await interaction.response.send_message("❌ 팀 크기는 2, 3, 4만 가능합니다.")
        return

    teams = create_teams(members, size)

    msg = f"🎯 **팀 결과 (채널: {voice_channel.name})**\n\n"

    for i, team in enumerate(teams, 1):
        names = ", ".join([m.display_name for m in team])
        msg += f"**팀 {i} ({len(team)}명)**: {names}\n"

    view = MoveTeamsView(teams)

    await interaction.response.send_message(msg, view=view)


# ---------------------------
# 🤖 봇 시작 + GUILD SYNC
# ---------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

    try:
        synced = await bot.tree.sync(guild=GUILD_OBJ)
        print(f"Synced {len(synced)} commands (guild only)")
    except Exception as e:
        print(e)


# ---------------------------
# RUN
# ---------------------------
bot.run(TOKEN)
