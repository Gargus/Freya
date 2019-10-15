from discord.ext import commands


class StatsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="stats")
    @commands.is_owner()
    async def stats(self, ctx):
        print("Amount of guilds:", len(self.bot.guilds))
        print("Amount of users:", len(self.bot.users))

    @commands.command(name="guilds")
    @commands.is_owner()
    async def servers(self, ctx, amount: int):
        sorted_guilds = sorted(self.bot.guilds, key=lambda x: x.member_count, reverse=True)
        string = ""
        for i in range(amount):
            try:
                guild = sorted_guilds[i]
                string += f"{guild.name} | {guild.member_count} | {guild.id}\n"

            except Exception:
                pass
        await ctx.send("Guilds", description=string)


def setup(bot):
    bot.add_cog(StatsCog(bot))
