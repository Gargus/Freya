from discord.ext import commands
def check_if_op(ctx):
    if ctx.author.id == ctx.bot.owner_id:
        return True
    perms = {'manage_guild': True}
    ch = ctx.channel
    permissions = ch.permissions_for(ctx.author)
    missing = [perm for perm, value in perms.items() if getattr(permissions, perm, None) != value]

    if not missing:
        return True
    else:
        return False


def check_if_donor(ctx):
    if ctx.donor:
        return True
    raise commands.CheckFailure("donor")