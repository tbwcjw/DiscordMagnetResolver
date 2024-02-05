# DiscordMagnetResolver - Christian Wiles 2023
import os
import discord
from discord.ext import commands
import re
import libtorrent as lt
from urllib.parse import unquote
import tempfile
import asyncio

#libtorrent forced me to this
import warnings

intents = discord.Intents.default()
intents.message_content = True
intents.typing = True
intents.presences  = True

bot = commands.Bot(command_prefix='/', case_insensitive=True, intents=intents)
resp = set()
TIMEOUT = 30
TOKEN = os.environ.get('TOKEN')
DHT_PORTS = [6881, 6891]

@bot.event
async def on_ready():
    bot.app_author = 'tbwcjw'
    bot.app_title = 'DiscordMagnetResolver'
    bot.app_version = '2.0.0'
    print(f"{bot.app_title} - {bot.app_version}\nBy {bot.app_author}, 2023.\nLogged in as {bot.user.name}")
    await bot.change_presence(activity=discord.Game(name="Waiting for magnet links..."))

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return  # im retarded
    
    magnet = message.content.lower()
    if 'magnet:' in magnet and message.id not in resp:
        await bot.change_presence(activity=discord.Game(name="Getting metadata for a magnet..."))
        resp.add(message.id)
        print(f"[NOTICE] waiting to process magnet for message: {message.id}")
        info = await processMagnet(magnet)
        valid = await validateMagnet(magnet)
        if valid is True and info is not None and info is not False:
            print(f"[OK]received metadata for a magnet with infohash: {info.info_hash()} ")
            await message.add_reaction("\U0001F7E2") #green\
            await message.reply(embed=await response(info, magnet))
            print(f"[OK]sent reply to {message.id} with infohash: {info.info_hash()}")
        else:
            print(f"[FAILED]failed to recieve metadata for a magnet link")
            await message.add_reaction("\U0001F534") #red
    await bot.change_presence(activity=discord.Game(name="Waiting for magnet links..."))
    await bot.process_commands(message)

@bot.command(description='Helpful information about the bot.')
async def about(ctx):
    print(f"called /about by: {ctx.author.name} ({ctx.author.id})")
    await ctx.send(f"""
    > **{bot.app_title}** - Version {bot.app_version}
    > By {bot.app_author}, 2023.
    > 
    > __Usage:__
    > 
    > -Paste a magnet link you wish to share, make sure it has the `magnet:` prefix.
    > -Send it, wait a while. When the bot validates the magnet it will leave a green circle reaction.
    > -An invalid magnet link will yield the red circle reaction of **doom**
    > -The bot will reply to the original message with all the information it can on the magnet and its associated torrent.
                   """)

async def response(info, magnet):
    embed=discord.Embed(
        title=f"{info.name()}",
    )
    embed.set_author(name="\U0001F916 Discord Magnet Resolver")
    embed.add_field(name="Infohash:", value=f"{info.info_hash()}", inline=False)
    embed.add_field(name="Total Size:", value=f"{info.total_size() / (1024*1024):.2f} MB")
    embed.add_field(name="Number Of Files:", value=f"{info.num_files()}")
    
    if info.num_files() < 14: #annoying
        file_tree = ""
        if info.files is not None:
            embed.add_field(name="File List:", value="", inline=False)
            for file in info.files():
                file.path = file.path.replace(info.name()+"\\", "")
                embed.add_field(name=f"> {file.path}", value=f"> {file.size / (1024*1024):.2f} MB", inline=True)
        else:
            print(f"[NOTICE]Couln't retrieve file list for infohash {info.info_hash()}")
    else:
        embed.add_field(name="File List:", value="Too many files to show...", inline=False)
    
    if len(info.trackers) > 0 and info.trackers is not None:
        embed.add_field(name="Tracker List:", value="", inline=False)
        for tracker in info.trackers:
            embed.add_field(name="", value=f"{unquote(tracker)}", inline=False)
    
    embed.set_footer(text=f"Number of pieces: {info.num_pieces()} / Piece length: {info.piece_length()}")
    return embed
async def processMagnet(input) -> None:
    try:
        ses = lt.session()
        ses.listen_on(DHT_PORTS[0], DHT_PORTS[1])
        params = {'save_path': tempfile.mkdtemp(),
                'file_priorities': [0] * 1000}
        ses.add_dht_router("router.utorrent.com", 6881)
        ses.add_dht_router("router.bittorrent.com", 6881)
        ses.add_dht_router("dht.transmissionbt.com", 6881)
        ses.start_dht()
        h = lt.add_magnet_uri(ses, input, params)
        print(f"[OK]libtorrent session started")
    except:
        print(f"[FAILED]libtorrent session could not be created on ports {DHT_PORTS[0]}, {DHT_PORTS[1]}")
        return False

    wait = 0
    TIMEOUT = 15

    try:
        while not h.has_metadata():
            wait += 1
            await asyncio.sleep(1)
            if wait > TIMEOUT:
                print(f"[FAILED]recieving metadata timed out")
                return None
    except Exception as e:
        print(f"[FAILED]libtorrent handle error: {e}")
        return None
    finally:
        torinfo = h.get_torrent_info()
        torinfo.trackers = set(re.findall(r'&tr=([^&]+)', input)) #list the trackers
        ses.remove_torrent(h, lt.options_t.delete_files)
        ses.pause()
        
    return torinfo

async def validateMagnet(input):
    pattern = r'^magnet:\?xt=urn:btih:[A-Fa-f0-9]{40,40}.*$'
    if re.match(pattern, unquote(input)):
        print(f"[SUCCESS]input is a valid magnet")
        return True
    else:
        print(f"[FAILED]input isn't a valid magnet...")
        return False
    
if __name__ == '__main__' and TOKEN is not None:
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    bot.run(TOKEN)
