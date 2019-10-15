from utils.profile import UserProfile
from datetime import datetime, timedelta

class Filter:
    def __init__(self, ctx, limit: int):
        self.ctx = ctx
        self.query = None
        self.values = None
        self.limit = limit
        self.arguments = 0

    # Here entries are fetched that has already been registered as "compatible"
    # So checks shouldn't needed to be as strict here. Date check should suffice

    def prepare_query(self, mode: str):
        profile = self.ctx.profile
        if mode == "new":
            self._query_new_users(profile)
        elif mode == "old":
            self._query_entried_users(profile)


    # Different specification rules
    def _query_entried_users(self, profile: UserProfile):
        pass

    # Different specification rules
    def _query_new_users(self, profile: UserProfile):
        pass

    def get_age_query(self, profile: UserProfile):
        if profile.age < 18:
            compare = '<'
        if profile.age >= 18:
            compare = '>'
        query = f"AND age(now(), users.birth) {compare} interval '18 years'"
        return query

    # Fetches the data from the database
    async def _fetch_users(self, ctx):
        # Execute the query to obtain users from database
        users = await ctx.db.fetch(self.query, *self.values)

        # returns the database records "We used 'fetch', meaning it will be a list of records"
        return users

    # Fetches the Profile objects
    async def fetch_users(self, ctx):

        # Create an empty list to place the user objects in (array)
        users = []

        # Obtain the record data (the function above)
        users_data = await self._fetch_users(ctx)

        # Iterate over each database record
        for i, user_data in enumerate(users_data):

            #
            user = UserProfile(ctx, user_data)
            users.append(user)
        return users


class GlobalFilter(Filter):
    def __init__(self, ctx, limit: int):
        super().__init__(ctx, limit)

    def _query_new_users(self, profile: UserProfile):

        query = ''' SELECT users.sex, users.bio, users.name, users.country, users.birth, users.preference, users.member_id, users.fame, users.created_at, users.filter, entries.compat  
                    FROM users LEFT JOIN entries ON users.member_id = entries.target_id AND entries.member_id = $1
                    LEFT JOIN matches ON (matches.target_id = users.member_id AND matches.source_id = $1)
                    OR (matches.source_id = users.member_id AND matches.target_id = $1)
                    WHERE entries is null
                    AND matches is null
                    AND users.member_id != $1
                    AND (users.preference = $2 OR users.preference = $3)
                '''
        query += self.get_age_query(profile)
        # This means that the user want sex specific entries
        values = (self.ctx.author.id, "both", profile.sex+"s")
        if profile.preference != "both":
            query += f"AND (users.sex = $4 OR users.sex = $5)"

            sex = profile.preference[:-1]

            # trans option male-to-female, female-to-male
            if sex == "male":
                trans = "female"
            elif sex == "female":
                trans = "male"

            values += (sex,)
            values += (trans+"-to-"+sex,)

            query += f"LIMIT $6"
            values += (self.limit,)
        else:
            query += f"LIMIT $4"
            values += (self.limit,)

        self.query = query
        self.values = values

    # Query for getting users that has already been swiped on (check date to swipe again)
    def _query_entried_users(self, profile: UserProfile):
        query = ''' SELECT users.sex, users.bio, users.name, users.country, users.birth, users.preference, users.member_id, users.fame, users.created_at, users.filter, entries.compat 
                    FROM users INNER JOIN entries ON users.member_id = entries.target_id
                    WHERE entries.member_id = $1
                    AND entries.date <= $2
                '''

        # Add additional garbage
        sevendays = datetime.now() - timedelta(days=7)
        values = (self.ctx.author.id, sevendays)
        if profile.preference != "both":
            query += f"AND (users.sex = $3 OR users.sex = $4)"

            sex = profile.preference[:-1]

            # trans option male-to-female, female-to-male
            if sex == "male":
                trans = "female"
            elif sex == "female":
                trans = "male"

            values += (sex,)
            values += (trans+"-to-"+sex,)

            # Order by
            query += "ORDER BY compat ASC "

            #Limit
            query += f"LIMIT $5"
            values += (self.limit,)

        else:
            # Order by
            query += "ORDER BY compat ASC "

            #Limit
            query += f"LIMIT $3"
            values += (self.limit,)

        self.query = query
        self.values = values






class ServerFilter(Filter):
    def __init__(self, ctx, limit: int):
        super().__init__(ctx, limit)

    # Fetch all the users that no entries where the author is the source exists on
    def _query_new_users(self, profile: UserProfile):
        query = ''' SELECT users.sex, users.bio, users.name, users.country, users.birth, users.preference, users.member_id, users.fame, users.created_at, users.filter, entries.compat  
                    FROM users LEFT JOIN entries ON users.member_id = entries.target_id AND entries.member_id = $1
                    LEFT JOIN matches ON (matches.target_id = users.member_id AND matches.source_id = $1)
                    OR (matches.source_id = users.member_id AND matches.target_id = $1)
                    LEFT JOIN guilds ON users.member_id = guilds.member_id
                    WHERE entries is null
                    AND guilds.guild_id = $2
                    AND matches is null
                    AND users.member_id != $1
                    AND (users.preference = $3 OR users.preference = $4)
                '''
        query += self.get_age_query(profile)
        # This means that the user want sex specific entries
        values = (self.ctx.author.id, self.ctx.guild.id, "both", profile.sex+"s")
        if profile.preference != "both":
            query += "AND (users.sex = $5 OR users.sex = $6) "
            sex = profile.preference[:-1]

            # trans option male-to-female, female-to-male
            if sex == "male":
                trans = "female"
            elif sex == "female":
                trans = "male"

            values += (sex,)
            values += (trans + "-to-" + sex,)

            query += "LIMIT $7"
            values += (self.limit,)
        else:
            query += "LIMIT $5"
            values += (self.limit,)
        self.query = query
        self.values = values

    # Fetch all the users that we can swipe on that exists from earlier entries
    def _query_entried_users(self, profile: UserProfile):
        query = ''' SELECT users.sex, users.bio, users.name, users.country, users.birth, users.preference, users.member_id, users.fame, users.created_at, users.filter, entries.compat 
                    FROM users INNER JOIN entries ON users.member_id = entries.target_id
                    LEFT JOIN guilds ON users.member_id = guilds.member_id
                    WHERE guilds.guild_id = $2
                    AND entries.member_id = $1
                    AND entries.date >= $3
                '''
        # Add additional garbage
        sevendays = datetime.now() - timedelta(days=7)
        values = (self.ctx.author.id, self.ctx.guild.id, sevendays)
        if profile.preference != "both":
            query += f"AND (users.sex = $4 OR users.sex = $5)"

            sex = profile.preference[:-1]

            # trans option male-to-female, female-to-male
            if sex == "male":
                trans = "female"
            elif sex == "female":
                trans = "male"

            values += (sex,)
            values += (trans + "-to-" + sex,)

            # Order by
            query += "ORDER BY compat ASC "

            # Limit
            query += f"LIMIT $6"
            values += (self.limit,)

        else:
            # Order by
            query += "ORDER BY compat ASC "

            # Limit
            query += f"LIMIT $4"
            values += (self.limit,)

        self.query = query
        self.values = values
