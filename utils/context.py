from discord.ext import commands
from utils.profile import Profile, generate_profile
from discord.errors import InvalidArgument
from discord.file import File
import discord

class _ContextDBAcquire:
    __slots__ = ('ctx', 'timeout')

    def __init__(self, ctx, timeout):
        self.ctx = ctx
        self.timeout = timeout

    def __await__(self):
        return self.ctx._acquire(self.timeout).__await__()

    async def __aenter__(self):
        await self.ctx._acquire(self.timeout)
        return self.ctx.db

    async def __aexit__(self, *args):
        await self.ctx.release()


class Context(commands.Context):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.pool = self.bot.pool
        self.db = None
        self.profile = None

    def set_channel(self, channel):
        self.channel = channel

    async def send(self, *args, **kwargs):
        # Create an embed
        if self.channel:
            kwargs["static_channel"] = self.channel
        desc = kwargs.get("description")
        if desc:
            embed = discord.Embed(title=args[0], description=desc, colour=0xd89a88)
            del kwargs["description"]
        else:

            embed = discord.Embed(title=args[0], description=f"", colour=0xd89a88)
        embed.set_author(name=f"{self.author.name}", icon_url=self.author.avatar_url)


        image = kwargs.get("image")
        if image is not None:
            embed.set_image(image)
            del kwargs["image"]

        thumbnail = kwargs.get("thumbnail")
        if thumbnail is None:
            embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/589129757589897263/609709332317077504/pixelpeach.png")
        else:
            del kwargs["thumbnail"]

        try:
            footer = kwargs.pop("footer")
        except KeyError:
            pass
        else:
            embed.set_footer(text=footer, icon_url="https://cdn.discordapp.com/attachments/589129757589897263/601625803993776189/tooltip.png")

        field = kwargs.get("field")
        if field:
            embed.add_field(name=field[0], value=field[1])
            del kwargs["field"]
        fields = kwargs.get("fields")
        if fields:
            for field in fields:
                embed.add_field(name=field[0], value=field[1], inline=False)
            del kwargs["fields"]
        # If a file isn't sent, embed the message
        if kwargs.get("text") is None:
            kwargs["embed"] = embed
        else:
            del kwargs["text"]
            return await self._send(*args, **kwargs)
        return await self._send(**kwargs)

    async def _send(self, content=None, *, tts=False, embed=None, file=None, files=None, delete_after=None, nonce=None, static_channel=None):
        # If we want to set a static channel to the context and send content there
        channel = await self._get_channel()
        if static_channel:
            channel = static_channel


        state = self._state
        content = str(content) if content is not None else None
        if embed is not None:
            embed = embed.to_dict()

        if file is not None and files is not None:
            raise InvalidArgument('cannot pass both file and files parameter to send()')

        if file is not None:
            if not isinstance(file, File):
                raise InvalidArgument('file parameter must be File')

            try:
                data = await state.http.send_files(channel.id, files=[file],
                                                   content=content, tts=tts, embed=embed, nonce=nonce)
            finally:
                file.close()

        elif files is not None:
            if len(files) > 10:
                raise InvalidArgument('files parameter must be a list of up to 10 elements')
            elif not all(isinstance(file, File) for file in files):
                raise InvalidArgument('files parameter must be a list of File')

            try:
                data = await state.http.send_files(channel.id, files=files, content=content, tts=tts,
                                                   embed=embed, nonce=nonce)
            finally:
                for f in files:
                    f.close()
        else:
            data = await state.http.send_message(channel.id, content, tts=tts, embed=embed, nonce=nonce)

        ret = state.create_message(channel=channel, data=data)
        if delete_after is not None:
            await ret.delete(delay=delete_after)
        return ret

    async def _acquire(self, timeout):
        if self.db is None:
            self.db = await self.pool.acquire(timeout=timeout)

        return self.db

    def acquire(self, *, timeout=None):
        """Acquires a database connection from the pool. e.g. ::
            async with ctx.acquire():
                await ctx.db.execute(...)
        or: ::
            await ctx.acquire()
            try:
                await ctx.db.execute(...)
            finally:
                await ctx.release()
        """
        return _ContextDBAcquire(self, timeout)

    async def release(self):
        """Releases the database connection from the pool.
        Useful if needed for "long" interactive commands where
        we want to release the connection and re-acquire later.
        Otherwise, this is called automatically by the bot.
        """
        # from source digging asyncpg source, releasing an already
        # released connection does nothing

        if self.db is not None:
            await self.bot.pool.release(self.db)
            self.db = None