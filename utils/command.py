from discord.ext import commands
from discord.ext.commands.core import hooked_wrapped_callback
import discord.ext.commands.errors as errors
from utils.errors import RestrictionError

class RestrictedCommand(commands.Command):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def invoke(self, ctx):

        await self.prepare(ctx)

        # terminate the invoked_subcommand chain.
        # since we're in a regular command (and not a group) then
        # the invoked subcommand is None.
        ctx.invoked_subcommand = None
        injected = hooked_wrapped_callback(self, ctx, self.callback)


        # Checks if the user is already executing this command.
        # If that is true, we throw an exception
        if not ctx.bot.restricted.get(ctx.author.id):
            ctx.bot.restricted[ctx.author.id] = {}
        restrict = ctx.bot.restricted[ctx.author.id].get(self.name, None)
        if restrict:
            raise RestrictionError("Cannot use the command multiple times")
        else:
            ctx.bot.restricted[ctx.author.id][self.name] = True

        await injected(*ctx.args, **ctx.kwargs)

        # Once the command has been terminated, we clear the restriction
        ctx.bot.restricted[ctx.author.id][self.name] = False

class DMCommand(commands.Command):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def invoke(self, ctx):
        await self.prepare(ctx)

        # terminate the invoked_subcommand chain.
        # since we're in a regular command (and not a group) then
        # the invoked subcommand is None.
        ctx.invoked_subcommand = None
        injected = hooked_wrapped_callback(self, ctx, self.callback)

        #Does the DM channel stuff
        dm_channel = ctx.author.dm_channel
        if not dm_channel:
            await ctx.author.create_dm()
        if ctx.channel != dm_channel:
            await ctx.channel.send(
                f"{ctx.author.mention}, I sent you a DM.\n*If you didn't receive it, correct your account settings*")
        ctx.set_channel(ctx.author.dm_channel)
        await injected(*ctx.args, **ctx.kwargs)

class DMRestrictedCommand(RestrictedCommand):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def invoke(self, ctx):

        await self.prepare(ctx)

        # terminate the invoked_subcommand chain.
        # since we're in a regular command (and not a group) then
        # the invoked subcommand is None.
        ctx.invoked_subcommand = None
        injected = hooked_wrapped_callback(self, ctx, self.callback)


        # Checks if the user is already executing this command.
        # If that is true, we throw an exception
        if not ctx.bot.restricted.get(ctx.author.id):
            ctx.bot.restricted[ctx.author.id] = {}
        restrict = ctx.bot.restricted[ctx.author.id].get(self.name, None)
        if restrict:
            raise RestrictionError("Cannot use the command multiple times")
        else:
            ctx.bot.restricted[ctx.author.id][self.name] = True

        # Changes the channel to the DM channel

        dm_channel = ctx.author.dm_channel
        if not dm_channel:
            await ctx.author.create_dm()
        if ctx.channel != dm_channel:
            await ctx.channel.send(f"{ctx.author.mention}, I sent you a DM.\n*If you didn't receive it, correct your account settings*")
        ctx.set_channel(ctx.author.dm_channel)
        await injected(*ctx.args, **ctx.kwargs)

        # Once the command has been terminated, we clear the restriction
        ctx.bot.restricted[ctx.author.id][self.name] = False
