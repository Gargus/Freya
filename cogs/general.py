from discord.ext import commands


class GeneralCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command("limits")
    @commands.is_owner()
    async def limits(self, ctx):
        # Gets all the users
        users = await ctx.db.fetch("SELECT * FROM users")
        for user in users:
            await ctx.db.execute("INSERT INTO limits (member_id, likes, superlikes) VALUES ($1, $2, $3) ON CONFLICT (member_id) DO NOTHING", user["member_id"], 100, 1)
        print("Limits created for users")

    # TODO helper commands in json have hardcoded prefixes. Potential fix
    @commands.command(name="help")
    async def help(self, ctx):
        fields = []
        fields.append(("Patch notes", "Added claim command. You can now claim fame and more flames by voting"))
        fields.append(("Description", "This is the most advanced, if not the only proper matchmaking bot out there! Can be comparable to Tinder. Go ahead and play around with the commands."))
        fields.append(("Prefix", f"The prefix for all commands is `{ctx.prefix}`"))
        for cog_name in self.bot.cogs:
            cog = self.bot.get_cog(cog_name)
            commands = cog.get_commands()
            info_string = ""
            for command in commands:
                command_help = self.bot.json.db["command_helper"].get(command.name)

                # If we're not added the command in the json file, we jump to the next one
                if not command_help:
                    continue
                usage = command_help["usage"]
                description = command_help["description"]
                info_string += f"``{command.name} {usage}`` - " + description + "\n"

            name = cog_name.split("Cog")[0]
            if info_string:
                field = (name, info_string)
                fields.append(field)

        reactions = ""
        reactions+= "◀ - Browse to the previous image of the profile\n"
        reactions+= "▶ - Browse to the next image of the profile\n"
        reactions+= "⏏ - Toggles between display modes [Frame, Bio]\n"
        reactions+= "👍 - Upvotes an user. If you both upvote eachother you match!\n"
        reactions+= "👎 - Downvotes an user. I'd say the explanation is self-explanatory\n"
        reactions+= "🔥 - Set yourself on fire! [once per day] With this like, the one you used the flame on will know that you liked them!\n"
        reactions+= "<:redTick:600735269792120977> - Cancel the swiping process"
        fields.append(("Reactions", reactions))
        await ctx.send(
            "To invite this bot to your server, or to vote, visit this link: https://discordbots.org/bot/600024172726321171",
            fields=fields)

def setup(bot):
    bot.add_cog(GeneralCog(bot))