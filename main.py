import discord
from discord.ext import commands
import edge_tts
import asyncio
import os
import time

# 1. 봇 설정 및 인텐트 설정
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

# 2. 목소리 파일 생성 함수 (Edge TTS 선희)
async def make_voice(text):
    fname = f"voice_{int(time.time())}.mp3"
    # Edge TTS를 사용하여 선희(SunHi) 목소리로 저장
    communicate = edge_tts.Communicate(text, "ko-KR-SunHiNeural")
    await communicate.save(fname)
    return fname

@bot.event
async def on_ready():
    await bot.tree.sync()
    print("--- 24시간 입장 감지 선희 봇 가동 중! ---")

# 3. 음성 채널 상태 변화 감지 (입장/퇴장 알림)
@bot.event
async def on_voice_state_update(member, before, after):
    # 봇이 낸 소리는 무시
    if member.bot: return

    # 봇이 연결된 음성 채널 확인
    vc = member.guild.voice_client
    if not vc: return

    # 누군가 봇이 있는 채널로 들어왔을 때
    if before.channel != after.channel and after.channel == vc.channel:
        text = f"{member.display_name}님이 들어오셨어요. 반가워요!"
        current_file = await make_voice(text)
        
        while vc.is_playing(): # 이미 재생 중이면 잠시 대기
            await asyncio.sleep(0.5)
            
        vc.play(discord.FFmpegPCMAudio(current_file), after=lambda e: os.remove(current_file) if os.path.exists(current_file) else None)

    # 누군가 채널에서 나갔을 때
    elif before.channel == vc.channel and after.channel != vc.channel:
        text = f"{member.display_name}님이 나가셨어요."
        current_file = await make_voice(text)
        
        while vc.is_playing():
            await asyncio.sleep(0.5)
            
        vc.play(discord.FFmpegPCMAudio(current_file), after=lambda e: os.remove(current_file) if os.path.exists(current_file) else None)

# 4. 채팅 읽어주기 기능
@bot.event
async def on_message(message):
    if message.author.bot: return
    vc = message.guild.voice_client
    if vc and vc.is_connected():
        if vc.is_playing(): vc.stop()
        current_file = await make_voice(message.content)
        vc.play(discord.FFmpegPCMAudio(current_file), after=lambda e: os.remove(current_file) if os.path.exists(current_file) else None)

# 5. 슬래시 명령어
@bot.tree.command(name="들어와", description="음성 채널에 입장 시킵니다")
async def enter(interaction: discord.Interaction):
    if interaction.user.voice:
        await interaction.user.voice.channel.connect()
        await interaction.response.send_message("✅ 입장 감지 모드 시작! 누구 들어오면 내가 알려줄게.")
    else:
        await interaction.response.send_message("음성 채널에 먼저 들어가줘!", ephemeral=True)

@bot.tree.command(name="나가", description="봇을 내보냅니다")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("👋 고생했어!")

# 6. 실행 부분 (깃허브 Secrets에 저장된 토큰을 사용)
# 깃허브 저장소 Settings -> Secrets -> Actions에 DISCORD_TOKEN을 등록해야 합니다.
token = os.getenv('DISCORD_TOKEN')

if token:
    bot.run(token)
else:
    print("에러: DISCORD_TOKEN 환경 변수를 찾을 수 없습니다. 깃허브 설정을 확인하세요.")
