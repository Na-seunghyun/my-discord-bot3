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
# 🎯 닉네임 검사 함수 (🔥 핵심 수정)
# ======================================================
def is_valid_nick(nick: str) -> bool:
    if not nick:
        return False

    parts = [p.strip() for p in nick.split("/")]

    if len(parts) != 3:
        return False

    name, gameid, year = parts

    if not name or not gameid:
        return False

    if not year.isdigit() or len(year) != 2:
        return False

    return True


# ======================================================
# 🔎 /검사 (완전 안정 버전)
# ======================================================
@bot.tree.command(name="검사", guild=GUILD_OBJ)
async def check_nicknames(interaction: discord.Interaction):

    # 🚨 권한 체크
    if not await check_permission(interaction):
        return await interaction.response.send_message("❌ 권한 없음", ephemeral=True)

    # ⚡ 즉시 ACK (필수)
    await interaction.response.defer(ephemeral=True)

    invalid = []

    for m in interaction.guild.members:
        if m.bot:
            continue

        nick = m.nick or m.name

        if not is_valid_nick(nick):
            invalid.append(m)

    if not invalid:
        return await interaction.followup.send("✅ 모든 닉네임 정상입니다")

    msg = "⚠️ 닉네임 오류 사용자:\n\n"

    for m in invalid[:30]:
        msg += f"• {m.mention} ({m.nick or m.name})\n"

        # DM 안내
        try:
            await m.send("⚠️ 닉네임 형식 오류\n형식: 닉네임 / 게임아이디 / 2자리 년생")
        except:
            pass

    await interaction.followup.send(msg)


# ======================================================
# 🤖 시작
# ======================================================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.tree.sync(guild=GUILD_OBJ)
    print("Synced")


bot.run(TOKEN)
