import discord
from discord.ext import commands
import edge_tts
import asyncio
import os
import time
import re  # [추가] 초성을 찾아서 바꿔주기 위해 필요해!

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

# [핵심] 여러 명이 말할 때 씹히지 않게 차례대로 줄 세우는 도구
play_lock = asyncio.Lock()

# [기능 추가] 초성 및 단어를 한글 발음으로 바꿔주는 함수
def clean_text(text):
    # 1. 단어 통째로 바꾸기 (ㄹㅇ, ㅇㄷ, ㅇㅋ 등)
    # 뒤에 공백을 살짝 넣어서 단어끼리 붙어있어도 잘 인식하게 했어
    text = text.replace("ㄹㅇ", " 레알 ").replace("ㅇㄷ", " 어디 ").replace("ㅇㅋ", " 오키 ")
    text = text.replace("ㄱㄱ", " 고고 ").replace("ㅂㅇ", " 바이 ").replace("ㅎㅇ", " 하이 ")
    text = text.replace("ㅎㄷㄷ", " 후덜덜 ").replace("ㅁㅎ", " 뭐해 ")

    # 2. 한 글자씩 반복되는 초성 처리 (ㅋㅋㅋㅋ -> 크크크크)
    # 정규식 패턴을 더 꼼꼼하게 잡았어
    dic = {
        "ㅋ": "크", "ㅎ": "흐", "ㅠ": "유", "ㅜ": "우", 
        "ㅅ": "시옷", "ㄴ": "노", "ㅇ": "응", "ㄷ": "덜"
    }
    
    for char, sound in dic.items():
        # r'[char]+' 패턴으로 해당 글자가 연속될 때 모두 찾아서 발음으로 바꿔줘
        text = re.sub(f'{char}+', lambda m: sound * len(m.group()), 4), text)
    
    # 마지막으로 앞뒤 불필요한 공백만 정리
    return text.strip()

# 목소리 파일 생성 함수 (초성 변환 기능 포함)
async def make_voice(text):
    # [수정] 말하기 전에 글자를 먼저 깨끗하게 바꿈!
    processed_text = clean_text(text)
    
    fname = f"voice_{int(time.time() * 1000)}.mp3"
    communicate = edge_tts.Communicate(processed_text, "ko-KR-SunHiNeural")
    await communicate.save(fname)
    return fname

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"--- {bot.user.name} 가동 시작! (입퇴장 알림 + 초성 변환 모드) ---")

# [기능] 입장/퇴장 감지 알림 & 사람이 없으면 자동 퇴장
@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot: return

    vc = member.guild.voice_client
    if not vc: return

    # 1. 누군가 봇이 있는 채널로 들어왔을 때 (입장 알림)
    if before.channel != after.channel and after.channel == vc.channel:
        async with play_lock: 
            text = f"{member.display_name}님이 들어오셨어요. 반가워요!"
            current_file = await make_voice(text)
            while vc.is_playing(): await asyncio.sleep(0.2)
            if os.path.exists(current_file):
                vc.play(discord.FFmpegPCMAudio(current_file), after=lambda e: os.remove(current_file) if os.path.exists(current_file) else None)
                while vc.is_playing(): await asyncio.sleep(0.1)

    # 2. 누군가 채널에서 나갔을 때 (퇴장 알림 & 자동 퇴장 체크)
    elif before.channel == vc.channel and after.channel != vc.channel:
        remaining_members = [m for m in vc.channel.members if not m.bot]
        
        if not remaining_members: 
            await asyncio.sleep(1)
            await vc.disconnect()
            print(f"[{member.guild.name}] 빈 채널이라 자동 퇴장함.")
        else: 
            async with play_lock:
                text = f"{member.display_name}님이 나가셨어요."
                current_file = await make_voice(text)
                while vc.is_playing(): await asyncio.sleep(0.2)
                if os.path.exists(current_file):
                    vc.play(discord.FFmpegPCMAudio(current_file), after=lambda e: os.remove(current_file) if os.path.exists(current_file) else None)
                    while vc.is_playing(): await asyncio.sleep(0.1)

# [기능] 채팅 치면 자동 입장 및 읽어주기
@bot.event
async def on_message(message):
    if message.author.bot: return
    
    if message.author.voice:
        vc = message.guild.voice_client
        
        if not vc:
            vc = await message.author.voice.channel.connect()
        elif vc.channel != message.author.voice.channel:
            await vc.move_to(message.author.voice.channel)

        async with play_lock:
            current_file = await make_voice(message.content)
            while vc.is_playing(): await asyncio.sleep(0.2)
            if os.path.exists(current_file):
                vc.play(discord.FFmpegPCMAudio(current_file), after=lambda e: os.remove(current_file) if os.path.exists(current_file) else None)
                while vc.is_playing(): await asyncio.sleep(0.1)

    await bot.process_commands(message)

# 슬래시 명령어
@bot.tree.command(name="들어와", description="봇을 강제로 입장시킵니다")
async def enter(interaction: discord.Interaction):
    if interaction.user.voice:
        await interaction.user.voice.channel.connect()
        await interaction.response.send_message("✅ 입퇴장 감지 및 초성 변환 모드 작동 중!")
    else:
        await interaction.response.send_message("먼저 음성 채널에 들어가줘!", ephemeral=True)

@bot.tree.command(name="나가", description="봇을 퇴장시킵니다")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("👋 수고했어!")

token = os.getenv('DISCORD_TOKEN')
if token:
    bot.run(token)
else:
    print("에러: DISCORD_TOKEN을 찾을 수 없습니다.")
