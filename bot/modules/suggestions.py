import discord
from discord.ext import commands
from shared.db import settings, execute, now, log
class Suggestions(commands.Cog):
 def __init__(self,bot): self.bot=bot
 @commands.Cog.listener()
 async def on_message(self,message):
  if message.author.bot or not message.guild: return
  cfg=await settings(); ch=int(cfg.get('suggestion_channel_id','0') or 0)
  if message.channel.id != ch: return
  content=message.content.strip(); att=[a.url for a in message.attachments]
  if att: content+='\n\n'+'\n'.join(att)
  if not content: return
  sid=await execute('INSERT INTO suggestions (discord_id,discord_name,content,status,created_at,updated_at) VALUES (?,?,?,?,?,?)',(str(message.author.id),str(message.author),content,'analysis',now(),now()))
  embed=discord.Embed(title=f'💡 Nova Sugestão #{sid}',description=content,color=discord.Color.blurple()); embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
  sent=await message.channel.send(embed=embed); await sent.add_reaction('✅'); await sent.add_reaction('❌')
  try:
   th=await sent.create_thread(name=f'Sugestão #{sid}', auto_archive_duration=1440); await th.send(f'Discussão da sugestão de {message.author.mention}')
  except Exception: pass
  await execute('UPDATE suggestions SET message_id=? WHERE id=?',(str(sent.id),sid)); await log('suggestion_created', {'id':sid,'user':message.author.id})
  try: await message.delete()
  except discord.Forbidden: pass
async def setup(bot): await bot.add_cog(Suggestions(bot))
