import discord
from discord.ext import commands
import edge_tts
import asyncio
import os
import time
import re

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

# [핵심] 여러 명이 말할 때 씹히지 않게 차례대로 줄 세우는 도구
play_lock = asyncio.Lock()

# [수정] 텍스트 정화 함수 (디코 이모지, 링크, 태그 처리)
def clean_text(text, guild=None):
    # 1. 주소(http/https) 무시 (움짤 링크 등 방지)
    text = re.sub(r'https?://\S+', '', text)

    # 2. 유저 멘션 처리 (<@!ID> -> 닉네임)
    if guild:
        mentions = re.findall(r'<@!?([0-9]+)>', text)
        for user_id in mentions:
            member = guild.get_member(int(user_id))
            if member:
                nick = member.display_name
                text = text.replace(f'<@{user_id}>', f' {nick} ').replace(f'<@!{user_id}>', f' {nick} ')

    # 3. 디코 전용 커스텀 이모지 (<:name:id> 또는 <a:name:id>)만 "이모지"라고 읽기
    # 휴대폰 기본 이모지는 건드리지 않아!
    if re.search(r'<a?:\w+:\d+>', text):
        text = re.sub(r'<a?:\w+:\d+>', ' 이모지 ', text)

 # 4. 단어 통째로 바꾸기 (긴 단어부터 위로!)
    # 선희가 세 글자 단어를 먼저 찾게 순서를 바꿨어.
    text = text.replace("ㄱㅇㄷ", " 개이득 ") # 이걸 제일 위로!
    text = text.replace("ㅇㅈㄹ", " 이지랄 ")
    text = text.replace("ㅎㄷㄷ", " 후덜덜 ")

    # 그다음 두 글자 단어들 처리
    text = text.replace("ㄹㅇ", " 레알 ").replace("ㅇㄷ", " 어디 ").replace("ㅇㅋ", " 오키 ")
    text = text.replace("ㄱㄱ", " 고고 ").replace("ㅂㅇ", " 바이 ").replace("ㅎㅇ", " 하이 ")
    text = text.replace("ㅁㅎ", " 뭐해 ").replace("ㅈㄴ", " 존나 ").replace("ㅈㄹ", " 지랄 ")
    text = text.replace("ㅇㅈ", " 인정 ").replace("ㅇㅎ", " 아하 ")
    
    # 5. 한 글자씩 반복되는 초성 처리 (최대 4개 제한)
    dic = {
        "ㅋ": "크", "ㅎ": "흐", "ㅠ": "유", "ㅜ": "우", 
        "ㅅ": "샤", "ㄴ": "노", "ㅇ": "응", "ㄷ": "덜"
    }
    
    for char, sound in dic.items():
        text = re.sub(f'{char}+', lambda m: sound * min(len(m.group()), 4), text)
    
    return text.strip()

# 목소리 파일 생성 함수
async def make_voice(text, guild=None):
    processed_text = clean_text(text, guild)
    
    # 읽을 내용이 아예 없으면 패스
    if not processed_text.strip():
        return None

    fname = f"voice_{int(time.time() * 1000)}.mp3"
    communicate = edge_tts.Communicate(processed_text, "ko-KR-SunHiNeural")
    await communicate.save(fname)
    return fname

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"--- {bot.user.name} 가동 시작! (커스텀 이모지 필터 적용) ---")

# [기능] 입장/퇴장 감지 알림 & 사람이 없으면 자동 퇴장
@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot: return
    vc = member.guild.voice_client
    if not vc: return

    if before.channel != after.channel and after.channel == vc.channel:
        async with play_lock: 
            text = f"{member.display_name}님이 들어오셨어요. 반가워요!"
            current_file = await make_voice(text, member.guild)
            if current_file:
                while vc.is_playing(): await asyncio.sleep(0.2)
                vc.play(discord.FFmpegPCMAudio(current_file), after=lambda e: os.remove(current_file) if os.path.exists(current_file) else None)
                while vc.is_playing(): await asyncio.sleep(0.1)

    elif before.channel == vc.channel and after.channel != vc.channel:
        remaining_members = [m for m in vc.channel.members if not m.bot]
        if not remaining_members: 
            await asyncio.sleep(1)
            await vc.disconnect()
            print(f"[{member.guild.name}] 빈 채널이라 자동 퇴장함.")
        else: 
            async with play_lock:
                text = f"{member.display_name}님이 나가셨어요."
                current_file = await make_voice(text, member.guild)
                if current_file:
                    while vc.is_playing(): await asyncio.sleep(0.2)
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
            current_file = await make_voice(message.content, message.guild)
            if current_file:
                while vc.is_playing(): await asyncio.sleep(0.2)
                vc.play(discord.FFmpegPCMAudio(current_file), after=lambda e: os.remove(current_file) if os.path.exists(current_file) else None)
                while vc.is_playing(): await asyncio.sleep(0.1)

    await bot.process_commands(message)

# 슬래시 명령어
@bot.tree.command(name="들어와", description="봇을 강제로 입장시킵니다")
async def enter(interaction: discord.Interaction):
    if interaction.user.voice:
        await interaction.user.voice.channel.connect()
        await interaction.response.send_message("✅ 봇이 가동되었습니다!")
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
