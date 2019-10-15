import logging
import sys
import traceback

import aiohttp
import aioredis
import discord
from discord.ext import commands
import discord.ext.commands.errors as errors
import datetime
from utils.command import RestrictedCommand
from utils.errors import RestrictionError
from utils.cache import ImageCache, FontCache, Cache, JsonCache
from utils.context import Context
from utils.prefix import Prefix
from utils.profile import generate_profile
import asyncio

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%m-%d %H:%M',
                    handlers=[
                        logging.FileHandler("/home/ec2-user/logs/freya.log", mode='w'),
                        #logging.StreamHandler()
                    ])




extensions = ["cogs.profile", "cogs.swipe", "cogs.data", "cogs.general", "cogs.stats", "cogs.settings", "cogs.voting", "cogs.verification", "cogs.image"]


class Rdb(object):
    def __init__(self, uri, loop):
        self.redis_adress = uri
        self.loop = loop
        self.loop.create_task(self.create())

    async def create(self):
        self.redis = await aioredis.create_redis(self.redis_adress, encoding='utf8')


def _prefix_callable(bot, msg):
    user_id = bot.user.id
    base = [f'<@!{user_id}> ', f'<@{user_id}> ']
    if msg.guild is None:
        base.append('t.')
        base.append('T.')
    else:
        base.extend(bot.prefixes.get(msg.guild.id, ['t.', 'T.']))
    return base


class Tinker(commands.AutoShardedBot):
    def __init__(self):
        super().__init__(command_prefix=_prefix_callable, owner_id=394859035209498626, case_insensitive=True)
        self.restrictions = ["create", "edit", ""]
        self.reactions = {"arrows": ["◀", "▶"],
                          "toggle": ["⏏"],
                          "ticks": ["<:greenTick:600735269993578496>", "<:redTick:600735269792120977>"],
                          "boolean": ["<:greenTick:600735269993578496>", "<:redTick:600735269792120977>"],
                          "thumbs": ["👍","👎"],
                          "cancel": ["<:redTick:600735269792120977>"],
                          "pager": ["⏪", "⏩"],
                          "superlike": "🔥"
        }

        self.translate = {"greenTick": 1, "redTick": 0}

        # Simple "cache" for some data
        self.data = {}

        self.cache = Cache()
        # Prefix class for fetching cached prefixes
        self.prefixes = Prefix(self)

        # Loads the images into memory
        self.images = ImageCache("images")

        # Removes the help command
        self.remove_command("help")
        # Loads the extensions (cogs)
        for ext in extensions:
            try:
                self.load_extension(ext)
            except Exception:
                print(f'Failed to load extension {ext}.', file=sys.stderr)
                traceback.print_exc()
            else:
                print(f'Successfully loaded {ext}')
        # Can be used to measure statistics
        self.stats = {}

        # Can be used to prevent people from using commands multiple times
        self.restricted = {}

        # Loads the fonts into memory
        self.fonts = FontCache("fonts")

        # Loads data from json files as a directory
        self.json = JsonCache()

        # Creates session for API calls.
        self.session = aiohttp.ClientSession(loop=self.loop)

        # Starts background tasks ::

        # Starts the latency timer
        self.loop.create_task(self.latency_timer())

        # Creates redis database class
        #self.db = Rdb(config.redis_path, self.loop)

        print("Tinker successfully initialized.")

    async def latency_timer(self):
        await self.wait_until_ready()
        while True:
            for latency in self.latencies:
                logging.info(f"Shard {latency[0]}: {latency[1]}s")
            await asyncio.sleep(60)

    async def setup(self):
        # Sets up the cogs
        await self.setup_cogs()

    async def setup_cogs(self):
        for cog_name in self.cogs:
            cog = self.get_cog(cog_name)
            try:
                func = getattr(cog, "setup_cog")
            except AttributeError:
                print(f"{cog_name} is missing a setup function")
            else:
                self.loop.create_task(func())

    async def set_guild_prefix(self, guild, prefix):
        self.prefixes.put(guild.id, prefix)

    # Handles all the command exceptions
    async def on_command_error(self, context, exception):
        # Command helper output
        if isinstance(exception, errors.MissingRequiredArgument) or isinstance(exception, errors.BadArgument):
            command_help = self.json.db["command_helper"]
            name = context.command.name
            command = command_help[name]
            usage = command_help[name]["usage"]
            string = ""

            for example in command_help[name]["examples"]:
                string += "``" + context.prefix + example + "``\n"
            fields = [("Examples:", string)]
            await context.send("You entered the command incorrectly.", description=f"Correct Format: ``{context.prefix}{name} {usage}``", field=fields[0])

        if isinstance(exception, errors.CommandOnCooldown):
            await context.send(str(exception))
        if context.command:

            # We enter here if it's any form of restricted command
            if isinstance(context.command, RestrictedCommand):

                # Even if the command crashed, we remove the command restriction
                # Unless the error is of the type "RestrictionError"
                if not isinstance(exception, RestrictionError):
                    self.restricted[context.author.id][context.command.name] = False
                else:
                    await context.send("This command is already running. Exit the earlier command to start a new one")

            print("Error:", exception, "User: ", context.author, "(" + str(context.author.id) + "),", "Command:", context.command.name + ",", "Guild: " + str(context.guild) + ", Channel: "+ str(context.channel))
        else:
            print("Error:", exception, "User: ", context.author, "(" + str(context.author.id) + "),", "Guild: " + str(context.guild) + ", Channel: "+ str(context.channel))

    # Can be used for statistics
    async def on_command(self, context):
        date = datetime.datetime.now()
        date = str(date).split()
        print(context.author, "executing", context.command.name, "in", context.guild, "in", context.channel)

    async def on_message(self, message):
        # Wait untill the bot is ready
        await self.wait_until_ready()

        if message.author.bot:
            return

        # Lets us know if the message is sent in DM's or guild
        if message.guild:
            pass
        else:
            pass

        # Sends the message further for processing
        await self.process_commands(message)

    async def process_commands(self, message):

        # Grabs the context. We can use our own context class here with the `cls` parameter


        ctx = await self.get_context(message, cls=Context)

        # If the context doesn't contain a command
        if not ctx.command:
            return

        # Invoked the context (Takes us to the cog command)
        # Also pools a connection for the database as ctx.db
        async with ctx.acquire():

            # Here the profile should also be fetched.
            # If the user have no profile registered AND the command isn't create

            ctx.profile = await generate_profile(ctx)
            if not ctx.profile:
                if ctx.command:
                    if ctx.command.name != "create" and ctx.command.name != "help":
                        await ctx.send(f"You have to register a profile.\nUse ``{ctx.prefix}create``")
                        return

            # Fetch the images if profile exists
            else:
                await ctx.profile.fetch_pictures()

            # Invoke the command
            await self.invoke(ctx)

    # This runs whenever the bot reconnects. Setup functions is more useful in the init of the bot class, not here
    async def on_ready(self):
        await self.change_presence(status=discord.Status.online, activity=discord.Game(f"Prefix: `t.`"))
        print(f'Ready: {self.user} (ID: {self.user.id})')
        print(discord.__version__)
        print('------')
        self.loop.create_task(self.setup())

    # Make sure the events adds people to the guild database if needed







