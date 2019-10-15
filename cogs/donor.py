from discord.ext import commands
import json
import asyncio
import utils.checks as checks
import re


class DonorCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.donor_roles = []
        self.donors = {}
        self.themes = {}
        self.theme_list = []

    async def main_setup(self):
        await self.setup_donors()

    async def assign(self, user_id, permission):
        self.donors[user_id] = {"permission": permission, "theme": self.themes[self.theme_list[permission]]}
        async with self.bot.pool.acquire() as c:
            # TODO if we need database stuff for donors, implement that here
            pass
        print("Added permission level:", permission, "to:", user_id)

    async def remove(self, user_id):
        # Removes from donor list
        del self.donors[user_id]
        # Removes donor from db
        async with self.bot.pool.acquire() as c:
            # TODO if we need database stuff for donors, implement that here
            pass

    def get_donor_roles(self):
        return self.donor_roles

    def get_user(self, user_id):
        return self.donors.get(user_id, None)

    def get_all_donors(self):
        return self.donors

    def get_all_donor_ids(self):
        return self.donors.keys()

    def get_all_donor_members(self):
        members = []
        for guild in self.bot.guilds:
            for member in guild.members:
                if member.id in self.donors.keys():
                    members.append(member)
        return members

    async def setup_donors(self):

        with open("themes.json") as f:
            self.themes = json.load(f)

        donor_ids = [507336053158445092, 507324154383433738, 507336193546125333, 507369940676902932, 507381388832669696,
                     507373034001399809]
        self.theme_list = ["blue", "gold", "green", "purple", "redish", "red"]

        # Fetch the hub server
        guild = self.bot.get_guild(self.bot.home_guild_id)
        async with self.bot.pool.acquire() as c:

            # Loop through all of the donor role id's
            for i, donor_id in enumerate(donor_ids):

                #Obtain the role itself
                role = guild.get_role(donor_id)

                # Obtain the members that have that role assigned
                for member in role.members:

                    # Insert some information about the donaor position into local memory
                    self.donors[member.id] = {"permission": i, "theme": self.themes[self.theme_list[i]]}

                    # TODO if we need database stuff for donors, implement that here

                self.donor_roles.append(role)

    @commands.command(name="theme")
    async def theme(self, ctx):
        donor = self.donors.get(ctx.author.id, None)
        options = ["black"]
        string = "``black``\n"
        if donor:
            for i in range(donor["permission"] + 1):
                theme = self.theme_list[i]
                string += f"``{theme}``\n"
                options.append(theme)
        msg = await ctx.send("Select the type of theme you want to use", add_fields=[("Themes:", string)])

        def check(m):
            if m.content in options:
                return m.author == ctx.message.author

        try:
            message = await self.bot.wait_for('message', timeout=20, check=check)
        except asyncio.TimeoutError:
            await msg.delete()
        else:
            if donor:
                self.donors[ctx.author.id] = {"permission": donor["permission"], "theme": self.themes[message.content]}
            await msg.delete()
            await message.delete()
            await ctx.send(f"You've successfully changed your theme to {message.content}!")

    @commands.Cog.listener("on_member_join")
    async def on_member_join(self, member):
        if member.guild.id != self.bot.home_guild_id:
            return
        for i, role in enumerate(self.get_donor_roles()):
            if role in member.roles:
                print("Assigning Member to internal donor list (on_member_join)")
                await self.assign(member.id, i)

    @commands.Cog.listener("on_member_update")
    async def on_member_update(self, before, after):
        # Return if it's not Asgard
        if before.guild.id != self.bot.home_guild_id:
            return
        # Return if roles has not been changed
        if before.roles == after.roles:
            return

        for i, role in enumerate(self.get_donor_roles()):
            # If the role didn't exist before
            if role not in before.roles:
                # And the role exists now
                if role in after.roles:
                    print("Assigning Member to internal donor list (on_member_update)")
                    await self.assign(after.id, i)
            # If the role existed before
            if role in before.roles:
                # But does not exist anymore
                if role not in after.roles:
                    try:
                        await self.remove(after.id)
                    except Exception:
                        pass


def setup(bot):
    bot.add_cog(DonorCog(bot))
