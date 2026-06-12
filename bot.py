import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import random
import asyncio
import edge_tts
import uuid
import re
import json
import hashlib
from datetime import datetime, timezone, timedelta
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

VOICE_OPTIONS = {
    "여자1": "ko-KR-SunHiNeural",
    "남자1": "ko-KR-InJoonNeural",
    "남자2": "ko-KR-HyunsuMultilingualNeural"
}

VOICE_NAMES = {
    "ko-KR-SunHiNeural": "여자1",
    "ko-KR-InJoonNeural": "남자1",
    "ko-KR-HyunsuMultilingualNeural": "남자2"
}

DEFAULT_TTS_VOICE = "ko-KR-SunHiNeural"

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

GAMBLE_DATA_FILE = "gamble_data.json"
GAMBLE_DAILY_ALLOWANCE = 500
GAMBLE_DATA_VERSION = 2
GAMBLE_WIN_RATE = 0.45
KST = timezone(timedelta(hours=9))
gamble_lock = asyncio.Lock()
DONATION_QR_FILE = "donation_qr.jpg"

GAMBLE_WIN_MESSAGES = [
    "🎰 잭팟은 아니지만 손맛은 확실합니다!",
    "🍀 오늘 운이 살짝 웃어줬습니다.",
    "💎 판돈이 예쁘게 불어났습니다.",
    "🔥 분위기 탔습니다. 하지만 다음 판은 모릅니다.",
    "🪙 동전이 굴러가더니 지갑으로 돌아왔습니다."
]

GAMBLE_LOSE_MESSAGES = [
    "🕳️ 판돈이 조용히 사라졌습니다.",
    "🥲 운이 잠깐 외출했습니다.",
    "💨 손에 쥐고 있던 돈이 바람이 됐습니다.",
    "🧊 차갑게 식었습니다. 다음 판은 다를지도요.",
    "📉 그래프가 잠깐 아래를 보고 있습니다."
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
# 🎲 도박 데이터
# ======================================================
def get_current_day_key() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


def load_gamble_data() -> dict:
    if not os.path.exists(GAMBLE_DATA_FILE):
        return {"users": {}}

    try:
        with open(GAMBLE_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print("도박 데이터 로드 실패:", e)
        return {"users": {}}

    if not isinstance(data, dict):
        return {"users": {}}

    data.setdefault("users", {})
    return data


def save_gamble_data(data: dict):
    try:
        with open(GAMBLE_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("도박 데이터 저장 실패:", e)


def get_gamble_account(data: dict, user_id: int) -> dict:
    users = data.setdefault("users", {})
    key = str(user_id)
    day_key = get_current_day_key()

    account = users.setdefault(
        key,
        {
            "profit": 0,
            "daily_bonus": GAMBLE_DAILY_ALLOWANCE,
            "day": day_key,
            "version": GAMBLE_DATA_VERSION,
            "wins": 0,
            "losses": 0
        }
    )

    if int(account.get("version", 0)) < GAMBLE_DATA_VERSION:
        account["daily_bonus"] = GAMBLE_DAILY_ALLOWANCE
        account["day"] = day_key
        account["version"] = GAMBLE_DATA_VERSION

    if "weekly_bonus" in account:
        account.pop("weekly_bonus", None)
        account["daily_bonus"] = GAMBLE_DAILY_ALLOWANCE

    if "week" in account:
        account.pop("week", None)
        account["day"] = ""

    if account.get("day") != day_key:
        account["daily_bonus"] = GAMBLE_DAILY_ALLOWANCE
        account["day"] = day_key

    account.setdefault("profit", 0)
    account.setdefault("daily_bonus", GAMBLE_DAILY_ALLOWANCE)
    account.setdefault("version", GAMBLE_DATA_VERSION)
    account.setdefault("wins", 0)
    account.setdefault("losses", 0)

    return account


def get_gamble_balance(account: dict) -> int:
    return int(account.get("profit", 0)) + int(account.get("daily_bonus", 0))


def subtract_gamble_balance(account: dict, amount: int):
    daily_bonus = int(account.get("daily_bonus", 0))
    from_bonus = min(daily_bonus, amount)

    account["daily_bonus"] = daily_bonus - from_bonus
    account["profit"] = int(account.get("profit", 0)) - (amount - from_bonus)


# ======================================================
# 🔮 사주 운세
# ======================================================
SAJU_ELEMENTS = {
    "木": "목",
    "火": "화",
    "土": "토",
    "金": "금",
    "水": "수"
}

SAJU_STEM_ELEMENTS = {
    "甲": "木", "乙": "木",
    "丙": "火", "丁": "火",
    "戊": "土", "己": "土",
    "庚": "金", "辛": "金",
    "壬": "水", "癸": "水"
}

SAJU_ELEMENT_KEYWORDS = {
    "木": ("성장", "새로운 시작", "관계 확장"),
    "火": ("표현", "열정", "주목받는 흐름"),
    "土": ("안정", "정리", "꾸준함"),
    "金": ("판단", "결단", "원칙"),
    "水": ("생각", "유연함", "정보")
}

SAJU_ELEMENT_ADVICE = {
    "木": "새로운 제안이나 대화를 가볍게 열어보기 좋은 흐름입니다.",
    "火": "표현력이 살아나는 날이라, 생각을 너무 오래 묵히지 않는 편이 좋습니다.",
    "土": "급하게 움직이기보다 정리하고 확인할수록 운이 안정됩니다.",
    "金": "판단이 또렷해지는 대신 말이 날카로워질 수 있어 한 박자 쉬면 좋습니다.",
    "水": "정보를 모으고 분위기를 읽는 데 강점이 생기는 날입니다."
}

SAJU_DAY_MASTER_TRAITS = {
    "甲": ("큰 나무", "곧게 뻗는 힘이 강하고, 목표가 생기면 꾸준히 밀고 가는 타입입니다."),
    "乙": ("풀과 꽃", "부드럽게 적응하고 관계 속에서 기회를 찾는 감각이 좋습니다."),
    "丙": ("태양", "밝게 드러나는 기운이 강하고, 분위기를 살리는 표현력이 있습니다."),
    "丁": ("촛불", "섬세한 집중력과 감정의 온도가 살아있는 타입입니다."),
    "戊": ("큰 산", "중심을 잡고 버티는 힘이 있으며, 주변을 안정시키는 편입니다."),
    "己": ("밭의 흙", "현실감각이 좋고, 작은 것을 쌓아 결과로 만드는 데 강합니다."),
    "庚": ("단단한 쇠", "결단력과 승부 감각이 있으며, 기준이 분명한 타입입니다."),
    "辛": ("보석", "디테일과 완성도에 민감하고, 감각적인 판단이 돋보입니다."),
    "壬": ("큰 물", "생각의 폭이 넓고 흐름을 읽는 능력이 좋은 편입니다."),
    "癸": ("비와 이슬", "조용히 스며드는 관찰력과 섬세한 이해력이 있습니다.")
}


def parse_birth_date(value: str):
    value = value.strip()

    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass

    return None


def parse_birth_time(value: str):
    value = value.strip()

    for fmt in ("%H:%M", "%H%M"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.hour, dt.minute
        except ValueError:
            pass

    if value.isdigit():
        hour = int(value)
        if 0 <= hour <= 23:
            return hour, 0

    return None


def get_saju_score(seed_text: str, label: str, low: int = 45, high: int = 96) -> int:
    digest = hashlib.sha256(f"{seed_text}:{label}".encode("utf-8")).hexdigest()
    return low + (int(digest[:8], 16) % (high - low + 1))


def build_saju_summary(user_id: int, birth_date, birth_time):
    from lunar_python import Solar

    hour, minute = birth_time
    solar = Solar.fromYmdHms(
        birth_date.year,
        birth_date.month,
        birth_date.day,
        hour,
        minute,
        0
    )

    lunar = solar.getLunar()
    eight_char = lunar.getEightChar()

    pillars = [
        eight_char.getYear(),
        eight_char.getMonth(),
        eight_char.getDay(),
        eight_char.getTime()
    ]

    wuxing_text = (
        eight_char.getYearWuXing()
        + eight_char.getMonthWuXing()
        + eight_char.getDayWuXing()
        + eight_char.getTimeWuXing()
    )

    counts = {element: wuxing_text.count(element) for element in SAJU_ELEMENTS}
    dominant = max(counts, key=counts.get)
    weakest = min(counts, key=counts.get)

    day_master = eight_char.getDay()[0]
    day_element = SAJU_STEM_ELEMENTS.get(day_master, dominant)

    seed_text = (
        f"{user_id}:{get_current_day_key()}:"
        f"{'-'.join(pillars)}:{wuxing_text}"
    )

    total_score = get_saju_score(seed_text, "total")
    money_score = get_saju_score(seed_text, "money")
    relation_score = get_saju_score(seed_text, "relation")
    gamble_score = get_saju_score(seed_text, "gamble", 35, 92)

    keywords = SAJU_ELEMENT_KEYWORDS.get(dominant, ("균형", "관찰", "정리"))

    element_counts = " / ".join(
        f"{SAJU_ELEMENTS[k]} {v}" for k, v in counts.items()
    )

    msg = (
        "🔮 **오늘의 사주 운세**\n\n"
        f"📅 기준일: {get_current_day_key()} (한국시간)\n"
        f"🧭 사주팔자: {' '.join(pillars)}\n"
        f"🌿 오행 분포: {element_counts}\n"
        f"☀️ 일간: {day_master}({SAJU_ELEMENTS.get(day_element, day_element)})\n\n"
        f"총운: **{total_score}점**\n"
        f"재물운: **{money_score}점**\n"
        f"관계운: **{relation_score}점**\n"
        f"승부운: **{gamble_score}점**\n\n"
        f"오늘 강한 기운은 **{SAJU_ELEMENTS[dominant]}**입니다.\n"
        f"{SAJU_ELEMENT_ADVICE.get(dominant, '균형을 살피면 좋은 날입니다.')}\n\n"
        f"부족한 기운은 **{SAJU_ELEMENTS[weakest]}** 쪽이라, "
        "그 부분은 무리하기보다 천천히 보완하는 편이 좋습니다.\n"
        f"행운 키워드: **{keywords[0]} / {keywords[1]} / {keywords[2]}**\n\n"
        "※ 재미용 운세입니다. 중요한 결정은 현실 정보와 함께 판단해주세요."
    )

    return msg


def build_saju_reading(user_id: int, birth_date, birth_time):
    from lunar_python import Solar

    hour, minute = birth_time
    solar = Solar.fromYmdHms(
        birth_date.year,
        birth_date.month,
        birth_date.day,
        hour,
        minute,
        0
    )

    lunar = solar.getLunar()
    eight_char = lunar.getEightChar()

    pillars = [
        eight_char.getYear(),
        eight_char.getMonth(),
        eight_char.getDay(),
        eight_char.getTime()
    ]

    wuxing_text = (
        eight_char.getYearWuXing()
        + eight_char.getMonthWuXing()
        + eight_char.getDayWuXing()
        + eight_char.getTimeWuXing()
    )

    counts = {element: wuxing_text.count(element) for element in SAJU_ELEMENTS}
    dominant = max(counts, key=counts.get)
    weakest = min(counts, key=counts.get)

    day_master = eight_char.getDay()[0]
    day_element = SAJU_STEM_ELEMENTS.get(day_master, dominant)
    day_title, day_trait = SAJU_DAY_MASTER_TRAITS.get(
        day_master,
        ("일간", "자신만의 흐름을 가지고 상황에 맞춰 움직이는 타입입니다.")
    )

    seed_text = (
        f"{user_id}:{get_current_day_key()}:"
        f"{'-'.join(pillars)}:{wuxing_text}:reading"
    )

    total_score = get_saju_score(seed_text, "total")
    money_score = get_saju_score(seed_text, "money")
    relation_score = get_saju_score(seed_text, "relation")
    gamble_score = get_saju_score(seed_text, "gamble", 35, 92)

    element_counts = " / ".join(
        f"{SAJU_ELEMENTS[k]} {v}" for k, v in counts.items()
    )
    keywords = SAJU_ELEMENT_KEYWORDS.get(dominant, ("균형", "관찰", "정리"))

    money_note = (
        "큰 한 방보다 작은 선택을 나눠서 가져가는 편이 안정적입니다."
        if money_score < 70
        else "흐름을 잘 타면 작은 이득을 키우기 좋은 날입니다."
    )
    relation_note = (
        "상대의 말을 끝까지 듣는 것이 관계운을 살립니다."
        if relation_score < 70
        else "가벼운 대화와 농담이 분위기를 부드럽게 만들 수 있습니다."
    )
    gamble_note = (
        "승부운이 강한 편은 아니니 올인보다 소액으로 분위기만 보는 쪽이 좋습니다."
        if gamble_score < 65
        else "승부 감각이 올라오지만, 과감함과 무모함은 한 끗 차이입니다."
    )

    msg = (
        "🔮 **사주풀이**\n\n"
        f"📅 입력 생일: {birth_date.strftime('%Y-%m-%d')} {hour:02d}:{minute:02d}\n"
        f"🧭 사주팔자: {' '.join(pillars)}\n"
        f"🌿 오행 분포: {element_counts}\n"
        f"☀️ 일간: {day_master}({SAJU_ELEMENTS.get(day_element, day_element)}) - {day_title}\n\n"
        "**1. 기본 성향**\n"
        f"{day_trait}\n"
        f"전체 흐름에서는 **{SAJU_ELEMENTS[dominant]}** 기운이 강하게 잡힙니다. "
        f"{SAJU_ELEMENT_ADVICE.get(dominant, '균형을 살피면 좋은 흐름입니다.')}\n\n"
        "**2. 부족한 기운**\n"
        f"상대적으로 부족한 쪽은 **{SAJU_ELEMENTS[weakest]}** 기운입니다. "
        "이 부분은 억지로 밀어붙이기보다, 주변 도움이나 작은 습관으로 보완하는 편이 좋습니다.\n\n"
        "**3. 오늘의 흐름**\n"
        f"총운은 **{total_score}점**입니다. "
        "오늘은 크게 무리하기보다 흐름을 보면서 선택하면 안정적입니다.\n\n"
        "**4. 재물운**\n"
        f"재물운은 **{money_score}점**입니다. {money_note}\n\n"
        "**5. 관계운**\n"
        f"관계운은 **{relation_score}점**입니다. {relation_note}\n\n"
        "**6. 승부운**\n"
        f"승부운은 **{gamble_score}점**입니다. {gamble_note}\n\n"
        "**7. 오늘의 키워드**\n"
        f"행운 키워드: **{keywords[0]} / {keywords[1]} / {keywords[2]}**\n"
        f"주의 키워드: **{SAJU_ELEMENTS[weakest]} 기운 부족 / 과한 확신 / 급한 선택**\n\n"
        "※ 오픈소스 만세력 계산을 바탕으로 만든 재미용 풀이입니다. "
        "중요한 결정은 현실 정보와 함께 판단해주세요."
    )

    return msg


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
    text = re.sub(r'ㅋ{2,}', '크크', text)
    text = re.sub(r'ㅎ{2,}', '하하', text)
    text = re.sub(r'ㅠ{2,}', '흑흑', text)
    text = re.sub(r'ㅜ{2,}', '흑흑', text)
    text = re.sub(r'ㄱ{2,}', '기역기역', text)
    text = re.sub(r'ㅇ{2,}', '응응', text)
    text = re.sub(r'ㄴ{2,}', '니은니은', text)
    text = re.sub(r'ㅂ{2,}', '비읍비읍', text)
    text = re.sub(r'ㅋ', '크', text)
    text = re.sub(r'ㅎ', '하', text)
    text = re.sub(r'ㅠ', '흑', text)
    text = re.sub(r'ㅜ', '흑', text)

    text = text.strip()

    if len(text) > 200:
        text = text[:200]

    return text

async def generate_tts(
    text: str,
    filename: str,
    voice_name: str,
    rate: str = "+0%"
):
    if voice_name not in VOICE_NAMES:
        voice_name = DEFAULT_TTS_VOICE

    communicate = edge_tts.Communicate(
        text=text,
        voice=voice_name,
        rate=rate
    )

    try:
        await communicate.save(filename)
    except Exception:
        if voice_name == DEFAULT_TTS_VOICE:
            raise

        communicate = edge_tts.Communicate(
            text=text,
            voice=DEFAULT_TTS_VOICE,
            rate=rate
        )
        await communicate.save(filename)


async def tts_worker(guild_id: int):

    session = tts_sessions[guild_id]
    queue = session["queue"]

    while True:

        item = await queue.get()

        try:
            if item is None:
                break

            if len(item) == 2:
                text, voice_name = item
                rate = "+0%"
            else:
                text, voice_name, rate = item

            vc = session["vc"]
            filename = None

            try:
                filename = f"tts_{uuid.uuid4().hex}.mp3"

                await generate_tts(
                    text,
                    filename,
                    voice_name,
                    rate
                )

                audio = discord.FFmpegPCMAudio(filename)

                vc.play(audio)

                while vc.is_playing():
                    await asyncio.sleep(0.1)

            except Exception as e:
                print("TTS 오류:", e)
                traceback.print_exc()

            finally:
                if filename:
                    try:
                        os.remove(filename)
                    except:
                        pass

        finally:
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
                "필요 시 다시 `/토끼tts등록 목소리`로 이용해주세요."
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

        if not await check_permission(interaction):
            return await interaction.response.send_message("❌ 권한 없음", ephemeral=True)

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
# 🐰 토끼봇 도움말 UI
# ======================================================
class RabbitBotHelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="기능소개", style=discord.ButtonStyle.primary)
    async def features(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "🐰 **토끼봇 기능소개**\n\n"
            "🎧 TTS: 채팅을 음성으로 읽어줍니다.\n"
            "🎲 도박: 매일 지급되는 가상 금액으로 가볍게 즐깁니다.\n"
            "🔮 사주/운세: 생년월일과 시간으로 재미용 운세를 봅니다.\n"
            "🎮 팀짜기/소환: 음성채널 인원을 나누거나 이동시킵니다.\n"
            "📋 검사/공지: 운영자를 위한 관리 기능입니다.",
            ephemeral=True
        )

    @discord.ui.button(label="TTS 사용법", style=discord.ButtonStyle.primary)
    async def tts(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "🎧 **TTS 사용법**\n\n"
            "1. 음성채널에 먼저 접속\n"
            "2. `/토끼tts등록 목소리` 사용\n"
            "3. 채팅을 입력하면 봇이 읽어줍니다\n"
            "4. 종료할 때는 `/토끼tts퇴장`\n\n"
            "목소리: 여자1 / 남자1 / 남자2\n"
            "속도 설정: `/토끼tts속도 값`\n"
            "예: `/토끼tts속도 10`, `/토끼tts속도 -10`, `/토끼tts속도 0`\n"
            "상태 확인: `/토끼tts상태`\n"
            "운영자 종료: `/토끼tts강제종료`",
            ephemeral=True
        )

    @discord.ui.button(label="도박 안내", style=discord.ButtonStyle.success)
    async def gamble_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "🎲 **도박 안내**\n\n"
            "`/도박 배팅금액` - 가상 금액으로 도박\n"
            "`/도박잔액` - 내 잔액과 전적 확인\n"
            "`/도박명예의전당` - 잔액 랭킹 확인\n\n"
            "매일 한국시간 기준 기본금 500원이 지급됩니다.\n"
            "기본금은 누적되지 않고, 도박 수익금은 유지됩니다.\n"
            "실제 돈이 아닌 서버 내 재미용 가상 금액입니다.",
            ephemeral=True
        )

    @discord.ui.button(label="사주/운세", style=discord.ButtonStyle.secondary)
    async def saju_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "🔮 **사주/운세 안내**\n\n"
            "`/사주운세 생년월일 태어난시간`\n"
            "- 짧은 오늘 운세를 봅니다.\n\n"
            "`/사주풀이 생년월일 태어난시간`\n"
            "- 성향, 오행, 재물운, 관계운, 승부운을 자세히 봅니다.\n\n"
            "예시: `/사주풀이 2000-01-23 14:30`\n"
            "개인정보는 저장하지 않고, 실행할 때만 계산합니다.",
            ephemeral=True
        )

    @discord.ui.button(label="후원", style=discord.ButtonStyle.danger)
    async def donate(self, interaction: discord.Interaction, button: discord.ui.Button):
        msg = (
            "💛 **토끼봇 후원하기**\n\n"
            "봇 운영과 서버 유지에 도움이 됩니다.\n"
            "후원은 선택이며, 항상 감사합니다!"
        )

        if os.path.exists(DONATION_QR_FILE):
            await interaction.response.send_message(
                msg,
                file=discord.File(DONATION_QR_FILE),
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                msg + "\n\n"
                f"⚠️ 후원 QR 이미지 파일이 아직 서버에 없습니다.\n"
                f"`{DONATION_QR_FILE}` 파일을 `bot.py`와 같은 위치에 올려주세요.",
                ephemeral=True
            )


# ======================================================
# 🤖 팀짜기
# ======================================================
@bot.tree.command(name="팀짜기", guild=GUILD_OBJ)
async def team(interaction: discord.Interaction, size: int):

    members, vc = get_voice_members(interaction)

    if not members:
        await interaction.response.send_message("❌ 음성채널 없음")
        return

    if size < 1:
        await interaction.response.send_message("❌ 팀 인원은 1명 이상이어야 합니다.", ephemeral=True)
        return

    if size > len(members):
        await interaction.response.send_message(
            f"❌ 현재 음성채널 인원은 {len(members)}명입니다. 팀 인원을 더 작게 입력해주세요.",
            ephemeral=True
        )
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

    if not await check_permission(interaction):
        return await interaction.response.send_message("❌ 권한 없음", ephemeral=True)

    voice_members = [
        m for m in interaction.guild.members
        if m.voice and m.voice.channel and not m.bot
    ]

    if not voice_members:
        return await interaction.response.send_message(
            "❌ 현재 음성채널에 소환할 유저가 없습니다.",
            ephemeral=True
        )

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

    if not await check_permission(interaction):
        return await interaction.response.send_message("❌ 권한 없음", ephemeral=True)

    if not interaction.user.voice:
        return await interaction.response.send_message("❌ 음성채널 없음", ephemeral=True)

    await interaction.response.send_message(
        "채널 선택",
        view=SummonChannelView(),
        ephemeral=True
    )

async def ensure_tts_session(guild: discord.Guild, channel: discord.VoiceChannel):

    session = tts_sessions.get(guild.id)

    if session:
        vc = session.get("vc")

        if vc and vc.is_connected():
            return session

        else:
            try:
                session["queue"].put_nowait(None)
            except:
                pass

            tts_sessions.pop(guild.id, None)

    # 세션 생성
    if guild.id not in tts_sessions:

        vc = await channel.connect()

        # 🎧 헤드폰 끄기 (Self Deaf)
        try:
            await guild.change_voice_state(
                channel=channel,
                self_deaf=True
            )
        except Exception as e:
            print("Self Deaf 설정 실패:", e)

        tts_sessions[guild.id] = {
            "vc": vc,
            "channel_id": channel.id,
            "users": {},
            "rates": {},
            "queue": asyncio.Queue(),
            "task": asyncio.create_task(
                tts_worker(guild.id)
            )
        }

    return tts_sessions[guild.id]


@bot.tree.command(name="토끼tts입장", guild=GUILD_OBJ)
async def tts_join(interaction: discord.Interaction):

    if not interaction.user.voice:
        return await interaction.response.send_message(
            "❌ 음성채널에 먼저 접속해주세요",
            ephemeral=True
        )

    await ensure_tts_session(
        interaction.guild,
        interaction.user.voice.channel
    )

    await interaction.response.send_message(
        "🎧 TTS 세션 활성화됨\n"
        "👉 `/토끼tts등록 목소리`로 등록할 수 있습니다."
    )

@bot.tree.command(name="토끼tts등록", guild=GUILD_OBJ)
async def tts_register(
    interaction: discord.Interaction,
    목소리: Literal["여자1", "남자1", "남자2"]
):

    if not interaction.user.voice:
        return await interaction.response.send_message(
            "❌ 음성채널에 먼저 접속해주세요",
            ephemeral=True
        )

    session = await ensure_tts_session(
        interaction.guild,
        interaction.user.voice.channel
    )

    voice_name = VOICE_OPTIONS[목소리]
    already_registered = interaction.user.id in session["users"]

    session["users"][interaction.user.id] = voice_name
    session.setdefault("rates", {}).setdefault(interaction.user.id, "+0%")

    if already_registered:
        await interaction.response.send_message(
            f"🎤 목소리 변경 완료: {VOICE_NAMES[voice_name]}",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"🎤 등록 완료: {VOICE_NAMES[voice_name]}"
        )


@bot.tree.command(name="토끼tts속도", guild=GUILD_OBJ)
async def tts_rate(interaction: discord.Interaction, 속도: int):

    if 속도 < -30 or 속도 > 30:
        return await interaction.response.send_message(
            "❌ 속도는 -30부터 30까지만 설정할 수 있습니다.\n"
            "예: `/토끼tts속도 10`, `/토끼tts속도 -10`, `/토끼tts속도 0`",
            ephemeral=True
        )

    session = tts_sessions.get(interaction.guild.id)

    if not session or interaction.user.id not in session["users"]:
        return await interaction.response.send_message(
            "❌ 먼저 `/토끼tts등록 목소리`로 TTS에 등록해주세요.",
            ephemeral=True
        )

    rate = f"{속도:+d}%"
    session.setdefault("rates", {})[interaction.user.id] = rate

    await interaction.response.send_message(
        f"🎚️ TTS 읽는 속도를 `{rate}`로 설정했습니다.",
        ephemeral=True
    )


@bot.tree.command(name="토끼tts퇴장", guild=GUILD_OBJ)
async def tts_leave(interaction: discord.Interaction):

    guild_id = interaction.guild.id

    session = tts_sessions.get(guild_id)

    if not session:
        return await interaction.response.send_message(
            "❌ TTS 세션이 없습니다. /토끼tts등록 목소리로 먼저 시작해주세요",
            ephemeral=True
        )

    user_id = interaction.user.id

    # 등록 안된 사람
    if user_id not in session["users"]:
        return await interaction.response.send_message(
            "❌ 등록된 사용자가 아닙니다",
            ephemeral=True
        )

    # 유저 제거
    session["users"].pop(user_id, None)
    session.setdefault("rates", {}).pop(user_id, None)

    remaining = len(session["users"])

    # 마지막 사용자 → 세션 종료
    if remaining == 0:

        vc = session.get("vc")

        try:
            if vc and vc.is_connected():
                await vc.disconnect()
        except Exception:
            pass

        # worker 종료 신호
        try:
            session["queue"].put_nowait(None)
        except Exception:
            pass

        tts_sessions.pop(guild_id, None)

        return await interaction.response.send_message(
            "🔇 마지막 사용자가 퇴장했습니다.\n"
            "🛑 TTS 세션이 자동 종료되었습니다."
        )

    await interaction.response.send_message(
        f"🔇 TTS 등록 해제 완료\n"
        f"👥 현재 등록자: {remaining}명"
    )

@bot.tree.command(name="토끼tts상태", guild=GUILD_OBJ)
async def tts_status(interaction: discord.Interaction):

    session = tts_sessions.get(interaction.guild.id)

    if not session:
        return await interaction.response.send_message(
            "❌ 현재 활성화된 TTS 세션이 없습니다.",
            ephemeral=True
        )

    vc = session.get("vc")
    channel = vc.channel if vc and vc.channel else None
    users = session.get("users", {})
    rates = session.setdefault("rates", {})
    queue = session.get("queue")

    msg = "🎧 **토끼 TTS 상태**\n\n"
    msg += f"📍 음성채널: {channel.mention if channel else '알 수 없음'}\n"
    msg += f"👥 등록자: {len(users)}명\n"
    msg += f"🗣️ 대기 중인 문장: {queue.qsize() if queue else 0}개\n"

    if users:
        msg += "\n**등록자 목록**\n"
        for user_id, voice_name in users.items():
            member = interaction.guild.get_member(user_id)
            name = member.mention if member else f"`{user_id}`"
            msg += (
                f"• {name}: {VOICE_NAMES.get(voice_name, voice_name)} "
                f"/ 속도 {rates.get(user_id, '+0%')}\n"
            )
    else:
        msg += "\n등록된 사용자가 없습니다.\n"

    await interaction.response.send_message(
        msg,
        ephemeral=True,
        allowed_mentions=discord.AllowedMentions(users=True)
    )

@bot.tree.command(name="토끼tts강제종료", guild=GUILD_OBJ)
async def tts_force_stop(interaction: discord.Interaction):

    if not await check_permission(interaction):
        return await interaction.response.send_message(
            "❌ 권한 없음",
            ephemeral=True
        )

    session = tts_sessions.get(interaction.guild.id)

    if not session:
        return await interaction.response.send_message(
            "❌ 현재 활성화된 TTS 세션이 없습니다.",
            ephemeral=True
        )

    vc = session.get("vc")

    try:
        if vc and vc.is_playing():
            vc.stop()
    except Exception:
        pass

    try:
        if vc and vc.is_connected():
            await vc.disconnect()
    except Exception as e:
        print("TTS 강제종료 음성 연결 해제 실패:", e)

    try:
        session["queue"].put_nowait(None)
    except Exception:
        pass

    tts_sessions.pop(interaction.guild.id, None)

    await interaction.response.send_message(
        "🛑 TTS 세션을 강제 종료했습니다."
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

@bot.tree.command(name="토끼봇도움말", guild=GUILD_OBJ)
async def rabbit_bot_help(interaction: discord.Interaction):
    await interaction.response.send_message(
        "🐰 **토끼봇 도움말**\n\n"
        "아래 버튼을 눌러 필요한 안내를 확인하세요.",
        view=RabbitBotHelpView()
    )


# ======================================================
# 🎲 도박
# ======================================================
@bot.tree.command(name="도박", guild=GUILD_OBJ)
async def gamble(interaction: discord.Interaction, 배팅금액: int):

    if 배팅금액 <= 0:
        return await interaction.response.send_message(
            "❌ 배팅금액은 1원 이상이어야 합니다.",
            ephemeral=True
        )

    await interaction.response.defer()

    async with gamble_lock:
        data = load_gamble_data()
        account = get_gamble_account(data, interaction.user.id)
        balance = get_gamble_balance(account)

        if 배팅금액 > balance:
            return await interaction.followup.send(
                f"❌ 잔액이 부족합니다. 현재 잔액: {balance:,}원",
                ephemeral=True
            )

        win = random.random() < GAMBLE_WIN_RATE

        if win:
            account["profit"] = int(account.get("profit", 0)) + 배팅금액
            account["wins"] = int(account.get("wins", 0)) + 1
            flavor = random.choice(GAMBLE_WIN_MESSAGES)
            result_msg = (
                f"🎲 **도박 결과: 승리!**\n"
                f"{flavor}\n\n"
                f"👤 도전자: {interaction.user.mention}\n"
                f"💵 배팅금액: {배팅금액:,}원\n"
                f"💰 획득금액: +{배팅금액:,}원"
            )
        else:
            subtract_gamble_balance(account, 배팅금액)
            account["losses"] = int(account.get("losses", 0)) + 1
            flavor = random.choice(GAMBLE_LOSE_MESSAGES)
            result_msg = (
                f"🎲 **도박 결과: 실패...**\n"
                f"{flavor}\n\n"
                f"👤 도전자: {interaction.user.mention}\n"
                f"💵 배팅금액: {배팅금액:,}원\n"
                f"💸 손실금액: -{배팅금액:,}원"
            )

        new_balance = get_gamble_balance(account)
        save_gamble_data(data)

    await interaction.followup.send(
        f"{result_msg}\n"
        f"🏦 현재 잔액: **{new_balance:,}원**",
        allowed_mentions=discord.AllowedMentions(users=True)
    )


@bot.tree.command(name="도박잔액", guild=GUILD_OBJ)
async def gamble_balance(interaction: discord.Interaction):

    await interaction.response.defer(ephemeral=True)

    async with gamble_lock:
        data = load_gamble_data()
        account = get_gamble_account(data, interaction.user.id)
        balance = get_gamble_balance(account)
        save_gamble_data(data)

    await interaction.followup.send(
        f"🏦 {interaction.user.mention}님의 도박 잔액\n"
        f"💰 총 잔액: {balance:,}원\n"
        f"🎁 오늘 기본금: {int(account.get('daily_bonus', 0)):,}원\n"
        f"📈 도박 수익금: {int(account.get('profit', 0)):,}원\n"
        f"🎯 전적: {int(account.get('wins', 0))}승 {int(account.get('losses', 0))}패",
        ephemeral=True
    )


@bot.tree.command(name="도박명예의전당", guild=GUILD_OBJ)
async def gamble_hall_of_fame(interaction: discord.Interaction):

    await interaction.response.defer()

    async with gamble_lock:
        data = load_gamble_data()

        entries = []
        for user_id, account in data.get("users", {}).items():
            account = get_gamble_account(data, int(user_id))
            entries.append(
                (
                    int(user_id),
                    get_gamble_balance(account),
                    int(account.get("profit", 0)),
                    int(account.get("wins", 0)),
                    int(account.get("losses", 0))
                )
            )

        save_gamble_data(data)

    entries.sort(key=lambda item: item[1], reverse=True)
    day_key = get_current_day_key()

    if not entries:
        return await interaction.followup.send(
            f"🏆 **도박 명예의전당 ({day_key})**\n\n아직 기록이 없습니다."
        )

    msg = f"🏆 **도박 명예의전당 ({day_key})**\n\n"

    for rank, (user_id, balance, profit, wins, losses) in enumerate(entries[:10], 1):
        member = interaction.guild.get_member(user_id)
        name = member.mention if member else f"`{user_id}`"
        msg += (
            f"{rank}. {name} - {balance:,}원 "
            f"(수익금 {profit:,}원, {wins}승 {losses}패)\n"
        )

    await interaction.followup.send(
        msg,
        allowed_mentions=discord.AllowedMentions(users=True)
    )


# ======================================================
# 🔮 사주운세
# ======================================================
@bot.tree.command(name="사주운세", guild=GUILD_OBJ)
async def saju_fortune(
    interaction: discord.Interaction,
    생년월일: str,
    태어난시간: str
):

    birth_date = parse_birth_date(생년월일)
    birth_time = parse_birth_time(태어난시간)

    if not birth_date:
        return await interaction.response.send_message(
            "❌ 생년월일은 `YYYY-MM-DD` 또는 `YYYYMMDD` 형식으로 입력해주세요.\n"
            "예: `/사주운세 2000-01-23 14:30`",
            ephemeral=True
        )

    if not birth_time:
        return await interaction.response.send_message(
            "❌ 태어난시간은 `HH:MM`, `HHMM`, 또는 `시` 형식으로 입력해주세요.\n"
            "예: `14:30`, `1430`, `14`",
            ephemeral=True
        )

    await interaction.response.defer()

    try:
        msg = build_saju_summary(
            interaction.user.id,
            birth_date,
            birth_time
        )
    except ModuleNotFoundError:
        return await interaction.followup.send(
            "❌ 사주 계산 라이브러리가 설치되어 있지 않습니다.\n"
            "서버에서 아래 명령어를 한 번 실행해주세요.\n"
            "`pip install lunar_python`",
            ephemeral=True
        )
    except Exception as e:
        print("사주운세 오류:", e)
        traceback.print_exc()
        return await interaction.followup.send(
            f"❌ 사주운세 계산 중 오류가 발생했습니다.\n`{e}`",
            ephemeral=True
        )

    await interaction.followup.send(msg)


@bot.tree.command(name="사주풀이", guild=GUILD_OBJ)
async def saju_reading(
    interaction: discord.Interaction,
    생년월일: str,
    태어난시간: str
):

    birth_date = parse_birth_date(생년월일)
    birth_time = parse_birth_time(태어난시간)

    if not birth_date:
        return await interaction.response.send_message(
            "❌ 생년월일은 `YYYY-MM-DD` 또는 `YYYYMMDD` 형식으로 입력해주세요.\n"
            "예: `/사주풀이 2000-01-23 14:30`",
            ephemeral=True
        )

    if not birth_time:
        return await interaction.response.send_message(
            "❌ 태어난시간은 `HH:MM`, `HHMM`, 또는 `시` 형식으로 입력해주세요.\n"
            "예: `14:30`, `1430`, `14`",
            ephemeral=True
        )

    await interaction.response.defer()

    try:
        msg = build_saju_reading(
            interaction.user.id,
            birth_date,
            birth_time
        )
    except ModuleNotFoundError:
        return await interaction.followup.send(
            "❌ 사주 계산 라이브러리가 설치되어 있지 않습니다.\n"
            "서버에서 아래 명령어를 한 번 실행해주세요.\n"
            "`pip install lunar_python`",
            ephemeral=True
        )
    except Exception as e:
        print("사주풀이 오류:", e)
        traceback.print_exc()
        return await interaction.followup.send(
            f"❌ 사주풀이 계산 중 오류가 발생했습니다.\n`{e}`",
            ephemeral=True
        )

    if len(msg) <= 1900:
        await interaction.followup.send(msg)
        return

    parts = msg.split("\n\n")
    chunk = ""

    for part in parts:
        next_chunk = f"{chunk}\n\n{part}" if chunk else part

        if len(next_chunk) > 1900:
            await interaction.followup.send(chunk)
            chunk = part
        else:
            chunk = next_chunk

    if chunk:
        await interaction.followup.send(chunk)


# ======================================================
# 🎯 닉네임 검사
# ======================================================
def is_valid_nick(nick: str) -> bool:

    # 게스트는 검사 제외
    if "게스트" in nick:
        return True

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
        return await interaction.response.send_message(
            "❌ 권한 없음",
            ephemeral=True
        )

    await interaction.response.defer()

    invalid = []
    guests = []

    for m in interaction.guild.members:
        if m.bot:
            continue

        nick = m.nick or m.name

        # 게스트 목록 수집
        if "게스트" in nick:
            guests.append(m)
            continue

        if not is_valid_nick(nick):
            invalid.append(m)

    msg = ""

    # 오류 사용자
    if invalid:
        msg += "⚠️ 닉네임 오류 사용자 목록\n\n"

        for m in invalid[:50]:
            msg += f"• {m.mention} ({m.nick or m.name})\n"
    else:
        msg += "✅ 닉네임 형식 오류 없음\n"

    # 게스트 목록
    if guests:
        msg += "\n\n🎟️ 게스트 목록\n\n"

        for m in guests[:50]:
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
    rate = session.setdefault("rates", {}).get(message.author.id, "+0%")

    await session["queue"].put((text, voice_name, rate))

    try:
        await message.delete()
    except:
        pass
# ======================================================
# 🎤 등록 사용자 자동 해제
# ======================================================
@bot.event
async def on_voice_state_update(member, before, after):

    session = tts_sessions.get(member.guild.id)

    if not session:
        return

    vc = session.get("vc")

    if not vc or not vc.channel:
        return

    # 등록자가 아니면 무시
    if member.id not in session["users"]:
        return

    # 토끼봇이 있는 채널을 떠난 경우
    # (다른 채널 이동 / 연결 끊김 모두 포함)
    if before.channel == vc.channel and after.channel != vc.channel:

        session["users"].pop(member.id, None)
        session.setdefault("rates", {}).pop(member.id, None)

        print(
            f"[TTS] 자동 등록 해제: "
            f"{member.display_name} ({member.id})"
        )

        remaining = len(session["users"])

        print(
            f"[TTS] 남은 등록자: {remaining}명"
        )

        # 등록자 전부 사라짐
        if remaining == 0:

            print(
                f"[TTS] 등록자 없음 → 세션 종료 시작 "
                f"(Guild: {member.guild.name})"
            )

            try:
                session["queue"].put_nowait(None)
                print("[TTS] Worker 종료 신호 전송")
            except Exception as e:
                print(f"[TTS] Queue 종료 신호 실패: {e}")

            try:
                await vc.disconnect()
                print("[TTS] 음성채널 연결 해제")
            except Exception as e:
                print(f"[TTS] 음성채널 해제 실패: {e}")

            tts_sessions.pop(member.guild.id, None)

            print(
                f"[TTS] 세션 삭제 완료 "
                f"(Guild: {member.guild.name})"
            )
    
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
