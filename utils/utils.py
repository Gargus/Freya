import io
import datetime
import discord
import asyncio
from PIL import Image


def get_payload(img, gif=False):
    buf = io.BytesIO()
    if gif:
        img[0].save(buf, 'gif', save_all=True, append_images=img[1:], duration=100, loop=0)
        buf.seek(0)
        file = discord.File(buf, filename=str(datetime.datetime.now()) + "." + "gif")

    else:
        img.save(buf, 'png')
        buf.seek(0)
        file = discord.File(buf, filename=str(datetime.datetime.now()) + "." + "png")
    buf.close()
    return file

def resize_picture(picture, basewidth):
    img = picture
    wp = (basewidth / float(img.size[0]))
    hs = int((float(img.size[1]) * float(wp)))
    resized = img.resize((basewidth, hs), Image.ANTIALIAS)
    return resized

async def get_user_image_url(ctx, message, timer=60):
    def check(m):
        return m.author == ctx.author and m.channel == message.channel

    while True:
        try:
            msg = await ctx.bot.wait_for('message', check=check, timeout=timer)

        # If the process timed out
        except asyncio.TimeoutError:
            await attempt_delete(message)
            return None

        if msg.content.lower() == "exit":
            await attempt_delete(message)
            return None

        if not msg.attachments:
            await attempt_delete(message)
            message = await ctx.send(message.embeds[0].title,
                                     footer="If you want to cancel the process, type: exit",
                                     field=("Invalid data input. You need to post a image", msg.content))
            continue

        # Tried to remove the image posted, this will fail if the user registration process
        # is being performed in a DM channel
        # Returns the binary data
        await attempt_delete(message)

        if not msg.attachments[0].url:
            return msg.attachments[0].proxy_url
        return msg.attachments[0].url

async def get_user_reaction(ctx, message, reactions, timer):
    # Adds the reactions to the message
    for reaction in reactions:
        await message.add_reaction(reaction)

    # Checks if the user pressed any of the reactions
    def check(reaction, user):
        if user == ctx.author and reaction.message.id == message.id:
            if str(reaction.emoji) in reactions:
                return True

    # Gathers the reaction
    try:
        reaction, user = await ctx.bot.wait_for('reaction_add', timeout=timer, check=check)
    except asyncio.TimeoutError:
        raise asyncio.TimeoutError

    # Returns the reaction the user reacted to
    await message.delete()
    return reaction.emoji

async def attempt_delete(message):
    try:
        await message.delete()
    except Exception:
        return False
    else:
        return True