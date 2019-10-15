from discord.ext import commands
from utils.utils import get_user_reaction, get_user_image_url, get_payload, resize_picture
from PIL import Image, ImageSequence
import discord
from utils.cache import ImageCache
import io
import random
import time

class ImageCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.images = self.bot.images


    async def generate_avatar(self, size, user):
        # Obtain the profile image
        start = time.time()
        avatar_asset = user.avatar_url_as(format='webp')

        # Avatar binary
        avatar = await avatar_asset.read()

        # Resize it
        buf = io.BytesIO(avatar)
        buf.seek(0)
        img = Image.open(buf)
        resized = resize_picture(img, size)
        return resized

    async def generate_gif(self, mapping, user):
        start = time.time()
        # Obtains random mapping
        name = None
        suffix = random.randint(0, len(mapping)-1)
        for i, key in enumerate(mapping.keys()):
            # Take the random mapping
            if i == suffix:
                name = key

        gif = self.images.get_image("gifs", name)
        index = 1
        pos = None
        frames = []

        # Obtains the size
        size = mapping[name]["size"]

        # Obtains the resized avatar
        resized = await self.generate_avatar(size[0], user)
        resized.putalpha(190)

        # Iterate over each frame
        for frame in ImageSequence.Iterator(gif):

            # See if it can get a new position, otherwise run with the old one
            rep_pos = mapping[name]["positions"].get(str(index))
            if rep_pos is not None:
                pos = rep_pos

            frame = frame.convert('RGBA')

            frame.paste(resized, pos, resized)
            frames.append(frame)
            index += 1

        return get_payload(frames, gif=True)

    @commands.command(name="loveme")
    async def love_me(self, ctx, member: discord.Member):
        mapping = {
            "loveme_0": {
                "positions": {
                    "1": (87, 35),
                    "3": (87, 36),
                    "5": (87, 37),
                    "12": (88, 37),
                    "13": (90, 37),
                    "14": (91, 37)
                },
                "size": (115, 115)
            }
        }
        file = await self.generate_gif(mapping, member)
        await ctx.send("", file=file, text=True)


def setup(bot):
    bot.add_cog(ImageCog(bot))
