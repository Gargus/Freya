import dbl
import discord
from discord.ext import commands
from urllib.parse import urlencode
import aiohttp
import asyncio
import logging
from datetime import datetime, timedelta
import dbl
import config



class VotingCog(commands.Cog):
    """Handles interactions with the discordbots.org API"""

    def __init__(self, bot):
        self.bot = bot
        self.token = config.db_token
        # set this to your DBL token
        self.dblpy = None
        self.dblpy = dbl.DBLClient(self.bot, self.token)
        self.bot.loop.create_task(self.update_stats())

        # Simple cache for users to see if they're on a voting cooldown or not
        self.users = {}
        self.vote_link = "https://discordbots.org/bot/600024172726321171/vote"

    async def update_stats(self):
        """This function runs every 30 minutes to automatically update your server count"""
        if self.dblpy is None:
            return

        """Add this line here so it won't attempt to post before the dbl client is properly set up"""
        await self.bot.wait_until_ready()

        while True:
            logger.info('attempting to post server count')
            try:
                await self.dblpy.post_guild_count()
                logger.info('posted server count ({})'.format(len(self.bot.guilds)))
            except Exception as e:
                logger.exception('Failed to post server count\n{}: {}'.format(type(e).__name__, e))
            await asyncio.sleep(1800)

    @commands.command(name="claim")
    async def claim(self, ctx):
        testing = False
        _type = "upvote"
        bot_id = self.bot.user.id
        if testing:
            _type = "test"
            bot_id = 600024172726321171
        # Entry containing if the user has voted, and a date value
        entry = self.users.get(ctx.author.id)
        if entry:
            # This mean the time has exceeded 12h
            if datetime.now() > entry["date"]:
                # Removes the date entry from the cache
                del self.users[ctx.author.id]

        # If entry doesn't exist, apply it
        entry = self.users.get(ctx.author.id)
        if not entry:
            voter = await ctx.db.fetchrow("SELECT date, claimed FROM voters WHERE user_id = $1 AND bot_id = $2 AND type = $3",
                                       ctx.author.id, bot_id, _type)

            # User has never voted
            if not voter:
                await ctx.send(f"You've not voted yet! Go to: {self.vote_link}"
                               "\n to vote, and use the command again to claim your reward!")
                return

            # If the vote exists, set the date
            self.users[ctx.author.id] = {"date": voter["date"], "claimed": voter["claimed"]}
            entry = {"date": voter["date"], "claimed": voter["claimed"]}

        # entry should exist if we get here
        # If the 12h has exceeded the date
        date = entry["date"]
        claimed = entry["claimed"]

        # If the user has claimed before, we want to check if the user is on a cooldown, or he can vote again
        if claimed:
            if datetime.now() > date:
                await ctx.send(f"You can vote again! Go to: {self.vote_link}"
                               "\n to vote, and use the command again to claim your reward!")

            # If there is time left
            else:
                output = str(date - datetime.now())
                output = output[:output.find(".")].strip()
                await ctx.send(f"You can vote again in ``{output}`` hours", text=True)
            return

        # If we make it down here, we should be able to execute the voting benefits
        # TODO execute the functionality of the vote here
        flames = 2
        fame = 2
        await ctx.send("You successfully voted!", description=f"You claimed ``{flames} 🔥`` and ``{fame} fame``")
        await ctx.db.execute("UPDATE limits SET superlikes=superlikes+$1 WHERE member_id = $2", flames, ctx.author.id)
        await ctx.db.execute("UPDATE users SET fame=fame+$1 WHERE member_id = $2", fame, ctx.author.id)

        # Sets the claimed value back to True
        await ctx.db.execute("UPDATE voters SET claimed = $1 WHERE user_id = $2 AND bot_id = $3 AND type = $4", True,
                             ctx.author.id, bot_id, _type)
        del self.users[ctx.author.id]


def setup(bot):
    global logger
    logger = logging.getLogger('bot')
    bot.add_cog(VotingCog(bot))
