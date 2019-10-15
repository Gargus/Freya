from discord.ext import commands
import utils.checks as checks

class Prefix(commands.Converter):
    async def convert(self, ctx, argument):
        user_id = ctx.bot.user.id
        if argument.startswith((f'<@{user_id}>', f'<@!{user_id}>')):
            raise commands.BadArgument('That is a reserved prefix already in use.')
        return argument

class SettingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="prefixswap")
    @commands.check(checks.check_if_op)
    async def prefix_add(self, ctx, pref: Prefix):
        try:
            await self.bot.set_guild_prefix(ctx.guild, pref)
        except Exception as e:
            print(e, "error")
        else:
            status = await ctx.db.execute("UPDATE prefix SET prefix = $1 WHERE guild_id = $2", pref, ctx.guild.id)
            if str(status) == "UPDATE 0":
                await ctx.db.execute("INSERT INTO prefix (guild_id, prefix) VALUES ($1, $2)", ctx.guild.id, pref)
            await ctx.send(f"You successfully changed your prefix to: ``{pref}``")


def setup(bot):
    bot.add_cog(SettingCog(bot))
