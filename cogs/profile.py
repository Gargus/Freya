from discord.ext import commands
import re
import asyncio
import io
from PIL import Image
import datetime
from utils.utils import get_user_reaction, attempt_delete, resize_picture, get_payload
from utils.profile import Prefile, UserProfile, generate_profile
from country_list import countries_for_language
from utils.command import RestrictedCommand, DMRestrictedCommand, DMCommand
from utils.errors import DublicationError


class ProfileCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.timer = 300
        self.patterns = {"number": "^[1-9][0-9]?$|^100$",
                         "text": "^[a-zA-Z][A-Za-z' ]+$",
                         "date": "^(19|[2-9][0-9])\d{2}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$"
        }
        self.categories = ["name", "birth", "country", "sex", "preference", "bio", "images"]
        self.reactions = bot.reactions
        self.translate = bot.translate
        self.countries = self.setup_countries()
        self.activity = {}

    def setup_countries(self):
        countries = []
        for i, country in enumerate(countries_for_language('en')):
            # This is the country with spaces and capital letters
            countries.append(country[1])
        return countries

    async def _add_picture(self, ctx, binary, order):
        # Pushes the picture data into the database
        query = "INSERT INTO pictures (member_id, image, ordered, date) VALUES ($1, $2, $3, $4)"
        await ctx.db.execute(query, ctx.author.id, binary, order, datetime.datetime.now())

    async def _add_user(self, ctx, profile):
        # Extract all the info to push into the database
        bio = profile.bio
        name = profile.name
        country = profile.country
        age = profile.birth
        sex = profile.sex
        preference = profile.preference

        # Gather the binaries, and convert them to a smaller format
        for i, binary in enumerate(profile.image_binaries):
            # Push each picture to the database
            await self._add_picture(ctx, binary, i)

        # Execute user add query
        query = "INSERT INTO users (bio, name, country, birth, member_id, fame, created_at, sex, preference, filter) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)"
        query += " ON CONFLICT (member_id) DO NOTHING"
        result = await ctx.db.execute(query, bio, name, country, age, ctx.author.id, 0, datetime.datetime.now(), sex, preference, "global")
        result = result.split(" ")
        if result[2] == '0':
            raise DublicationError("Another profile from the same user was attempted to be added.")

        # Add limits entry
        # TODO might want to change the likes and superlike values, as they're now static and not dynamic
        query = "INSERT INTO limits (member_id, likes, superlikes) VALUES ($1, $2, $3) ON CONFLICT (member_id) DO NOTHING"
        await ctx.db.execute(query, ctx.author.id, 100, 1)

        # Also add the user to the internal user cache
        self.bot.cache.append("users", ctx.author.id)

        #Now add the user to every guild the bot and the user is in
        await self.add_into_guilds(ctx)

    async def add_into_guilds(self, ctx):
        # Iterates through every guild the bot is in
        for guild in self.bot.guilds:
            # checks if the member exist in the guild
            member = guild.get_member(ctx.author.id)
            #if he does, we add the data to the database and the cache
            if member:
                if guild.id not in self.bot.cache._db["guilds"]:
                    self.bot.cache._db["guilds"][guild.id] = []
                #Insert into database
                await ctx.db.execute("INSERT INTO guilds (member_id, guild_id) VALUES ($1, $2) ON CONFLICT (member_id, guild_id) DO NOTHING", ctx.author.id, guild.id)
                # Insert into cache
                self.bot.cache._db["guilds"][guild.id].append(ctx.author.id)


    # Updates the entry according to the user_data input
    async def _update_profile(self, ctx, p):
        #Removes the old pictures
        query = "DELETE FROM pictures WHERE member_id = $1"
        await ctx.db.execute(query, ctx.author.id)

        # Adds in the new ones
        for i, binary in enumerate(p.image_binaries):
            await self._add_picture(ctx, binary, i)

        query = "UPDATE users SET name = $1, birth = $2, country = $3, bio = $4, sex = $5, preference = $6 WHERE member_id = $7"
        await ctx.db.execute(query, p.name, p.birth, p.country, p.bio, p.sex, p.preference, ctx.author.id)

    def get_category(self, category: str):
        func = getattr(self, "get_"+category, None)
        if func is None:
            print("Category function does not exist!")
        return func

    async def get_sex(self, ctx, profile):
        sexs = ["male", "female", "male-to-female", "female-to-male"]
        tmp = ""
        for sex in sexs:
            tmp += f"``{sex}``\n"

        message = await ctx.send("Enter your sex",
                                 footer="Select one of the options listed. Trans options are now available too.", field=("Options:", tmp))
        sex = await self.get_user_data(ctx, message, listed=sexs)
        if sex:
            profile.sex = sex
            return True
        return False

    async def get_preference(self, ctx, profile):
        tmp = ""
        preferences = ["males", "females", "both"]
        for preference in preferences:
            tmp += f"``{preference}``\n"
        message = await ctx.send("Enter your matching preference",
                                 footer="Your pick here decides what sex you will be swiping on [Can be changed later]", field=("Options:", tmp))
        preference = await self.get_user_data(ctx, message, listed=preferences)
        if preference:
            profile.preference = preference
            return True
        return False

    async def get_name(self, ctx, profile):
        message = await ctx.send("Enter your name",
                                 footer="No special characters or numbers allowed [Max: 15 characters]")
        name = await self.get_user_data(ctx, message, self.patterns["text"], limit=15)
        if name:
            profile.name = name
            return True
        return False

    async def reset_entries(self, ctx):
        query = "DELETE FROM entries WHERE member_id = $1 or target_id = $1"
        await ctx.db.execute(query, ctx.author.id)

    async def get_birth(self, ctx, profile):
        message = await ctx.send("Enter your date of birth", footer="Follow this format: yyyy-mm-dd [Ex: 1998-04-01]")
        date = await self.get_user_data(ctx, message, self.patterns["date"])


        # Datetime of when the user is born
        if date:
            date = date.split("-")
            date_time = datetime.datetime(int(date[0]), int(date[1]), int(date[2]))
            profile.birth = date_time

            # Do the age check. Delete data if age groups has changed
            age = profile.calculate_age(date_time)
            if profile.age:
                if profile.age < 18:
                    if age >= 18:
                        await self.reset_entries(ctx)
                elif profile.age >= 18:
                    if age < 18:
                        await self.reset_entries(ctx)

            profile.age = profile.calculate_age(date_time)
            return True
        return False

    async def get_country(self, ctx, profile):
        common_locations = ["United States", "United Kingdom", "Australia"]
        tmp = ""
        for location in common_locations:
            tmp += f"``{location}``\n"
        field = ("Common locations", tmp)
        message = await ctx.send("Enter your country", footer="No special characters or numbers allowed [Max: 20 characters]", field=field)
        country = await self.get_user_data(ctx, message, listed=self.countries)
        if country:
            profile.country = country
            return True
        return False


    async def get_bio(self, ctx, profile):
        message = await ctx.send("Enter a biography", footer="Any text allowed [Max: 250 characters]")
        bio = await self.get_user_data(ctx, message, limit=250)
        if bio:
            profile.bio = bio
            return True
        return False

    def resize(self, image_bin, basewidth):
        buf = io.BytesIO(image_bin)
        buf.seek(0)
        img = Image.open(buf)
        resized = resize_picture(img, basewidth)
        buf2 = io.BytesIO()
        resized.save(buf2, format="png")
        return buf2.getvalue()


    async def get_images(self, ctx, profile):
        image_binaries = profile.image_binaries
        while len(image_binaries) < 6:
            message = await ctx.send("Post a picture to upload for your profile",
                                     footer=f"Drag or upload an image to this channel [Max {profile.pic_limit} images; 1 at a time]")
            image_bin = await self.get_user_data(ctx, message, image=True)

            # Get the image from the user (and also resize it)
            if image_bin:
                resized = self.resize(image_bin, 512)
                image_binaries.append(resized)

            # Check if the user want to upload another
            message = await ctx.send("Would you like to upload another picture?",
                                     footer=f"Use the reactions to confirm your decision [Images: {len(image_binaries)}/6]")
            try:
                reaction = await get_user_reaction(ctx, message, self.reactions["boolean"], self.timer)
            except asyncio.TimeoutError:
                await ctx.send("Timed out. Command cancelled")
                return False

            # Translates the reaction to a value (in this case boolean)
            if self.translate[reaction.name]:
                continue
            break

        return True

    async def update_images(self, ctx, profile):
        options = ["add"]

        # Should only be able to remove if the images exceeds 1
        if len(profile.image_binaries) > 1:
            options.append("remove")

        tmp = ""
        for option in options:
            tmp += f"``{option}``\n"
        message = await ctx.send("What would you like to do with your images?", footer="If you're maximum image limit is reached, you need to remove some before you add new ones. You need minimum 1 picture", description=tmp)
        data = await self.get_user_data(ctx, message, listed=options)
        if data == "add":
            result = await self.get_images(ctx, profile)
        elif data == "remove":
            result = await self.remove_image(ctx, profile)
        return result

    async def remove_image(self, ctx, profile):
        profile.mode = 1
        while len(profile.image_binaries) > 1:
            picture = profile.render_profile()
            message = await ctx.send(f"{ctx.author}, do you want to remove this picture?\n*Use the arrows to browse through images*", file=get_payload(picture), text=True)

            try:
                reaction = await profile.deploy_reactions(message, "arrows", "ticks", timer=self.timer)
            except asyncio.TimeoutError:
                await attempt_delete(message)
                return False
            try:
                status = self.translate.get(reaction.name)
            except Exception:
                continue

            if status:
                profile.remove_picture()
                break
            elif status is not None:
                break
        return True



    async def update_profile(self, ctx, profile):
        tmp = ""

        for category in self.categories:
            tmp += f"``{category}``\n"
        field = ("Categories:", tmp)
        message = await ctx.send("What would you like to change?", field=field, footer="Enter the name of the category that you want to change")
        data = await self.get_user_data(ctx, message, listed=self.categories)

        # We run this differently when we're updating the profile
        if data == "images":
            func = getattr(self, "update_"+data)
        elif data is not None:
            func = getattr(self, "get_"+data)
        else:
            return False

        if not (await func(ctx, profile)):
            return False
        profile.mode = 0
        return True


    async def profile_discord(self, ctx):
        prefile = Prefile(ctx)

        # Set the name
        name = ctx.author.display_name
        if len(name) > 15:
            name = name[:15]

        prefile.name = name
        prefile.categories_left.remove("name")

        # Set the image
        avatar_asset = ctx.author.avatar_url_as()
        avatar = await avatar_asset.read()
        prefile.image_binaries.append(self.resize(avatar, 512))
        prefile.categories_left.remove("images")

        return prefile

    async def profile_selection(self, ctx):
        options = ["custom", "discord"]
        tmp = ""
        for option in options:
            tmp += f"``{option}``\n"
        field = ("Options:", tmp)
        message = await ctx.send("You now have two options. Customize profile fully, or have it slightly adapted by your discord profile.", field=field, footer="You can change the settings after your profile is done no matter what option you started with!")
        creation = await self.get_user_data(ctx, message, listed=options)
        if creation:
            if creation == "discord":
                prefile = await self.profile_discord(ctx)
            elif creation == "custom":
                prefile = Prefile(ctx)
            return prefile

    @commands.command(name="create", cls=DMRestrictedCommand)
    async def create(self, ctx):
        if ctx.profile:
            await ctx.send("You've already created a profile", footer=f"Use {ctx.prefix}profile to display your profile or {ctx.prefix}edit to change it")
            return

        # Obtains the prefile. Can contain data already
        prefile = await self.profile_selection(ctx)
        if not prefile:
            return

        # Gather all the category data needed
        for category in prefile.categories_left:
            func = self.get_category(category)
            if not func:
                return
            if not (await func(ctx, prefile)):
                return

        while True:
            profile = prefile.render_profile()
            message = await ctx.send(f"**{ctx.author}**, are you happy with your profile?\n*Use the ticks to confirm your decision.*", file=get_payload(profile), text=True)

            # Deploys reactions to the image that are interactable
            # and affects the profile behaviour
            try:
                reaction = await prefile.deploy_reactions(message, "arrows", "toggle", "ticks", timer=self.timer)
            except asyncio.TimeoutError:
                await attempt_delete(message)
                return

            # If the user used an option that doesn't "rotate" the images
            if str(reaction) in prefile.reactions["ticks"]:
                await attempt_delete(message)

                # Profile as deemed good
                if self.translate.get(reaction.name):

                    # All data should have been gathered here, and we shall now push it to the database
                    try:
                        await self._add_user(ctx, prefile)
                    except DublicationError as e:
                        await ctx.send("Profile already exists. Discarding!")
                        raise e

                    await ctx.send("Profile was successfully created!", footer=f"Use {ctx.prefix}profile to display it")
                    print(ctx.author, "Created a profile", "in", ctx.guild, "in", ctx.channel)
                    break

                # Profile was not deemed good
                else:
                    await self.update_profile(ctx, prefile)
                    continue

    @commands.command(name="delete")
    async def delete(self, ctx):
        # Remove from Guilds, Users and Limits
        message = await ctx.send("Are you sure you want to delete your profile?")
        reaction = await get_user_reaction(ctx, message, self.bot.reactions["boolean"], self.timer)
        # TODO might want to put this into 1 query if we're suffering performance issues

        # Deletes all the records of the user
        if self.bot.translate[reaction.name]:
            await ctx.db.execute("DELETE FROM users WHERE member_id = $1", ctx.author.id)
            await ctx.db.execute("DELETE FROM limits WHERE member_id = $1", ctx.author.id)
            await ctx.db.execute("DELETE FROM guilds WHERE member_id = $1", ctx.author.id)
            await ctx.db.execute("DELETE FROM pictures WHERE member_id = $1", ctx.author.id)
            # Also remove from caches
            for guild in self.bot.guilds:
                if ctx.author.id in self.bot.cache._db["guilds"][guild.id]:
                    self.bot.cache._db["guilds"][guild.id].remove(ctx.author.id)
            self.bot.cache._db["users"].remove(ctx.author.id)
            await ctx.send("Profile was successfully deleted!", footer=f"If you want to create a new profile, use {ctx.prefix}create")

    @commands.command(name="matches", cls=DMRestrictedCommand)
    async def matches(self, ctx):
        query = '''SELECT * FROM users LEFT JOIN matches ON users.member_id = matches.source_id OR users.member_id = matches.target_id
                    WHERE (matches.source_id = $1 OR matches.target_id = $1) AND users.member_id != $1 ORDER BY matches.date DESC'''
        matches = await ctx.db.fetch(query, ctx.author.id)
        if not matches:
            await ctx.send("You have no matches as of now!")
            return

        users = []
        for match in matches:
            users.append(UserProfile(ctx, match))

        index = 0
        while True:

            # Index handling
            if index < 0:
                index = len(users)-1
            elif index>=len(users):
                index = 0

            # The profile
            pf = users[index]
            await pf.fetch_pictures()

            while True:
                profile = pf.render_profile()
                payload = get_payload(profile)
                user = self.bot.get_user(pf.member_id)
                if not user:
                    user = "User not found, sorry!"
                profile_msg = await ctx.send(f"**({index+1}/{len(users)})** You've matched with: **{user}**", file=payload, text=True)

                # Deploys reactions to the image that are interactable
                # and affects the profile behaviour
                try:
                    reaction = await pf.deploy_reactions(profile_msg, "arrows", "toggle", "pager","cancel", timer=self.timer)
                except asyncio.TimeoutError:
                    await attempt_delete(profile_msg)
                    return
                if str(reaction) == "⏪":
                    index-=1
                    break
                if str(reaction) == "⏩":
                    index+=1
                    break
                if str(reaction) == "<:redTick:600735269792120977>":
                    return

    @commands.command(name="filter")
    async def filter(self, ctx):
        filters = ["server", "global"]
        descriptions = ["filter that only lets you swipe on members of the server", "filter that lets you swipe on members across all servers"]
        tmp = ""
        for filter, description in zip(filters, descriptions):
            tmp += "``{}`` - {}\n".format(filter, description)
        field = ("Filters", tmp)
        message = await ctx.send("Enter the filter you want to activate",
                                 footer="Selecting the filter you're already using has no effect", field=field, description=f"Current filter: **{ctx.profile.filter}**")
        filter = await self.get_user_data(ctx, message, listed=filters)
        if filter:
            # Updates the filter value
            await ctx.db.execute("UPDATE users SET filter = $1 WHERE member_id = $2", filter, ctx.author.id)
            await ctx.send("Filter was successfully activated!", footer=f"Use {ctx.prefix}swipe to start swiping!")

    @commands.command(name="edit", cls=DMRestrictedCommand)
    async def update(self, ctx):
        prefile = Prefile(ctx)

        # Copy data from profile to testing profile (used for displaying before making the actual change)
        prefile.copy(ctx.profile)
        if not (await self.update_profile(ctx, prefile)):
            return

        # Loops through until the user is happy
        while True:
            profile = prefile.render_profile()
            message = await ctx.send(f"**{ctx.author}**, are you happy with your profile?\n*Use the ticks to confirm your decision.*", file=get_payload(profile), text=True)

            # Deploys reactions to the image that are interactable
            # and affects the profile behaviour
            try:
                reaction = await prefile.deploy_reactions(message, "arrows", "toggle", "ticks", timer=self.timer)
            except asyncio.TimeoutError:
                await attempt_delete(message)
                return

            # If the user used an option that doesn't "rotate" the images
            if str(reaction) in prefile.reactions["ticks"]:
                await attempt_delete(message)

                # Profile as deemed good
                if self.translate.get(reaction.name):
                    await ctx.send("Profile was successfully updated!", footer=f"Use {ctx.prefix}profile to display it")
                    break
                # Profile was not deemed good
                else:
                    if not (await self.update_profile(ctx, prefile)):
                        return
                    continue

        # Once here we push the actual changes to the database
        await self._update_profile(ctx, prefile)

    @commands.command(name="profile")
    async def profile(self, ctx):
        # Loads the profile

        # TODO this shit might leak still. Make sure to check in case it does

        # Fetches the image binaries
        while True:

            image = ctx.profile.render_profile()
            payload = get_payload(image)

            profile_msg = await ctx.send("", file=payload, text=True)

            # Deploys reactions to the image that are interactable
            # and affects the profile behaviour

            try:
                reaction = await ctx.profile.deploy_reactions(profile_msg, "arrows", "toggle", "cancel", timer=self.timer)
            except asyncio.TimeoutError:
                await attempt_delete(profile_msg)
                break
            if str(reaction) == "<:redTick:600735269792120977>":
                break

    def country_helper(self, content, countries, attempts):
        comp = len(content)-attempts
        while True:
            if comp < 1:
                comp = 1
            search = content[:comp]
            start_str = "*Did you mean...*\n\n"
            tmp = ""

            for country in countries:
                if country.lower().startswith(search):
                    tmp += f"``{country}``\n"
            if not tmp:
                comp-=1
            else:
                break

        return start_str+tmp

    async def get_user_data(self, ctx, message, pattern=False, image=False, limit=False, listed=False):

        # Checks if the input data is from the same user
        # As the one who executed the command
        def check(m):
            return m.author == ctx.author and m.channel == message.channel

        attempts = 0
        # Loops that runs until correct data is provided, or timeout
        while True:
            try:
                msg = await self.bot.wait_for('message', check=check, timeout=self.timer)

            # If the process timed out
            except asyncio.TimeoutError:
                await attempt_delete(message)
                return None

            if msg.content.lower() == "exit":
                await attempt_delete(message)
                return None

            # If we're looking for listed data
            if listed:
                content = msg.content.lower()
                for entry in listed:
                    if content == entry.lower():
                        await attempt_delete(message)
                        return entry

                # If the list passed is greater than 10, it is currently the countries
                tmp = ""
                if len(listed) > 10:
                    tmp = self.country_helper(content, listed, attempts)
                else:
                    for _ in listed:
                        tmp += f"``{_}``\n"
                exit_str = "If you want to cancel the process, type: ``exit``"
                await attempt_delete(message)
                message = await ctx.send(message.embeds[0].title,
                                         footer=message.embeds[0].footer.text,
                                         fields=[("Invalid data input", msg.content), ("Cancelling", exit_str)],
                                         description=tmp)
                attempts += 1
                continue

            # If we're looking for non-image data
            if not image:

                # If a pattern exists
                if pattern:

                    # Checks if the data that was sent it of the correct type
                    result = re.match(pattern, msg.content)
                    if not result:
                        await attempt_delete(message)
                        exit_str = "If you want to cancel the process, type: exit"
                        message = await ctx.send(message.embeds[0].title, footer=message.embeds[0].footer.text, fields=[("Invalid data input", msg.content), ("Cancelling", exit_str)])
                        continue

                    # Checks if the data is longer than the character limit or not
                    data = result.group(0)

                # If no pattern, add all the content
                else:
                    data = msg.content

                if limit:
                    if len(data) > limit:
                        await attempt_delete(message)
                        exit_str = "If you want to cancel the process, type: exit"
                        message = await ctx.send(message.embeds[0].title,
                                                 footer=message.embeds[0].footer.text,
                                                 fields=[("Invalid data input", msg.content), ("Cancelling", exit_str)])
                        continue


                # If the data was correct, we return the result
                await attempt_delete(message)
                return data

            # If we're looking for image data
            else:

                # If there is no image in the message
                if not msg.attachments:
                    await attempt_delete(message)
                    message = await ctx.send(message.embeds[0].title,
                                             footer="If you want to cancel the process, type: exit",
                                             field=("Invalid data input", msg.content))
                    continue

                buf = io.BytesIO()

                # Saves the image data to a buffer so we can return the binary data for database storage
                await msg.attachments[0].save(buf, seek_begin=True, use_cached=True)

                # Tried to remove the image posted, this will fail if the user registration process
                # is being performed in a DM channel
                await attempt_delete(msg)

                # Returns the binary data
                await attempt_delete(message)
                return buf.getvalue()


def setup(bot):
    bot.add_cog(ProfileCog(bot))
