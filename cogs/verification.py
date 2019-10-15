from discord.ext import commands
from utils.utils import get_user_reaction, get_user_image_url
import discord


class VerificationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.timer = 300

    @commands.command(name="verify")
    async def verification(self, ctx):
        requirements = ["Picture of yourself", "Date of birth", "Current date", "Discord tag"]
        tmp = ""
        for req in requirements:
            tmp += f"``{req}``\n"
        field = ("Requirements", tmp)
        message = await ctx.send("Verification", description="To get verified within the bot, you need to send a picture of yourself, containing a written text with specific information information", field=field, footer="Upload the image to this chat. Press the 'X' to exit")

        url = await get_user_image_url(ctx, message, self.timer)
        # Hub server guild
        guild = self.bot.get_guild(self.bot.home_guild_id)
        # verification-request channel
        channel = guild.get_channel(611962429139714069)

        embed = discord.Embed(title="Verification", description=f"", colour=0xd89a88)
        embed.set_author(name=f"{ctx.author} | {ctx.author.id}", icon_url=ctx.author.avatar_url)
        embed.set_image(url=url)
        await channel.send("", embed=embed)

    # Used for automatically verify users
    @commands.Cog.listener("on_raw_reaction_add")
    async def on_raw_reaction_add(self, payload):
        pass



def setup(bot):
    bot.add_cog(VerificationCog(bot))
