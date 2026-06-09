import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import random
import asyncio
import edge_tts
import uuid
import re
from typing import Literal
import emoji
import traceback

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
# 📢 공지 상태
# ======================================================
announcement_running = False

# ======================================================
# 🔊 토끼봇 TTS
# ======================================================
TTS_TEXT_CHANNEL_ID = 1513451508597788774

tts_sessions = {}

VOICE_POOL = [
    "ko-KR-SunHiNeural",
    "ko-KR-InJoonNeural",
    "ko-KR-HyunsuMultilingualNeural"
]

VOICE_NAMES = {
    "ko-KR-SunHiNeural": "선희",
    "ko-KR-InJoonNeural": "인준",
    "ko-KR-HyunsuMultilingualNeural": "현수"
}

# ======================================================
# 🎯 음성 채널
# ======================================================
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
# 🔥 채널 상태 체크 (핵심 수정)
# ======================================================
def is_channel_free(channel: discord.VoiceChannel) -> bool:
    return len([m for m in channel.members if not m.bot]) == 0


def get_sorted_channels(guild: discord.Guild):
    channels = []
    for cid in VOICE_CHANNEL_IDS:
        ch = guild.get_channel(cid)
        if isinstance(ch, discord.VoiceChannel):
            channels.append(ch)
    return channels


def build_channel_queue(guild: discord.Guild):
    channels = get_sorted_channels(guild)

    free = [ch for ch in channels if is_channel_free(ch)]
    used = [ch for ch in channels if not is_channel_free(ch)]

    return free + used


def clean_tts_text(text: str) -> str:

    # URL 제거
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'www\.\S+', '', text)
    text = re.sub(r'discord\.gg/\S+', '', text)

    # 멘션 제거
    text = re.sub(r'<@!?\d+>', '누군가', text)

    # 채널 멘션 제거
    text = re.sub(r'<#\d+>', '', text)

    # 역할 멘션 제거
    text = re.sub(r'<@&\d+>', '', text)

    # 웃음/울음 표현을 TTS 친화적으로 변환
    text = re.sub(r'ㅋ{3,}', '크크크', text)
    text = re.sub(r'ㅎ{3,}', '하하하', text)
    text = re.sub(r'ㅠ{2,}', '흑흑', text)
    text = re.sub(r'ㅜ{2,}', '흑흑', text)

    text = text.strip()

    if len(text) > 200:
        text = text[:200]

    return text

async def generate_tts(
    text: str,
    filename: str,
    voice_name: str
):
    communicate = edge_tts.Communicate(
        text=text,
        voice=voice_name
    )

    await communicate.save(filename)


async def tts_worker(guild_id: int):

    session = tts_sessions[guild_id]
    queue = session["queue"]

    while True:

        item = await queue.get()

        if item is None:
            break

        text, voice_name = item

        vc = session["vc"]

        try:
            filename = f"tts_{uuid.uuid4().hex}.mp3"

            await generate_tts(
                text,
                filename,
                voice_name
            )

            audio = discord.FFmpegPCMAudio(filename)

            vc.play(audio)

            while vc.is_playing():
                await asyncio.sleep(0.1)

            try:
                os.remove(filename)
            except:
                pass

        except Exception as e:
            print("TTS 오류:", e)
            traceback.print_exc()

        queue.task_done()


# ======================================================
# 📢 공지용 음성 재생
# ======================================================
async def play_announcement(vc, text):

    filename = f"announce_{uuid.uuid4().hex}.mp3"

    try:

        await generate_tts(
            text,
            filename,
            "ko-KR-SunHiNeural"
        )

        vc.play(
            discord.FFmpegPCMAudio(filename)
        )

        while vc.is_playing():
            await asyncio.sleep(0.2)

    except Exception as e:
        print("공지 재생 오류:", e)

    finally:

        try:
            os.remove(filename)
        except:
            pass


# ======================================================
# 📢 기존 TTS 강제 종료
# ======================================================
async def shutdown_all_tts(guild):

    guild_id = guild.id

    session = tts_sessions.get(guild_id)

    if not session:
        return

    try:

        channel = guild.get_channel(
            TTS_TEXT_CHANNEL_ID
        )

        if channel:
            await channel.send(
                "⚠️ 운영자 공지 방송이 시작되어 현재 TTS 세션이 종료되었습니다.\n"
                "필요 시 다시 `/토끼tts입장` 후 이용해주세요."
            )

    except Exception as e:
        print("공지 안내 실패:", e)

    try:

        vc = session["vc"]

        if vc.is_playing():
            vc.stop()

        await vc.disconnect()

    except Exception as e:
        print("음성 연결 종료 실패:", e)

    try:
        session["queue"].put_nowait(None)
    except:
        pass

    tts_sessions.pop(guild_id, None)

# ======================================================
# 🎮 팀 이동 (핵심 수정 완료)
# ======================================================
class MoveTeamsView(discord.ui.View):
    def __init__(self, teams):
        super().__init__(timeout=300)
        self.teams = teams

    @discord.ui.button(label="팀 이동하기", style=discord.ButtonStyle.green)
    async def move(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.defer()

        channel_queue = build_channel_queue(interaction.guild)

        for i, team in enumerate(self.teams):
            if i >= len(channel_queue):
                break

            target = channel_queue[i]
            await move_members_fast(team, target)

        await interaction.followup.send("✅ 팀 이동 완료 (빈 채널 우선 적용)")


# ======================================================
# 📢 채널 선택 UI
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
# 👤 개별 소환
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
# 🤖 팀짜기
# ======================================================
@bot.tree.command(name="팀짜기", guild=GUILD_OBJ)
async def team(interaction: discord.Interaction, size: int):

    members, vc = get_voice_members(interaction)

    if not members:
        await interaction.response.send_message("❌ 음성채널 없음")
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
        "음성채널 유저 선택",
        view=SummonUserView(interaction.guild),
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

@bot.tree.command(name="토끼tts입장", guild=GUILD_OBJ)
async def tts_join(interaction: discord.Interaction):

    if not interaction.user.voice:
        return await interaction.response.send_message(
            "❌ 음성채널에 먼저 접속해주세요",
            ephemeral=True
        )

    guild_id = interaction.guild.id
    channel = interaction.user.voice.channel

    # 세션 생성
    if guild_id not in tts_sessions:

        vc = await channel.connect()

        # 🎧 헤드폰 끄기 (Self Deaf)
        try:
            await interaction.guild.change_voice_state(
                channel=channel,
                self_deaf=True
            )
        except Exception as e:
            print("Self Deaf 설정 실패:", e)

        tts_sessions[guild_id] = {
            "vc": vc,
            "channel_id": channel.id,
            "users": {},
            "queue": asyncio.Queue(),
            "task": asyncio.create_task(
                tts_worker(guild_id)
            )
        }

    session = tts_sessions[guild_id]

    await interaction.response.send_message(
        "🎧 TTS 세션 활성화됨\n"
        "👉 이제 /토끼tts등록 사용"
    )

@bot.tree.command(name="토끼tts등록", guild=GUILD_OBJ)
async def tts_register(interaction: discord.Interaction):

    guild_id = interaction.guild.id

    if guild_id not in tts_sessions:
        return await interaction.response.send_message(
            "❌ 먼저 /토끼tts입장",
            ephemeral=True
        )

    session = tts_sessions[guild_id]

    if interaction.user.id in session["users"]:
        voice_name = session["users"][interaction.user.id]
        return await interaction.response.send_message(
            f"✅ 이미 등록됨 ({VOICE_NAMES[voice_name]})",
            ephemeral=True
        )

    if len(session["users"]) >= 3:
        return await interaction.response.send_message(
            "❌ 최대 3명",
            ephemeral=True
        )

    used = set(session["users"].values())

    voice_name = next(
        v for v in VOICE_POOL
        if v not in used
    )

    session["users"][interaction.user.id] = voice_name

    await interaction.response.send_message(
        f"🎤 등록 완료: {VOICE_NAMES[voice_name]}"
    )

@bot.tree.command(name="토끼tts퇴장", guild=GUILD_OBJ)
async def tts_leave(interaction: discord.Interaction):

    guild_id = interaction.guild.id

    session = tts_sessions.get(guild_id)

    if not session:
        return await interaction.response.send_message(
            "❌ TTS 세션이 없습니다. /토끼tts입장 먼저 해주세요",
            ephemeral=True
        )

    user_id = interaction.user.id

    # 등록 안된 사람
    if user_id not in session["users"]:
        return await interaction.response.send_message(
            "❌ 등록된 사용자가 아닙니다",
            ephemeral=True
        )

    # 1️⃣ 유저 제거
    session["users"].pop(user_id, None)

    remaining = len(session["users"])

    # 2️⃣ 마지막 사용자 → 세션 종료
    if remaining == 0:

        vc = session["vc"]

        try:
            await vc.disconnect()
        except:
            pass

        # worker 종료 신호
        session["queue"].put_nowait(None)

        tts_sessions.pop(guild_id, None)

        await interaction.response.send_message(
            "🔇 마지막 사용자가 나가서 TTS 세션이 종료되었습니다.\n👉 다시 /토끼tts입장 해주세요"
        )

        return

    # 3️⃣ 아직 사용자 남아있음
    await interaction.response.send_message(
        f"🔇 퇴장 완료\n"
        f"👥 현재 사용중: {remaining}/3\n"
        f"🎤 1자리 남음 (등록 가능)"
    )


@bot.tree.command(
    name="공지",
    description="전체 음성채널 공지",
    guild=GUILD_OBJ
)
async def announce(
    interaction: discord.Interaction,
    내용: str
):

    global announcement_running

    # 권한 확인
    if not await check_permission(interaction):
        return await interaction.response.send_message(
            "❌ 권한 없음",
            ephemeral=True
        )

    # 이미 공지 진행중
    if announcement_running:
        return await interaction.response.send_message(
            "❌ 이미 공지 방송이 진행중입니다.",
            ephemeral=True
        )

    await interaction.response.defer()

    announcement_running = True

    try:

        # 기존 TTS 종료
        await shutdown_all_tts(
            interaction.guild
        )

        # 사람이 있는 음성채널 찾기
        targets = []

        for vc in interaction.guild.voice_channels:

            humans = [
                m for m in vc.members
                if not m.bot
            ]

            if humans:
                targets.append(vc)

        # 공지 시작 안내
        await interaction.followup.send(
            f"📢 공지 방송 시작\n"
            f"🎧 대상 채널: {len(targets)}개"
        )

        count = 0

        for vc in targets:

            try:

                voice_client = await vc.connect()

                # 🎧 헤드폰 끄기 (Self Deaf)
                try:
                    await interaction.guild.change_voice_state(
                        channel=vc,
                        self_deaf=True
                    )
                except Exception as e:
                    print(
                        "Self Deaf 설정 실패:",
                        e
                    )

                await play_announcement(
                    voice_client,
                    내용
                )

                await voice_client.disconnect()

                count += 1

                await asyncio.sleep(1)

            except Exception as e:

                print(
                    f"공지 실패 {vc.name}",
                    e
                )

        # 완료 메시지
        await interaction.followup.send(
            f"✅ 공지 완료\n"
            f"📢 방송 채널 수: {count}"
        )

        print(
            f"[공지 완료] "
            f"{interaction.user} "
            f"채널 {count}개"
        )

    except Exception as e:

        print(
            "공지 오류:",
            e
        )

        await interaction.followup.send(
            f"❌ 공지 중 오류 발생\n{e}"
        )

    finally:

        announcement_running = False

@bot.tree.command(name="토끼tts도움말", guild=GUILD_OBJ)
async def tts_help(interaction: discord.Interaction):

    msg = (
        "🎧 **토끼 TTS 사용 방법 안내**\n\n"

        "━━━━━━━━━━━━━━━━━━\n"
        "1️⃣ `/토끼tts입장`\n"
        "👉 TTS 시스템을 시작합니다\n"
        "👉 봇이 음성채널에 입장합니다\n\n"

        "2️⃣ `/토끼tts등록`\n"
        "👉 최대 3명까지 등록 가능합니다\n"
        "👉 등록된 사용자만 채팅이 TTS로 읽힙니다\n"
        "👉 자동으로 목소리가 배정됩니다 (선희 / 인준 / 현수)\n\n"

        "3️⃣ 채팅 사용\n"
        "👉 지정된 텍스트 채널에 메시지를 입력하면 자동 음성 변환됩니다\n"
        "👉 등록되지 않은 사용자는 반응하지 않습니다\n\n"

        "4️⃣ `/토끼tts퇴장`\n"
        "👉 본인만 TTS 등록을 해제합니다\n"
        "👉 모든 사용자가 나가면 TTS 세션이 종료됩니다\n"
        "👉 마지막 사용자 퇴장 시 봇도 음성채널에서 나갑니다\n\n"

        "5️⃣ `/공지 내용`\n"
        "👉 권한이 있는 운영자만 사용 가능합니다\n"
        "👉 사람이 있는 모든 음성채널에 순차적으로 공지를 방송합니다\n"
        "👉 공지 시작 시 현재 TTS 세션은 자동 종료됩니다\n"
        "👉 공지 종료 후 필요 시 다시 `/토끼tts입장` 해주세요\n\n"

        "━━━━━━━━━━━━━━━━━━\n"
        "⚠️ 규칙\n"
        "• 최대 3명까지 동시 사용 가능\n"
        "• 채널 이동 시 봇은 따라가지 않습니다\n"
        "• 반드시 입장 → 등록 순서로 사용하세요\n"
        "• 운영자가 `/공지`를 실행하면 현재 TTS 세션은 종료됩니다\n"
    )

    await interaction.response.send_message(
        msg,
        ephemeral=True
    )

# ======================================================
# 🎯 닉네임 검사
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


@bot.tree.command(name="검사", guild=GUILD_OBJ)
async def check_nicknames(interaction: discord.Interaction):

    if not await check_permission(interaction):
        return await interaction.response.send_message("❌ 권한 없음", ephemeral=True)

    await interaction.response.defer()

    invalid = []

    for m in interaction.guild.members:
        if m.bot:
            continue

        nick = m.nick or m.name

        if not is_valid_nick(nick):
            invalid.append(m)

    if not invalid:
        return await interaction.followup.send("✅ 모든 닉네임 정상입니다")

    msg = "⚠️ 닉네임 오류 사용자 목록\n\n"

    for m in invalid[:50]:
        msg += f"• {m.mention} ({m.nick or m.name})\n"

    await interaction.followup.send(
        msg,
        allowed_mentions=discord.AllowedMentions(users=True)
    )

@bot.event
async def on_message(message):

    if message.author.bot or not message.guild:
        return

    global announcement_running

    if announcement_running:
        return
        
    session = tts_sessions.get(message.guild.id)
    if not session:
        return

    vc = session.get("vc")
    if not vc or not vc.channel:
        return

    # ==================================================
    # 🎯 채널 필터 (텍스트 OR 음성채널 기준)
    # ==================================================

    is_text_channel = (message.channel.id == TTS_TEXT_CHANNEL_ID)

    is_voice_channel = False

    if message.author.voice and message.author.voice.channel:
        is_voice_channel = (
            message.author.voice.channel.id == vc.channel.id
        )

    if not (is_text_channel or is_voice_channel):
        return

    # ==================================================
    # 🚫 등록 유저 필터
    # ==================================================
    if message.author.id not in session["users"]:
        return

    text = clean_tts_text(message.content)

    if not text:
        return

    voice_name = session["users"][message.author.id]

    await session["queue"].put((text, voice_name))

    try:
        await message.delete()
    except:
        pass
# ======================================================
# 🚫 voice state (SESSION 구조에서는 비활성)
# ======================================================
@bot.event
async def on_voice_state_update(member, before, after):
    # session 기반 구조에서는 아무것도 하지 않음
    return
    
# ======================================================
# 🤖 시작
# ======================================================
@bot.event
async def on_ready():

    print(f"Logged in as {bot.user}")

    try:
        await bot.tree.sync(guild=GUILD_OBJ)
        print("Synced")
    except Exception as e:
        print(f"Sync error: {e}")

# ======================================================
# 🚀 실행
# ======================================================
bot.run(TOKEN)
