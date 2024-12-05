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
import typing
import aiohttp
from io import BytesIO

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
    'options': '-vn'
}

# Classe YTDLSource
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
intents.reactions = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Systèmes existants
levels = {}
try:
    with open('levels.json', 'r') as f:
        levels = json.load(f)
except FileNotFoundError:
    pass

reminders = []
warnings = {}
daily_rewards = {}

# Nouvelles fonctionnalités
class CustomHelp(commands.HelpCommand):
    async def send_bot_help(self, mapping):
        embed = discord.Embed(title="🤖 Aide du Bot", color=discord.Color.blue())
        
        # Catégories avec emojis
        categories = {
            "Music": "🎵 Musique",
            "Games": "🎮 Jeux",
            "AdvancedModeration": "🛡️ Modération",
            "Utilities": "🛠️ Utilitaires",
            None: "🎲 Commandes Générales"  # Pour les commandes sans catégorie
        }
        
        # Emojis pour les commandes spécifiques
        command_emojis = {
            "play": "▶️",
            "pause": "⏸️",
            "resume": "⏯️",
            "stop": "⏹️",
            "volume": "🔊",
            "join": "📥",
            "pendu": "🎯",
            "guess": "💭",
            "warn": "⚠️",
            "warnings": "📋",
            "kick": "🚫",
            "clear": "🧹",
            "avatar": "🖼️",
            "userinfo": "👤",
            "poll": "📊",
            "poll2": "📈",
            "giveaway": "🎉",
            "ping": "🏓",
            "dice": "🎲",
            "say": "💬",
            "joke": "😄",
            "serverinfo": "ℹ️",
            "caca": "💩",
            "reminder": "⏰",
            "rank": "📊",
            "top": "🏆",
            "stats": "📊",
            "daily": "🎁"
        }

        for cog, commands in mapping.items():
            filtered = await self.filter_commands(commands, sort=True)
            if filtered:
                cog_name = getattr(cog, "qualified_name", "Autres")
                category_name = categories.get(cog_name, cog_name)
                
                # Création de la liste des commandes avec leurs emojis
                cmd_list = []
                for cmd in filtered:
                    emoji = command_emojis.get(cmd.name, "➡️")  # Emoji par défaut si non trouvé
                    cmd_list.append(f"{emoji} `{cmd.name}` - {cmd.help}")
                
                if cmd_list:  # N'ajoute le field que s'il y a des commandes
                    embed.add_field(
                        name=category_name,
                        value="\n".join(cmd_list),
                        inline=False
                    )
        
        # Pied de page avec des informations supplémentaires
        embed.set_footer(text="💡 Utilisez !help <commande> pour plus de détails sur une commande spécifique")
        
        await self.get_destination().send(embed=embed)

    async def send_command_help(self, command):
        embed = discord.Embed(
            title=f"ℹ️ Aide pour la commande: {command.name}",
            color=discord.Color.blue()
        )
        
        # Ajouter la description de la commande
        embed.add_field(
            name="📝 Description",
            value=command.help or "Aucune description disponible",
            inline=False
        )
        
        # Ajouter la syntaxe de la commande
        syntax = f"!{command.name}"
        if command.signature:
            syntax += f" {command.signature}"
        embed.add_field(
            name="⌨️ Syntaxe",
            value=f"```{syntax}```",
            inline=False
        )
        
        # Ajouter les alias si présents
        if command.aliases:
            embed.add_field(
                name="🔄 Alias",
                value=", ".join(f"`{alias}`" for alias in command.aliases),
                inline=False
            )
        
        await self.get_destination().send(embed=embed)

bot.help_command = CustomHelp()

# Classe pour les jeux
class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.hangman_games = {}
        self.tictactoe_games = {}

    @commands.command(name='pendu', help='Jouer au pendu')
    async def hangman(self, ctx):
        if ctx.channel.id in self.hangman_games:
            await ctx.send("Une partie est déjà en cours dans ce canal!")
            return

        words = ['python', 'discord', 'bot', 'programmation', 'jeu', 'ordinateur']
        word = random.choice(words)
        guessed = set()
        max_tries = 6
        tries = 0

        self.hangman_games[ctx.channel.id] = {
            'word': word,
            'guessed': guessed,
            'tries': tries
        }

        await ctx.send("Partie de pendu commencée! Utilisez `!guess <lettre>` pour deviner.")
        await self.display_hangman(ctx)

    @commands.command(name='guess', help='Deviner une lettre au pendu')
    async def guess(self, ctx, letter: str):
        if ctx.channel.id not in self.hangman_games:
            await ctx.send("Aucune partie en cours! Utilisez `!pendu` pour commencer.")
            return

        game = self.hangman_games[ctx.channel.id]
        letter = letter.lower()

        if letter in game['guessed']:
            await ctx.send("Vous avez déjà deviné cette lettre!")
            return

        game['guessed'].add(letter)
        if letter not in game['word']:
            game['tries'] += 1

        await self.display_hangman(ctx)

    async def display_hangman(self, ctx):
        game = self.hangman_games[ctx.channel.id]
        word_display = ''
        for letter in game['word']:
            if letter in game['guessed']:
                word_display += letter
            else:
                word_display += '\\_'  # Correction de l'échappement

        hangman_pics = [
            '''
              +---+
              |   |
                  |
                  |
                  |
                  |
            =========''',  # Suppression des échappements inutiles
            '''
              +---+
              |   |
              O   |
                  |
                  |
                  |
            =========''',
            '''
              +---+
              |   |
              O   |
              |   |
                  |
                  |
            =========''',
            '''
              +---+
              |   |
              O   |
             /|   |
                  |
                  |
            =========''',
            '''
              +---+
              |   |
              O   |
             /|\  |
                  |
                  |
            =========''',
            '''
              +---+
              |   |
              O   |
             /|\  |
             /    |
                  |
            =========''',
            '''
              +---+
              |   |
              O   |
             /|\  |
             / \  |
                  |
            ========='''
        ]

        embed = discord.Embed(title="Pendu", color=discord.Color.blue())
        embed.add_field(name="Mot", value=word_display, inline=False)
        embed.add_field(name="Lettres devinées", value=', '.join(sorted(game['guessed'])) or "Aucune", inline=False)
        embed.add_field(name="État", value=f"```{hangman_pics[game['tries']]}```", inline=False)

        if word_display == game['word']:
            embed.add_field(name="Résultat", value="🎉 Félicitations! Vous avez gagné!", inline=False)
            del self.hangman_games[ctx.channel.id]
        elif game['tries'] >= 6:
            embed.add_field(name="Résultat", value=f"💀 Perdu! Le mot était: {game['word']}", inline=False)
            del self.hangman_games[ctx.channel.id]

        await ctx.send(embed=embed)

# Classe pour la modération avancée
class AdvancedModeration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='warn', help='Avertir un membre')
    @commands.has_permissions(kick_members=True)
    async def warn(self, ctx, member: discord.Member, *, reason="Aucune raison fournie"):
        if str(member.id) not in warnings:
            warnings[str(member.id)] = []
        
        warnings[str(member.id)].append({
            'reason': reason,
            'time': datetime.now().isoformat(),
            'warner': ctx.author.id
        })

        embed = discord.Embed(title="Avertissement", color=discord.Color.orange())
        embed.add_field(name="Membre", value=member.mention)
        embed.add_field(name="Raison", value=reason)
        embed.add_field(name="Nombre d'avertissements", value=len(warnings[str(member.id)]))
        
        await ctx.send(embed=embed)
        try:
            await member.send(f"Vous avez reçu un avertissement sur {ctx.guild.name}. Raison: {reason}")
        except:
            pass

    @commands.command(name='warnings', help='Voir les avertissements d\'un membre')
    @commands.has_permissions(kick_members=True)
    async def warnings(self, ctx, member: discord.Member):
        if str(member.id) not in warnings or not warnings[str(member.id)]:
            await ctx.send(f"{member.display_name} n'a aucun avertissement.")
            return

        embed = discord.Embed(title=f"Avertissements de {member.display_name}", color=discord.Color.orange())
        for i, warning in enumerate(warnings[str(member.id)], 1):
            warner = ctx.guild.get_member(warning['warner'])
            warner_name = warner.display_name if warner else "Modérateur inconnu"
            embed.add_field(
                name=f"Avertissement {i}",
                value=f"Raison: {warning['reason']}\nPar: {warner_name}\nDate: {parser.parse(warning['time']).strftime('%d/%m/%Y %H:%M')}",
                inline=False
            )
        
        await ctx.send(embed=embed)

# Classe pour les utilitaires
class Utilities(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='avatar', help='Afficher l\'avatar d\'un membre')
    async def avatar(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        embed = discord.Embed(title=f"Avatar de {member.display_name}", color=discord.Color.blue())
        embed.set_image(url=member.avatar.url if member.avatar else member.default_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name='userinfo', help='Afficher les informations d\'un membre')
    async def userinfo(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        roles = [role.mention for role in member.roles[1:]]  # Exclure @everyone
        
        embed = discord.Embed(title="Informations utilisateur", color=member.color)
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        
        embed.add_field(name="Nom", value=member.display_name, inline=True)
        embed.add_field(name="ID", value=member.id, inline=True)
        embed.add_field(name="Compte créé le", value=member.created_at.strftime("%d/%m/%Y"), inline=True)
        embed.add_field(name="A rejoint le", value=member.joined_at.strftime("%d/%m/%Y"), inline=True)
        embed.add_field(name=f"Rôles ({len(roles)})", value=" ".join(roles) if roles else "Aucun", inline=False)
        
        await ctx.send(embed=embed)

    @commands.command(name='poll2', help='Créer un sondage avancé')
    async def poll2(self, ctx, question: str, *options):
        if len(options) < 2:
            await ctx.send("Il faut au moins 2 options!")
            return
        if len(options) > 10:
            await ctx.send("Maximum 10 options!")
            return

        emoji_numbers = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
        description = []
        for i, option in enumerate(options):
            description.append(f"{emoji_numbers[i]} {option}")

        embed = discord.Embed(
            title=question,
            description="\n".join(description),
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Sondage créé par {ctx.author.display_name}")
        
        poll_msg = await ctx.send(embed=embed)
        for i in range(len(options)):
            await poll_msg.add_reaction(emoji_numbers[i])

    @commands.command(name='giveaway', help='Créer un giveaway')
    @commands.has_permissions(manage_messages=True)
    async def giveaway(self, ctx, duration: str, winners: int, *, prize: str):
        try:
            duration_seconds = self.parse_duration(duration)
        except ValueError:
            await ctx.send("Format de durée invalide! Utilisez par exemple: 1h, 30m, 1d")
            return

        if winners < 1:
            await ctx.send("Il faut au moins 1 gagnant!")
            return

        end_time = datetime.now() + timedelta(seconds=duration_seconds)
        
        embed = discord.Embed(
            title="🎉 GIVEAWAY 🎉",
            description=f"**Prix:** {prize}\n\n"
                      f"Réagissez avec 🎉 pour participer!\n\n"
                      f"Fin dans: {duration}\n"
                      f"Nombre de gagnants: {winners}",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Se termine le {end_time.strftime('%d/%m/%Y à %H:%M')}")
        
        message = await ctx.send(embed=embed)
        await message.add_reaction("🎉")
        
        await asyncio.sleep(duration_seconds)
        
        message = await ctx.channel.fetch_message(message.id)
        reaction = discord.utils.get(message.reactions, emoji="🎉")
        
        if reaction.count <= 1:
            await ctx.send("Pas assez de participants pour le giveaway!")
            return
            
        users = [user async for user in reaction.users() if not user.bot]
        if len(users) < winners:
            winners = len(users)
            
        winners_list = random.sample(users, winners)
        winners_mentions = [winner.mention for winner in winners_list]
        
        await ctx.send(f"🎉 Félicitations {', '.join(winners_mentions)}! Vous avez gagné: **{prize}**!")

    def parse_duration(self, duration: str) -> int:
        duration = duration.lower()
        total_seconds = 0
        
        time_units = {
            's': 1,
            'm': 60,
            'h': 3600,
            'd': 86400
        }
        
        current_number = ""
        for char in duration:
            if char.isdigit():
                current_number += char
            elif char in time_units:
                if not current_number:
                    raise ValueError("Format invalide")
                total_seconds += int(current_number) * time_units[char]
                current_number = ""
            else:
                raise ValueError("Format invalide")
                
        if current_number:
            raise ValueError("Format invalide")
            
        return total_seconds

# Garder les fonctionnalités existantes intactes
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

# Fonction pour créer un embed de niveau
async def create_rank_image(user, xp, level, rank, total_users):
    # Création d'un embed moderne pour le rank avec une couleur dynamique
    colors = {
        1: discord.Color.from_rgb(192, 192, 192),  # Argent
        5: discord.Color.from_rgb(218, 165, 32),   # Or
        10: discord.Color.from_rgb(229, 83, 0),    # Bronze
        15: discord.Color.from_rgb(219, 112, 147), # Rose
        20: discord.Color.from_rgb(138, 43, 226)   # Violet
    }
    
    # Sélectionner la couleur en fonction du niveau
    embed_color = discord.Color.blue()
    for lvl, color in sorted(colors.items(), reverse=True):
        if level >= lvl:
            embed_color = color
            break
    
    embed = discord.Embed(color=embed_color)
    
    # Titre avec des emojis basés sur le niveau
    level_emojis = {
        1: "🌱",   # Débutant
        5: "⭐",   # Étoile
        10: "💫",  # Super étoile
        15: "🌟",  # Méga étoile
        20: "👑",  # Roi
        30: "⚡",  # Légende
        50: "🔥"   # Dieu
    }
    
    level_emoji = "🌱"
    for lvl, emoji in sorted(level_emojis.items(), reverse=True):
        if level >= lvl:
            level_emoji = emoji
            break
    
    embed.set_author(
        name=f"Niveau de {user.display_name} {level_emoji}",
        icon_url=user.avatar.url if user.avatar else user.default_avatar.url
    )
    
    # Calcul de la progression
    xp_needed = level * 100
    progress = (xp % 100) / 100
    
    # Barre de progression améliorée avec des emojis
    bar_length = 10
    filled = int(progress * bar_length)
    
    # Nouveaux caractères pour la barre de progression
    progress_bar = "▰" * filled + "▱" * (bar_length - filled)
    
    # Stats avec emojis
    embed.add_field(
        name="👥 Rang",
        value=f"#{rank}/{total_users}",
        inline=True
    )
    embed.add_field(
        name=f"{level_emoji} Niveau",
        value=str(level),
        inline=True
    )
    embed.add_field(
        name="✨ XP",
        value=f"{xp}/{xp_needed}",
        inline=True
    )
    
    # Barre de progression avec pourcentage
    embed.add_field(
        name=f"📊 Progression • {int(progress * 100)}%",
        value=f"`{progress_bar}`",
        inline=False
    )
    
    # Footer avec XP restant et message motivant
    xp_remaining = xp_needed - (xp % 100)
    motivational_messages = [
        "Continue comme ça! 🎮",
        "Tu es sur la bonne voie! 🎯",
        "Plus que {xp_remaining} XP! 💪",
        "La victoire est proche! 🏆",
        "Tu peux le faire! ⚡"
    ]
    
    embed.set_footer(text=f"{random.choice(motivational_messages).format(xp_remaining=xp_remaining)}")
    
    return embed

# Modification du système de gain d'XP
def calculate_xp_for_level(level):
    """Calcule l'XP nécessaire pour atteindre le niveau suivant"""
    return int(100 * (1.2 ** (level - 1)))

def calculate_total_xp(level):
    """Calcule l'XP total nécessaire jusqu'à ce niveau"""
    total = 0
    for lvl in range(1, level + 1):
        total += calculate_xp_for_level(lvl)
    return total

@bot.event
async def on_message(message):
    if not message.author.bot:
        user_id = str(message.author.id)
        if user_id not in levels:
            levels[user_id] = {"xp": 0, "level": 1}
        
        # Système de gain d'XP réduit et plus équilibré
        base_xp = random.randint(3, 8)  # Réduit de 15-25 à 3-8
        
        # Bonus réduits
        if len(message.content) > 100:
            base_xp += 2  # Réduit de 5 à 2
        if message.attachments:
            base_xp += 1  # Réduit de 3 à 1
        if message.embeds:
            base_xp += 1  # Réduit de 2 à 1
        
        levels[user_id]["xp"] += base_xp
        current_xp = levels[user_id]["xp"]
        current_level = levels[user_id]["level"]
        
        # Vérifier si le niveau augmente
        while current_xp >= calculate_total_xp(current_level):
            current_level += 1
            levels[user_id]["level"] = current_level
            
            # Message de niveau supérieur
            embed = discord.Embed(
                title=f"🎉 NIVEAU SUPÉRIEUR! 🎊",
                description=f"Félicitations {message.author.mention}!",
                color=discord.Color.gold()
            )
            
            # Effets visuels selon le niveau
            if current_level >= 20:
                embed.description += "\n👑 **NIVEAU LÉGENDAIRE!** 👑"
            elif current_level >= 10:
                embed.description += "\n⭐ **NIVEAU ÉTOILE!** ⭐"
            elif current_level >= 5:
                embed.description += "\n✨ **NIVEAU SPÉCIAL!** ✨"
            
            next_level_xp = calculate_xp_for_level(current_level)
            
            embed.add_field(
                name="📈 Progression",
                value=f"```Niveau {current_level-1} ➜ Niveau {current_level}```",
                inline=False
            )
            embed.add_field(
                name="🌟 XP Total",
                value=f"```{current_xp} XP```",
                inline=True
            )
            embed.add_field(
                name="⚡ Prochain niveau",
                value=f"```{next_level_xp} XP requis```",
                inline=True
            )
            
            embed.set_thumbnail(url=message.author.avatar.url if message.author.avatar else message.author.default_avatar.url)
            embed.set_footer(text="🎮 Continue de discuter pour gagner plus d'XP!")
            
            await message.channel.send(embed=embed)
        
        with open('levels.json', 'w') as f:
            json.dump(levels, f)
    
    await bot.process_commands(message)

# Commande pour afficher le niveau
@bot.command(name='rank', help='Affiche ton niveau et ton rang')
async def rank(ctx, member: discord.Member = None):
    member = member or ctx.author
    user_id = str(member.id)
    
    if user_id not in levels:
        if member == ctx.author:
            await ctx.send("Tu n'as pas encore de niveau! Continue à discuter pour en gagner.")
        else:
            await ctx.send(f"{member.display_name} n'a pas encore de niveau!")
        return
    
    # Trier tous les utilisateurs par XP pour déterminer le rang
    sorted_users = sorted(levels.items(), key=lambda x: (x[1]["level"], x[1]["xp"]), reverse=True)
    user_rank = next(i for i, (uid, _) in enumerate(sorted_users, 1) if uid == user_id)
    
    xp = levels[user_id]["xp"]
    lvl = levels[user_id]["level"]
    
    # Créer et envoyer l'embed
    embed = await create_rank_image(member, xp, lvl, user_rank, len(levels))
    await ctx.send(embed=embed)

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

# Système de classement et statistiques
@bot.command(name='top', help='Affiche le classement des membres')
async def leaderboard(ctx, page: int = 1):
    # Trier les utilisateurs par niveau et XP
    sorted_users = sorted(levels.items(), key=lambda x: (x[1]["level"], x[1]["xp"]), reverse=True)
    
    # Pagination (10 utilisateurs par page)
    items_per_page = 10
    pages = (len(sorted_users) + items_per_page - 1) // items_per_page
    page = min(max(1, page), pages)
    
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    
    embed = discord.Embed(
        title="🏆 Classement du Serveur",
        description="Les membres les plus actifs",
        color=discord.Color.gold()
    )
    
    medal_emojis = ["🥇", "🥈", "🥉"]
    
    for idx, (user_id, data) in enumerate(sorted_users[start_idx:end_idx], start=start_idx + 1):
        try:
            member = await ctx.guild.fetch_member(int(user_id))
            if member:
                # Ajouter médaille pour le top 3
                rank_emoji = medal_emojis[idx-1] if idx <= 3 else f"#{idx}"
                
                # Obtenir l'emoji de niveau
                level_emoji = "🌱"
                for lvl, emoji in sorted(level_emojis.items(), reverse=True):
                    if data["level"] >= lvl:
                        level_emoji = emoji
                        break
                
                embed.add_field(
                    name=f"{rank_emoji} {member.display_name}",
                    value=f"{level_emoji} Niveau {data['level']} • ✨ {data['xp']} XP",
                    inline=False
                )
        except:
            continue
    
    embed.set_footer(text=f"Page {page}/{pages} • Utilisez !top <numéro de page>")
    await ctx.send(embed=embed)

@bot.command(name='stats', help='Affiche les statistiques détaillées d\'un membre')
async def stats(ctx, member: discord.Member = None):
    member = member or ctx.author
    user_id = str(member.id)
    
    if user_id not in levels:
        await ctx.send("Aucune statistique disponible pour ce membre.")
        return
    
    # Récupérer les données
    data = levels[user_id]
    xp = data["xp"]
    lvl = data["level"]
    
    # Calculer le rang
    sorted_users = sorted(levels.items(), key=lambda x: (x[1]["level"], x[1]["xp"]), reverse=True)
    rank = next(i for i, (uid, _) in enumerate(sorted_users, 1) if uid == user_id)
    
    # Créer l'embed
    embed = discord.Embed(
        title=f"📊 Statistiques de {member.display_name}",
        color=member.color
    )
    
    # Avatar
    embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
    
    # Statistiques principales
    embed.add_field(
        name="🏆 Classement",
        value=f"#{rank} sur {len(levels)} membres",
        inline=True
    )
    embed.add_field(
        name="📈 Niveau",
        value=str(lvl),
        inline=True
    )
    embed.add_field(
        name="✨ XP Total",
        value=str(xp),
        inline=True
    )
    
    # Progression
    xp_for_next = calculate_xp_for_level(lvl)
    current_level_xp = xp % xp_for_next
    progress = (current_level_xp / xp_for_next) * 100
    
    # Barre de progression
    progress_bar = "▰" * int(progress/10) + "▱" * (10 - int(progress/10))
    embed.add_field(
        name="📊 Progression vers le niveau suivant",
        value=f"`{progress_bar}` {int(progress)}%",
        inline=False
    )
    
    # Estimation du temps restant
    xp_needed = xp_for_next - current_level_xp
    messages_needed = xp_needed // 20  # En supposant une moyenne de 20 XP par message
    embed.add_field(
        name="⏳ Estimation",
        value=f"Environ {messages_needed} messages pour le prochain niveau",
        inline=False
    )
    
    # Badges et récompenses
    badges = []
    if lvl >= 50: badges.append("🔥 Dieu")
    if lvl >= 30: badges.append("⚡ Légende")
    if lvl >= 20: badges.append("👑 Roi")
    if lvl >= 15: badges.append("🌟 Méga étoile")
    if lvl >= 10: badges.append("💫 Super étoile")
    if lvl >= 5: badges.append("⭐ Étoile")
    
    if badges:
        embed.add_field(
            name="🏅 Badges Débloqués",
            value="\n".join(badges),
            inline=False
        )
    
    await ctx.send(embed=embed)

# Système de récompenses quotidiennes
@bot.command(name='daily', help='Récupère ta récompense quotidienne d\'XP')
async def daily(ctx):
    user_id = str(ctx.author.id)
    current_time = datetime.now()
    
    if user_id in daily_rewards:
        last_claim = datetime.fromisoformat(daily_rewards[user_id])
        time_diff = current_time - last_claim
        
        if time_diff.days < 1:
            next_claim = last_claim + timedelta(days=1)
            time_remaining = next_claim - current_time
            hours = time_remaining.seconds // 3600
            minutes = (time_remaining.seconds % 3600) // 60
            
            await ctx.send(f"⏳ Tu dois attendre encore {hours}h {minutes}m pour ta prochaine récompense!")
            return
    
    if user_id not in levels:
        levels[user_id] = {"xp": 0, "level": 1}
    
    current_level = levels[user_id]["level"]
    
    # Récompense de base réduite
    bonus_xp = random.randint(15, 30)  # Réduit de 50-100 à 15-30
    
    # Bonus basé sur le niveau (plus petit)
    level_bonus = current_level * 2  # Réduit de 5 à 2
    bonus_xp += level_bonus
    
    levels[user_id]["xp"] += bonus_xp
    daily_rewards[user_id] = current_time.isoformat()
    
    with open('levels.json', 'w') as f:
        json.dump(levels, f)
    
    embed = discord.Embed(
        title="🎁 Récompense Quotidienne!",
        description=f"Félicitations {ctx.author.mention}!",
        color=discord.Color.green()
    )
    
    embed.add_field(
        name="💰 Récompense",
        value=f"+{bonus_xp} XP",
        inline=True
    )
    
    if level_bonus > 0:
        embed.add_field(
            name="⭐ Bonus de niveau",
            value=f"+{level_bonus} XP",
            inline=True
        )
    
    # Afficher la progression
    current_xp = levels[user_id]["xp"]
    next_level_xp = calculate_xp_for_level(current_level)
    xp_needed = next_level_xp - (current_xp % next_level_xp)
    
    embed.add_field(
        name="📊 Progression",
        value=f"Plus que {xp_needed} XP pour le niveau {current_level + 1}!",
        inline=False
    )
    
    embed.set_footer(text="Reviens demain pour plus de récompenses!")
    await ctx.send(embed=embed)

# Ajouter les nouvelles classes au bot
async def setup():
    await bot.add_cog(Games(bot))
    await bot.add_cog(AdvancedModeration(bot))
    await bot.add_cog(Utilities(bot))
    await bot.add_cog(Music(bot))

# Lancer le bot
if __name__ == '__main__':
    asyncio.run(setup())
    bot.run(TOKEN)
