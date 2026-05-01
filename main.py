import discord
from discord.ext import commands
import edge_tts
import asyncio
import os
import time

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

# 목소리 파일 생성 함수
async def make_voice(text):
    fname = f"voice_{int(time.time())}.mp3"
    communicate = edge_tts.Communicate(text, "ko-KR-SunHiNeural")
    await communicate.save(fname)
    return fname

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"--- {bot.user.name} 가동 시작! (입퇴장 알림 + 자동화 모드) ---")

# [기능] 입장/퇴장 감지 알림 & 사람이 없으면 자동 퇴장
@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot: return

    vc = member.guild.voice_client
    if not vc: return

    # 1. 누군가 봇이 있는 채널로 들어왔을 때 (입장 알림)
    if before.channel != after.channel and after.channel == vc.channel:
        text = f"{member.display_name}님이 들어오셨어요. 반가워요!"
        current_file = await make_voice(text)
        while vc.is_playing(): await asyncio.sleep(0.5)
        vc.play(discord.FFmpegPCMAudio(current_file), after=lambda e: os.remove(current_file) if os.path.exists(current_file) else None)

    # 2. 누군가 채널에서 나갔을 때 (퇴장 알림 & 자동 퇴장 체크)
    elif before.channel == vc.channel and after.channel != vc.channel:
        # 남은 사람이 있는지 확인
        remaining_members = [m for m in vc.channel.members if not m.bot]
        
        if not remaining_members: # 아무도 없으면 자동 퇴장
            await asyncio.sleep(1)
            await vc.disconnect()
            print(f"[{member.guild.name}] 빈 채널이라 자동 퇴장함.")
        else: # 사람이 남아있으면 퇴장 멘트만 출력
            text = f"{member.display_name}님이 나가셨어요."
            current_file = await make_voice(text)
            while vc.is_playing(): await asyncio.sleep(0.5)
            vc.play(discord.FFmpegPCMAudio(current_file), after=lambda e: os.remove(current_file) if os.path.exists(current_file) else None)

# [기능] 채팅 치면 자동 입장 및 읽어주기
@bot.event
async def on_message(message):
    if message.author.bot: return
    
    # 메시지를 보낸 사용자가 음성 채널에 있을 때만 작동
    if message.author.voice:
        vc = message.guild.voice_client
        
        # 봇이 없으면 자동 접속, 있으면 채널 이동
        if not vc:
            vc = await message.author.voice.channel.connect()
        elif vc.channel != message.author.voice.channel:
            await vc.move_to(message.author.voice.channel)

        # 텍스트 읽어주기
        if vc.is_playing(): vc.stop()
        current_file = await make_voice(message.content)
        vc.play(discord.FFmpegPCMAudio(current_file), after=lambda e: os.remove(current_file) if os.path.exists(current_file) else None)

    await bot.process_commands(message)

# 슬래시 명령어
@bot.tree.command(name="들어와", description="봇을 강제로 입장시킵니다")
async def enter(interaction: discord.Interaction):
    if interaction.user.voice:
        await interaction.user.voice.channel.connect()
        await interaction.response.send_message("✅ 입퇴장 감지 및 채팅 읽기 모드 작동 중!")
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
