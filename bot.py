import os
import random
import discord
import json
import asyncio
import yt_dlp
from discord.ext import commands, tasks
from dotenv import load_dotenv
import requests
from datetime import datetime, timedelta
from dateutil import parser

# Configuration yt-dlp
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

# Configuration FFmpeg
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
    'executable': 'C:\\ffmpeg\\bin\\ffmpeg.exe'  # Spécifiez le chemin complet vers ffmpeg.exe
}


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None):
        loop = loop or asyncio.get_event_loop()
        ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)
        
        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
            
            if 'entries' in data:
                data = data['entries'][0]
                
            filename = data['url']
            return cls(discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS), data=data)
        except Exception as e:
            print(f"Erreur lors de l'extraction: {str(e)}")
            raise e

# Charger les variables d'environnement
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Configuration du bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Système de niveaux
levels = {}
try:
    with open('levels.json', 'r') as f:
        levels = json.load(f)
except FileNotFoundError:
    pass

# Système de rappels
reminders = []

# Commandes de musique
class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = {}

    @commands.command(name='join', help='Fait rejoindre le bot dans votre salon vocal')
    async def join(self, ctx):
        if not ctx.author.voice:
            await ctx.send("Tu dois être dans un salon vocal!")
            return

        channel = ctx.author.voice.channel
        if ctx.voice_client is not None:
            await ctx.voice_client.move_to(channel)
        else:
            await channel.connect()
        await ctx.send(f"Connecté à {channel.name}")

    @commands.command(name='play', help='Joue une musique (!play <url ou recherche>)')
    async def play(self, ctx, *, query):
        if not ctx.voice_client:
            await ctx.invoke(self.join)

        async with ctx.typing():
            try:
                # Si ce n'est pas une URL YouTube, on fait une recherche
                if not query.startswith(('https://', 'http://')):
                    query = f"ytsearch:{query}"

                player = await YTDLSource.from_url(query, loop=self.bot.loop)
                ctx.voice_client.play(player, after=lambda e: print(f'Erreur de lecture: {e}') if e else None)
                await ctx.send(f' En train de jouer: {player.title}')
            except Exception as e:
                await ctx.send(f"Une erreur s'est produite: {str(e)}")

    @commands.command(name='stop', help='Arrête la musique')
    async def stop(self, ctx):
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await ctx.send("Musique arrêtée et déconnecté du salon vocal")
        else:
            await ctx.send("Je ne suis pas dans un salon vocal!")

    @commands.command(name='pause', help='Met en pause la musique')
    async def pause(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send(" Musique mise en pause")
        else:
            await ctx.send("Aucune musique n'est en cours de lecture")

    @commands.command(name='resume', help='Reprend la lecture de la musique')
    async def resume(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send(" Reprise de la lecture")
        else:
            await ctx.send("La musique n'est pas en pause")

    @commands.command(name='volume', help='Change le volume (0-100)')
    async def volume(self, ctx, volume: int):
        if not ctx.voice_client:
            return await ctx.send("Je ne suis pas connecté à un salon vocal.")
        
        if 0 <= volume <= 100:
            ctx.voice_client.source.volume = volume / 100
            await ctx.send(f"Volume réglé à {volume}%")
        else:
            await ctx.send("Le volume doit être entre 0 et 100")

# Événement: Bot prêt
@bot.event
async def on_ready():
    print(f'{bot.user} est connecté et prêt!')
    await bot.change_presence(activity=discord.Game(name="!help pour de l'aide"))
    check_reminders.start()
    await bot.add_cog(Music(bot))

# Commande: Ping
@bot.command(name='ping', help='Vérifie si le bot répond')
async def ping(ctx):
    await ctx.send(f'Pong! Latence: {round(bot.latency * 1000)}ms')

# Commande: Dé
@bot.command(name='dice', help='Lance un dé (nombre de faces optionnel)')
async def dice(ctx, faces: int = 6):
    result = random.randint(1, faces)
    await ctx.send(f' Le dé à {faces} faces donne: {result}')

# Commande: Répéter
@bot.command(name='say', help='Répète le message donné')
async def say(ctx, *, message):
    try:
        await ctx.message.delete()
    except discord.errors.Forbidden:
        pass  # Ignorer si le bot n'a pas la permission de supprimer
    
    await ctx.send(message)

# Commande: Clear
@bot.command(name='clear', help='Supprime un nombre spécifié de messages')
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int):
    await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f'{amount} messages ont été supprimés!', delete_after=5)

# Commande: Kick
@bot.command(name='kick', help='Expulse un membre')
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason=None):
    await member.kick(reason=reason)
    await ctx.send(f'{member.mention} a été expulsé. Raison: {reason}')

# Commande: Blague
@bot.command(name='joke', help='Affiche une blague aléatoire')
async def joke(ctx):
    response = requests.get('https://v2.jokeapi.dev/joke/Any?lang=fr&safe=true')
    if response.status_code == 200:
        joke_data = response.json()
        if joke_data['type'] == 'single':
            await ctx.send(joke_data['joke'])
        else:
            await ctx.send(f"{joke_data['setup']}\n||{joke_data['delivery']}||")
    else:
        await ctx.send("Désolé, je n'ai pas pu récupérer de blague...")

# Événement: Nouveau membre
@bot.event
async def on_member_join(member):
    channel = member.guild.system_channel
    if channel:
        await channel.send(f'Bienvenue {member.mention} sur le serveur! ')

# Événement: Membre part
@bot.event
async def on_member_remove(member):
    channel = member.guild.system_channel
    if channel:
        await channel.send(f'Au revoir {member.name}... ')

# Gestion des erreurs
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.errors.MissingPermissions):
        await ctx.send("Vous n'avez pas les permissions nécessaires pour cette commande.")
    elif isinstance(error, commands.errors.MissingRequiredArgument):
        await ctx.send("Il manque un argument requis pour cette commande.")
    else:
        await ctx.send(f"Une erreur s'est produite: {str(error)}")

# Système de niveaux
@bot.event
async def on_message(message):
    if not message.author.bot:
        user_id = str(message.author.id)
        if user_id not in levels:
            levels[user_id] = {"xp": 0, "level": 1}
        
        levels[user_id]["xp"] += random.randint(5, 15)
        xp = levels[user_id]["xp"]
        lvl = levels[user_id]["level"]
        
        if xp >= lvl * 100:
            levels[user_id]["level"] += 1
            await message.channel.send(f' Félicitations {message.author.mention}! Tu as atteint le niveau {lvl + 1}!')
        
        with open('levels.json', 'w') as f:
            json.dump(levels, f)
    
    await bot.process_commands(message)

@bot.command(name='level', help='Affiche ton niveau actuel')
async def level(ctx):
    user_id = str(ctx.author.id)
    if user_id in levels:
        xp = levels[user_id]["xp"]
        lvl = levels[user_id]["level"]
        await ctx.send(f'Niveau: {lvl} | XP: {xp}/{lvl * 100}')
    else:
        await ctx.send("Tu n'as pas encore de niveau!")

# Système de sondage
@bot.command(name='poll', help='Crée un sondage (!poll "question" "option1" "option2" ...)')
async def poll(ctx, question, *options):
    if len(options) < 2:
        await ctx.send("Il faut au moins 2 options pour créer un sondage!")
        return
    
    if len(options) > 10:
        await ctx.send("Vous ne pouvez pas avoir plus de 10 options dans un sondage.")
        return

    emoji_numbers = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']

    description = []
    for i, option in enumerate(options):
        description.append(f'{emoji_numbers[i]} {option}')

    embed = discord.Embed(
        title=question,
        description='\n'.join(description),
        color=discord.Color.blue()
    )
    poll_msg = await ctx.send(embed=embed)

    # Ajouter les réactions
    for i in range(len(options)):
        await poll_msg.add_reaction(emoji_numbers[i])


# Informations sur le serveur
@bot.command(name='serverinfo', help='Affiche les informations du serveur')
async def serverinfo(ctx):
    guild = ctx.guild
    embed = discord.Embed(title=f"Informations sur {guild.name}", color=discord.Color.blue())
    embed.add_field(name="Propriétaire", value=guild.owner.mention)
    embed.add_field(name="Membres", value=guild.member_count)
    embed.add_field(name="Créé le", value=guild.created_at.strftime("%d/%m/%Y"))
    embed.add_field(name="Nombre de salons", value=len(guild.channels))
    embed.add_field(name="Nombre de rôles", value=len(guild.roles))
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    await ctx.send(embed=embed)

# Commande : Caca
@bot.command(name='caca', help='Envoie un message avec @everyone et un emoji caca (modifiable par les admins)')
@commands.has_permissions(administrator=True)  # Seul un administrateur peut utiliser cette commande
async def caca(ctx, emoji: str = '💩'):
    # Envoi du message avec @everyone et l'emoji caca
    await ctx.send(f"@everyone {emoji} CACA {emoji}")


# Système de rappels
@bot.command(name='reminder', help='Crée un rappel (!reminder "temps" "message")')
async def set_reminder(ctx, time, *, message):
    try:
        when = parser.parse(time)
        if when < datetime.now():
            await ctx.send("Le temps spécifié est dans le passé!")
            return
        
        reminders.append({
            'user': ctx.author.id,
            'channel': ctx.channel.id,
            'time': when,
            'message': message
        })
        await ctx.send(f"Je te rappellerai de '{message}' le {when.strftime('%d/%m/%Y à %H:%M')}")
    except ValueError:
        await ctx.send("Format de temps invalide! Utilisez un format comme '2024-02-20 15:30' ou 'demain 14:00'")

@tasks.loop(seconds=60)
async def check_reminders():
    now = datetime.now()
    to_remove = []
    
    for reminder in reminders:
        if reminder['time'] <= now:
            channel = bot.get_channel(reminder['channel'])
            user = await bot.fetch_user(reminder['user'])
            await channel.send(f"{user.mention}, rappel: {reminder['message']}")
            to_remove.append(reminder)
    
    for reminder in to_remove:
        reminders.remove(reminder)

# Lancer le bot
if __name__ == '__main__':
    bot.run(TOKEN)
