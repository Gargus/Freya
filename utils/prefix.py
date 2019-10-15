class Prefix:
    """The "database" object. Internally based on ``json``."""

    async def prefix_setup(self):
        async with self.bot.pool.acquire() as c:
            prefixes = await c.fetch("SELECT * FROM prefix")
            for prefix in prefixes:
                self._db[prefix['guild_id']] = [prefix['prefix']]

    def __init__(self, bot):
        self.bot = bot
        self._db = {}
        self.bot.loop.create_task(self.prefix_setup())

    def get(self, guild_id, optional=None):
        if guild_id not in self._db:
            return optional
        return self._db[guild_id]

    def remove(self, guild_id):
        if guild_id in self._db:
            del self._db[guild_id]

    def put(self, guild_id, prefix):
        self._db[guild_id] = [prefix]
