from discord.ext import commands
from utils.command import RestrictedCommand
from utils.profile import UserProfile, generate_profile
from datetime import datetime, timedelta
import utils.errors as errors
from utils.filters import Filter, GlobalFilter, ServerFilter
from utils.rendering import RenderSettings
import asyncpg
from utils.utils import get_payload, attempt_delete, resize_picture
import asyncio
from PIL import Image
import io
import discord




class SwipeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.images = bot.images
        self.timer = 300
        self.bot.loop.create_task(self.limit_filler())

    async def limit_filler(self):
        # TODO Resetting procedures might be different per user, so make sure to implement that later
        while True:
            async with self.bot.pool.acquire() as c:
                await c.execute("UPDATE limits SET likes = $1, superlikes = $2", 100, 1)
            # Resets limits every 24h
            await asyncio.sleep(86400)

    async def _fetch_user(self, ctx, user_id):
        query = "SELECT * FROM users WHERE member_id = $1"
        record = await ctx.db.fetchrow(query, user_id)
        return record

    async def fetch_user(self, ctx, user_id):
        record = await self._fetch_user(ctx, user_id)
        if not record:
            print("User could not be found")
            return None

        user = UserProfile(ctx, record)
        await user.fetch_pictures()
        return user

    def heartify(self, binary):
        match_mask = self.images.get_image("layout", "match_mask")
        # 512xN
        basewidth = 349
        height = 331

        # Open the binary
        buf = io.BytesIO(binary)
        buf.seek(0)
        heart_img = Image.open(buf)

        picture = resize_picture(heart_img, basewidth)

        h = picture.size[1]
        # Crop it
        if h > 331:
            picture = picture.crop((0, 0, basewidth, height))

        # Extend it
        elif h < 331:
            pos = int((height - h) / 2)
            new = Image.new("RGBA", (349, 331), color=(238, 28, 36))
            new.paste(picture, (0, pos))
            picture = new

        # Now we composite
        # picture = picture.rotate(18, center=(20, 0))
        picture = Image.composite(picture, match_mask, match_mask)
        return picture

    def generate_match(self, author: UserProfile, user: UserProfile):
        new = Image.new("RGBA", (700, 500), color=0)
        match_border = self.images.get_image("layout", "match_border")
        author_heart = self.heartify(author.image_binaries[0])
        user_heart = self.heartify(user.image_binaries[0])
        author_heart = author_heart.rotate(11, expand=True)
        user_heart = user_heart.rotate(-10, expand=True)
        new.paste(author_heart, (13, 101), author_heart)
        new.paste(user_heart, (279, -6), user_heart)
        new.paste(match_border, (0, 0), match_border)

        return new

    @commands.command(name="match")
    @commands.is_owner()
    async def force_match(self, ctx, target: discord.Member):
        target_profile = await generate_profile(ctx, target.id)
        await target_profile.fetch_pictures()
        if not target_profile:
            print("Member didn't have a profile.")
            return

        await self.match(ctx, target_profile)

    async def match(self, ctx, user: UserProfile):
        # Obtains the user from whereever it is
        target = self.bot.get_user(user.member_id)
        print(ctx.author, "Matched with", target)
        # If target is not using the bot anymore
        if not target:
            await ctx.send("You matched, unfortunetely the user is no longer within my viscinity (Not in any relating servers) so I cannot find the users tag for you to add. Better luck next time!", text=True)
            return

        img = self.generate_match(ctx.profile, user)

        # Sends the image to the author
        if not ctx.author.dm_channel:
            await ctx.author.create_dm()
        try:
            await ctx.author.dm_channel.send("You matched with: **"+str(target)+"**, now go ahead and add them. Don't be shy", file=get_payload(img))
        except Exception as e:
            print("Sending in chat instead, exception:", e)
            await ctx.send("I tried sending you a DM about you recent match, but I couldn't due to your settings! Please correct them before you continue")

        # Sends the image to the user
        if not target.dm_channel:
            await target.create_dm()
        await target.dm_channel.send("You matched with: **"+str(ctx.author)+"**, now go ahead and add them. Don't be shy", file=get_payload(img))

    async def _modify_entry(self, ctx, user: UserProfile, swipe: bool, entry: asyncpg.Record, superlike=False):
        # Update fame for the target if it was swiped right on
        if swipe:
            fame = 1
            # Gives more fame if you superlike someone
            if superlike:
                fame = 3
            query = "UPDATE users SET fame=$1 WHERE member_id = $2"
            await ctx.db.execute(query, user.fame+fame, user.member_id)

        # If the entry exists
        if entry:
            superlike = entry.get("superlike", False)
            status = entry["status"]

            # It's a match
            if status and swipe:

                # dispatches the image creation and sending of the matched image
                self.bot.loop.create_task(self.match(ctx, user))

                # delete the targets entry, and the authors if an entry existed since earlier
                query = "DELETE FROM entries WHERE (member_id = $1 AND target_id = $2) OR (member_id = $2 AND target_id = $1)"
                await ctx.db.execute(query, ctx.author.id, user.member_id)

                # we also add an entry to the matches table
                query = "INSERT INTO matches (source_id, target_id, date) VALUES ($1, $2, $3)"
                await ctx.db.execute(query, ctx.author.id, user.member_id, datetime.now())

                #Return as we do not need to do any insertion or updating of previous entries
                return

        # If we had an earlier entry with this user, we update it if we didn't match
        compat = user.compat
        if compat is not None:
            # If we disliked, we up the compat
            if not swipe:
                compat += 1
            query = "UPDATE entries SET status = $1, date = $2, compat = $3, superlike = $4 WHERE member_id = $5 AND target_id = $6"
            await ctx.db.execute(query, swipe, datetime.now(), compat,superlike, ctx.author.id, user.member_id)

        # If it's a new user, we have to add an entry if we didn't match
        else:
            query = "INSERT INTO entries (member_id, target_id, status, date, compat, superlike) VALUES ($1, $2, $3, $4, $5, $6)"
            await ctx.db.execute(query, ctx.author.id, user.member_id, swipe, datetime.now(), 0, superlike)

    async def swipe(self, ctx, user: UserProfile):
        # Fetches the images for the user
        await user.fetch_pictures()

        # Fetch an entry to check if the user already has swiped on us earlier
        # This way we can also check if they superliked us
        query = "SELECT * FROM entries WHERE member_id = $1 AND target_id = $2"
        entry = await ctx.db.fetchrow(query, user.member_id, ctx.author.id)

        # If an entry exists and if the other user.
        if entry:
            superlike = entry.get("superlike", False)
            if superlike:
                user.render_settings = RenderSettings.SUPERLIKE

        while True:
            profile = user.render_profile()
            payload = get_payload(profile)
            msg = await ctx.send(f"**{ctx.author.name}** is swiping.", file=payload, text=True)

            # Deploys reactions to the image that are interactable
            # and affects the profile behaviour
            reactions = ["arrows", "toggle", "thumbs", "cancel"]

            # If the user swiping got superlikes available
            if ctx.profile.superlikes:
                index = reactions.index("thumbs")+1
                reactions.insert(index, "superlike")

            try:
                reaction = await user.deploy_reactions(msg, *reactions, timer=self.timer)
            except asyncio.TimeoutError:
                await attempt_delete(msg)
                return False
            # If the user swiped
            if reaction == "👍":
                ctx.profile.likes-=1
                await self._modify_entry(ctx, user, True, entry)
                return True

            elif reaction == "🔥":
                ctx.profile.superlikes-=1
                await self._modify_entry(ctx, user, True, entry, superlike=True)
                return True

            elif reaction == "👎":
                await self._modify_entry(ctx, user, False, entry)
                return True

            elif str(reaction) == "<:redTick:600735269792120977>":
                return False

    def generate_filter(self, ctx, limit=None, filter=None):
        if not filter:
            filter = ctx.profile.filter
        if filter == "global":
            return GlobalFilter(ctx, limit)
        elif filter == "server":
            return ServerFilter(ctx, limit)

    @commands.command("reload")
    @commands.is_owner()
    async def reload(self, ctx):
        self.bot.images.setup()

    @commands.command("test", cls=RestrictedCommand)
    async def testing(self, ctx):
        pass

    @commands.command(name="swipe", cls=RestrictedCommand)
    async def swiping(self, ctx):
        # This will let us know if a limits record exists
        if ctx.profile.likes is None:
            raise commands.CommandError("Limits entry does not exist for this member")

        # Configurations
        if ctx.profile.likes <= 0:
            await ctx.send("You got no likes left. Refreshes every 24h")
        # Entries per time
        limit = 30

        mode = "new"
        filter = self.generate_filter(ctx, limit)

        # Exclusive guild filter hardcoded
        if ctx.guild:
            if ctx.guild.id == 488129631501811724:
                filter = self.generate_filter(ctx, limit, filter="server")

        # Not used in a guild, and user is using the server filter
        else:
            if isinstance(filter, ServerFilter):
                await ctx.send(
                    "If you want to use the server filter, you need to use this command in a server.\nSwap to 'global' filter if you want to swipe in Direct Messages")
                return

        while True:
            # Fetch N users from the database with the users preference
            # These users run out, so we must obtain new ones if needed

            # We start by going through all the new users
            filter.prepare_query(mode)
            users = await filter.fetch_users(ctx)
            # This means we got nothing from the database. If we're running "new" mode
            # We want to change to "old" mode
            if not users:
                # If we ran the "new" filter, we now change to the old
                if mode == "new":
                    mode = "old"
                    continue
                # If we ran the "old" filter, we wan't to end the command
                # as there are no more users to swipe on
                else:
                    # When there's no more users to swipe on
                    await ctx.send("No more users to swipe on.")
                    break

            # If users were found
            if users:
                # Iterates over every user
                for user in users:
                    if not (await self.swipe(ctx, user)):
                        break

                    # decrement like value and break if we got no more left
                    if ctx.profile.likes <= 0:
                        await ctx.send("You got no likes left. Refreshes every 24h")
                        break
                else:
                    # If we didn't break, we continue
                    continue

                # If we did break, we break again
                break

        #Updates the limits that has been consumed
        await self._update_limits(ctx)

    async def _update_limits(self, ctx):
        query = "UPDATE limits SET likes = $1, superlikes = $2 WHERE member_id = $3"
        likes = ctx.profile.likes
        superlikes = ctx.profile.superlikes
        await ctx.db.execute(query, likes, superlikes, ctx.author.id)


def setup(bot):
    bot.add_cog(SwipeCog(bot))