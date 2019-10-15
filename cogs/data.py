from discord.ext import commands
from utils.utils import get_payload, attempt_delete
from utils.profile import generate_profile
import asyncio


class DataCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.timer = 300

    @commands.command(name="check_profile")
    async def check_profile(self, ctx, user_id: int):
        # Sends the profile imag
        pf = await generate_profile(ctx, user_id)
        while True:
            profile = pf.render_profile()
            payload = get_payload(profile)
            profile_msg = await ctx.send("", file=payload, text=True)

            # Deploys reactions to the image that are interactable
            # and affects the profile behaviour
            try:
                reaction = await pf.deploy_reactions(profile_msg, "arrows", "toggle","cancel", timer=self.timer)
            except asyncio.TimeoutError:
                await attempt_delete(profile_msg)
                return
            if str(reaction) == "<:redTick:600735269792120977>":
                return

    async def setup_cog(self):
        await self.bot.wait_until_ready()
        await self.setup_guilds()

    async def setup_guilds(self):
        async with self.bot.pool.acquire() as c:
            # We need to add the missing users to the databases too
            # Puts all the users FROM the database INTO cache
            self.bot.cache._db["guilds"] = {}
            self.bot.cache._db["users"] = []
            users = await c.fetch("SELECT member_id FROM users")
            for user in users:
                member_id = user["member_id"]

                #CACHE
                # Appends all the users registered to a local cache to be used for fast instructions
                self.bot.cache.append("users", member_id)

                # Now search which guilds this user belongs to, add add to guild database
                for guild in self.bot.guilds:
                    member = guild.get_member(member_id)
                    if member:
                        #DATABASE

                        # Should only insert if entry does not already exist
                        await c.execute(
                            "INSERT INTO guilds (member_id, guild_id) VALUES ($1, $2) ON CONFLICT (member_id, guild_id) DO NOTHING",
                            member.id, guild.id)

                        #CACHE
                        # Checks if the guild exists
                        if not self.bot.cache._db["guilds"].get(guild.id):
                            # If not, we hand it an emptry array for appendage
                            self.bot.cache._db["guilds"][guild.id] = []

                        # Appends the member_id to the guild
                        self.bot.cache._db["guilds"][guild.id].append(member_id)

    @commands.Cog.listener("on_member_join")
    async def on_member_join(self, member):
        # Check if the joined user exists in the database, if they do, add them to the guild
        # Checks if the user is registered to the bot
        user = self.bot.cache.get_from_list("users", member.id)
        if not user:
            return

        # check if there is a guild entry
        if not member.guild.id in self.bot.cache._db["guilds"]:
            self.bot.cache._db["guilds"][member.guild.id] = []

        async with self.bot.pool.acquire() as c:
            # If that is true, we add him to the guild cluster
            await c.execute("INSERT INTO guilds (member_id, guild_id) VALUES ($1, $2) ON CONFLICT (member_id, guild_id) DO NOTHING", member.id, member.guild.id)
            # Also add it to the cache
            self.bot.cache._db["guilds"][member.guild.id].append(member.id)

    @commands.Cog.listener("on_member_remove")
    async def on_member_remove(self, member):
        # Remove the user from the database if the entry exists
        user = self.bot.cache.get_from_list("users", member.id)
        if not user:
            return

        async with self.bot.pool.acquire() as c:
            # Removes the user and guild tie in the database
            await c.execute("DELETE FROM guilds WHERE member_id = $1 AND guild_id = $2", member.id, member.guild.id)
            # Removes it from the cache
            self.bot.cache._db["guilds"][member.guild.id].remove(member.id)

    @commands.Cog.listener("on_guild_join")
    async def on_guild_join(self, guild):
        # Make the bot check every user in the guild who owns a profile, and create a new guild entry and inser them all
        users = []

        # Iterate every member in the guild. If they're registered to the bot, we append them to a new list that will
        # then be added invidually to the database
        for member in guild.members:
            user = self.bot.cache.get_from_list("users", member.id)
            if user:
                users.append(user)

        # This mean at least one user were registered
        if users:
            self.bot.cache._db["guilds"][guild.id] = []
            async with self.bot.pool.acquire() as c:
                for user in users:
                    # Enters the user to the guild database
                    await c.execute("INSERT INTO guilds (member_id, guild_id) VALUES ($1, $2) ON CONFLICT (member_id, guild_id) DO NOTHING", user, guild.id)

                    # Enters user to the cache
                    self.bot.cache._db["guilds"][guild.id].append(user)

    @commands.Cog.listener("on_guild_remove")
    async def on_guild_remove(self, guild):
        # Check if the guild exists in the cache
        guilded = self.bot.cache._db["guilds"].get(guild.id)
        if not guilded:
            return
        async with self.bot.pool.acquire() as c:
            # Remove from database
            await c.execute("DELETE FROM guilds WHERE guild_id = $1", guild.id)
            # Remove from cache
            del self.bot.cache._db["guilds"][guild.id]


def setup(bot):
    bot.add_cog(DataCog(bot))