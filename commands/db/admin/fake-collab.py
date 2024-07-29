import discord
from discord.ext import commands
from discord.ext.commands import Greedy
from api.utils import get_team_size, is_in_team
from api.db_classes import Teams, Userbase, get_session
from api.submissions import new_competitor
from sqlalchemy import select, insert, update, delete

class fakeCollab(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pending_users = {}
        self.ctx = None
        self.author = None
        self.team_size = None

    @commands.hybrid_command(name="fake-collab", description="fake a collab (dev/test purposes)", with_app_command=True)
    async def collab(self, ctx, users: Greedy[discord.Member]):
        self.ctx = ctx
        self.author = ctx.author
        self.team_size = await get_team_size()

        #####################
        # Case handling
        #####################

        # Is there a task running?
        if self.team_size is None:
            return await ctx.send("There is no task running currently.")

        # Verify if it's indeed a collab task
        elif self.team_size < 2:
            return await ctx.send("This is a solo task. You may **not** collaborate!")


        # Make sure they don't try to collab with too many people
        elif len(users) + 1 > self.team_size:
            return await ctx.send("You are trying to collab with too many people!")

        # Make sure they are not already in a team
        if await is_in_team(ctx.author.id):
            return await ctx.send("You are already in a team.")

        # Make sure they are not collaborating with themselves: absurd
        for user in users:
            if user.id == self.author.id:
                return await ctx.send("Collaborating with... yourself? sus")

        ####################################
        # Adding executor to user db if new
        ####################################
        if await new_competitor(ctx.author.id):
            async with get_session() as session:
                await session.execute(insert(Userbase).values(user_id=ctx.author.id, user=self.bot.get_user(ctx.author.id).name,
                                                              display_name=self.bot.get_user(ctx.author.id).display_name))
                await session.commit()

        # Everyone has accepted
        await self.ctx.send(f"{self.author} is collaborating with {user.name}!")

        # Add team to Teams db
        user_ids = list(self.pending_users.keys())
        async with get_session() as session:
            await session.execute(
                insert(Teams).values(leader=self.author.id, user2=user_ids[0] if len(user_ids) > 0 else None,
                                        user3=user_ids[1] if len(user_ids) > 1 else None,
                                        user4=user_ids[2] if len(user_ids) > 2 else None))

            # Add any new users to Userbase db
            for id in self.pending_users:
                if await new_competitor(id):
                    # adding him to the user database.
                    await session.execute(insert(Userbase).values(user_id=id, user=self.bot.get_user(id).name,
                                                                        display_name=self.bot.get_user(id).display_name))
            # Commit both changes
            await session.commit()

        # clear pending users list
        self.pending_users.clear()
                

async def setup(bot):
    await bot.add_cog(fakeCollab(bot))