import asyncpg
from utils import utils
import io
from PIL import Image, ImageDraw, ImageFont
from sys import platform
from utils.image import OSDraw
import asyncio
import datetime
from dataclasses import dataclass
from utils.rendering import get_user_settings


# Handles the contrtuction and runs the co-routines required for
# a fully set-up Profile object
async def generate_profile(ctx, member_id=None):
    if not member_id:
        member_id = ctx.author.id
    record = await ctx.db.fetchrow("SELECT * FROM users LEFT JOIN limits USING (member_id) WHERE member_id = $1", member_id)
    if not record:
        return None
    profile = UserProfile(ctx, record)
    return profile


class Profile:
    def __init__(self, ctx):
        # Bot used for image cache
        self.member_id = None
        self.ctx = ctx
        self.images = self.ctx.bot.images
        self.reactions = ctx.bot.reactions

        # Used to generate image
        self.image_binaries = []
        self.index = 0
        self.render_settings = None

        self.pic_limit = 6

        self.age = None
        self.name = None
        self.sex = None
        self.preference = None
        self.country = None
        self.bio = None
        self.birth = None
        self.fame = None

        # 0 = BioMode, 1 = FrameMode
        self.mode = 0

    def calculate_age(self, birthdate):
        today = datetime.date.today()
        return today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))

    def swap_mode(self):
        self.mode = not self.mode

    def render_profile(self):
        images = self.images
        # Get the bio box if BioMode
        if self.mode == 0:
            image = Image.new('RGBA', (512, 850), color=0)

            biobox = self.images.get_image(*self.render_settings["biobox"])
            decor = self.images.get_image(*self.render_settings["decor"])
            self.apply_text(biobox)
            profile = self.generate_picture()
            sex = images.get_image("layout", self.sex)


            image.paste(profile, (0, 0), profile)
            image.paste(biobox, (0, 530))
            # Decor from settings
            if decor:
                image.paste(decor, (0, 0), decor)
            image.paste(sex, (410, 595), sex)
            self.apply_extra_text(image)

        # FrameMode
        elif self.mode == 1:
            # Dimensions for pasting
            x = 0
            y = 0

            image = Image.new('RGBA', (512, 850), color=(170, 68, 68))
            picture = self.generate_picture()

            # Calculate if positioning is needed
            h = picture.size[1]
            if h < 850:
                y = int(y+((850-h)/2))
            image.paste(picture, (x, y))
            frame = images.get_image("layout", "frame")
            image.paste(frame, (0, 0), frame)

        return image

    def remove_picture(self):
        del self.image_binaries[self.index]
        self.prev_index()

    def prev_index(self):
        self.index -= 1
        if self.index < 0:
            self.index = len(self.image_binaries)-1

    def next_index(self):
        self.index += 1
        if self.index > len(self.image_binaries) - 1:
            self.index = 0

    def load_picture(self):
        # Tries to obtain the image
        try:
            binary = self.image_binaries[self.index]
        except IndexError:
            raise IndexError("No image binary exists in the internal list")

        # Load the image binary from the indexed list
        buf = io.BytesIO(binary)
        buf.seek(0)
        picture = Image.open(buf)
        return picture

    def generate_picture(self):
        images = self.images
        profile = None

        picture = self.load_picture()

        # BioMode
        if self.mode == 0:

            # Coordinates
            y = 431
            x = 476

            # Get the border and the mask
            peach_border = images.get_image(*self.render_settings["border"])
            peach_mask2 = images.get_image("layout", "peach_mask")

            # Resize the picture
            resized = utils.resize_picture(picture, 476)

            # Crop the picture if needed
            h = resized.size[1]

            # No need to crop, but to get the image to the right dimensions
            if h < y:
                _y = int((y-h)/2)
                tmp = Image.new('RGBA', (x, y), color=self.render_settings["colors"]["bg"])
                tmp.paste(resized, (0, _y))
                resized = tmp

            # Do need to crop
            else:
                y_alignment = 50
                resized = resized.crop((0, y_alignment, x, y+y_alignment))
            # Create a picture with proper dimensions
            img = Image.new('RGBA', (512, 512), color=0)
            # Compose the profile picture
            comp = Image.composite(resized, peach_mask2, peach_mask2)
            # static values for position (shouldn't need changing)
            img.paste(comp, (18, 65))
            profile = Image.alpha_composite(img, peach_border)

        # FrameMode
        elif self.mode == 1:
            # No resizing needed as this is the default format from the database output
            profile = picture

        # TODO in case of memory leak. Check stuff here. Either close the image or check the reference above

        return profile

    async def deploy_reactions(self, message, *args, timer=60):
        reactions = []
        # Reaction modes, appends all the reactions
        # to add to the message
        for arg in args:
            for reaction in self.reactions[arg]:
                reactions.append(reaction)

        # Gets the reaction we pressed on the profile
        try:
            reaction = await utils.get_user_reaction(self.ctx, message, reactions, timer)
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError

        # translates the reaction
        self.translate_reaction(reaction)

        # Also returns it
        return reaction

    def translate_reaction(self, reaction):

        switcher = {
            "⏏": self.swap_mode,
            "◀": self.prev_index,
            "▶": self.next_index

        }
        func = switcher.get(reaction, lambda: None)
        func()

    def text_wrap(self, text, font, max_width):

        lines = []
        # If the width of the text is smaller than image width
        # we don't need to split it, just add it to the lines array
        # and return
        if font.getsize(text)[0] <= max_width:
            lines.append(text)
        else:
            # split the line by spaces to get words
            words = text.split(' ')
            i = 0
            # append every word to a line while its width is shorter than image width
            while i < len(words):
                line = ''
                while i < len(words) and font.getsize(line + words[i])[0] <= max_width:
                    line = line + words[i] + " "
                    i += 1
                if not line:
                    line = words[i]
                    i += 1
                # when the line gets longer than the max width do not append the word,
                # add the line to the lines array
                lines.append(line)
        return lines


    def apply_extra_text(self, image: Image):

        font_path = self.ctx.bot.fonts.get_font("AtlantisInternational")
        d = OSDraw(image)

        style = TextStyle(60, 174, 485, self.fame)

        font = ImageFont.truetype(font_path, style.font_size)

        #Draw Fame
        d.text((style.x, style.y), f"Fame {style.value}", font=font, fill=self.render_settings["colors"]["fame"])

    def apply_text(self, image: Image):
        font_path = self.ctx.bot.fonts.get_font("AtlantisInternational")
        font_path_dej = self.ctx.bot.fonts.get_font("OpenSansEmoji")
        d = OSDraw(image)
        bio_font = ImageFont.truetype(font_path_dej, 20)
        title_font = ImageFont.truetype(font_path, 60)

        color = "#4a1a1a"

        # Draw name
        d.text((60, 8), self.name.title(), font=title_font, fill=color)


        # Draw Age
        d.text((454, 8), str(self.age), font=title_font, fill=color)


        #Draw country
        d.text((60 , 59), self.country, font=title_font, fill=color)

        #Draw bio
        bio = self.bio.replace('\n', ' ').replace('\r', ' ')
        lines = self.text_wrap(bio, bio_font, 480)
        line_height = bio_font.getsize('hg')[1]
        x = 25
        y = 120
        if platform == "linux" or platform == "linux2":
            y += 7
        for line in lines:
            d.text((x, y), line, fill=color, font=bio_font)
            y = y + line_height

class TextStyle(object):
    def __init__(self, font_size: int, x: int, y: int, value: int):
        self.font_size = font_size
        self.x = x
        self.y = y
        self.value = value
        self.adjust()

    def adjust(self):
        if self.value is None:
            self.value = ""
            return
        length = len(str(self.value))
        if length > 2:
            for _ in range(length-2):
                self.font_size-=8
                self.y += 5


class Prefile(Profile):
    def __init__(self, ctx):
        super().__init__(ctx)
        self.render_settings = get_user_settings(ctx.author.id)
        self.birth = None
        self.categories_left = ctx.cog.categories.copy()

    def copy(self, profile: Profile):
        self.name = profile.name
        self.age = profile.age
        self.birth = profile.birth
        self.country = profile.country
        self.bio = profile.bio
        self.sex = profile.sex
        self.preference = profile.preference
        self.image_binaries = profile.image_binaries.copy()


class UserProfile(Profile):
    def __init__(self, ctx, record: asyncpg.Record):
        super().__init__(ctx)
        self.member_id = record["member_id"]
        self.render_settings = get_user_settings(self.member_id)

        # Attributes for the User object (Needs to be constructed with the data fetched from the database)
        self.fame = record["fame"]
        self.created_at = record["created_at"]

        self.sex = record["sex"]
        self.preference = record["preference"]
        self.birth = record["birth"]
        self.age = self.calculate_age(record["birth"])
        self.name = record["name"]
        self.country = record["country"]
        self.bio = record["bio"]

        # Like limits
        self.likes = record.get("likes")
        self.superlikes = record.get("superlikes")
        # These will have a value if it has been fetched when swiping
        self.compat = record.get("compat")

        # if we're using a specific filter
        self.filter = record.get("filter")

    def __str__(self):
        # Override to print a readable string presentation of your object
        # below is a dynamic way of doing this without explicity constructing the string manually
        keys = self.__dict__.copy()
        del keys["image_binaries"]
        del keys["ctx"]
        del keys["reactions"]
        return ', '.join(['{key}={value}'.format(key=key, value=self.__dict__.get(key)) for key in keys])

    async def _fetch_pictures(self):
        record = await self.ctx.db.fetch("SELECT * FROM pictures WHERE member_id = $1", self.member_id)
        return record

    async def fetch_pictures(self):
        record = await self._fetch_pictures()
        for image in record:
            self.image_binaries.append(image["image"])


