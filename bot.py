from tinker import Tinker
import asyncio
import config
import asyncpg

table_queries=[
        '''
            CREATE TABLE if not exists users(
                id serial PRIMARY KEY,
                sex text,
                bio text,
                name text,
                country text,
                birth timestamp,
                preference text,
                member_id bigint,
                fame int,
                created_at timestamp,
                filter text,
                UNIQUE(member_id)
            )
        ''',
            '''
            CREATE TABLE if not exists limits(
                id serial PRIMARY KEY,
                member_id bigint,
                likes smallint,
                superlikes smallint,
                UNIQUE(member_id)
            )
        '''
            ,
            '''
            CREATE TABLE if not exists pictures(
                id serial PRIMARY KEY,
                member_id bigint,
                image bytea,
                ordered smallint,
                date timestamp
            )
        ''',
            '''
            CREATE TABLE if not exists entries(
                id serial PRIMARY KEY,
                member_id bigint,
                target_id bigint,
                status boolean,
                date timestamp,
                compat smallint,
                superlike bool
            )  
        ''',
            '''
            CREATE TABLE if not exists matches(
                id serial PRIMARY KEY,
                source_id bigint,
                target_id bigint,
                date timestamp
            )
        ''',
            '''
            CREATE TABLE if not exists prefix(
                id serial PRIMARY KEY,
                guild_id bigint,
                prefix text
            )
        ''',
            '''
            CREATE TABLE if not exists guilds(
                id serial PRIMARY KEY,
                guild_id bigint,
                member_id bigint,
                UNIQUE (guild_id, member_id)
            )
        ''',
            '''
            CREATE TABLE if not exists voters(
                id serial PRIMARY KEY,
                bot_id bigint,
                user_id bigint,
                type text,
                isweekend boolean,
                query text,
                date timestamp,
                claimed boolean
            )
        ''',
            '''
            CREATE TABLE if not exists verification(
                id serial PRIMARY KEY,
                message_id bigint,
                user_id bigint
            )
        ''']

# Postgres functions
async def create_pool(uri):
    result = await asyncpg.create_pool(uri, command_timeout=60)
    return result

async def create_table(uri, q):
    conn = await asyncpg.connect(uri)
    await conn.execute(q)
    await conn.close()


def db_setup():
    run = asyncio.get_event_loop().run_until_complete
    try:
        print("Setting up tables...")
        for query in table_queries:
            run(create_table(config.postgresql, query))
    except Exception as e:
        print(e)
        print('Could not set up PostgreSQL. Exiting.')
        return
    print("Table setup done")


def run_bot():

    loop = asyncio.get_event_loop()
    try:
        print("Creating pool...")
        pool = loop.run_until_complete(create_pool(config.postgresql))
    except Exception as e:
        print('Could not set up PostgreSQL. Exiting.')
    print("Pool created successfully")
    bot = Tinker()
    bot.pool = pool

    # The guild id for the support server
    bot.home_guild_id = 472546414455685132
    bot.run(config.bot_token)


db_setup()
run_bot()