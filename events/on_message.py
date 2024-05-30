import discord
from discord.ext import commands
from api import submissions


class Message(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):

        await submissions.handle_dms(message, self)

        content = message.content
        lower_content = content.lower()

        msg_list = ["kierio", "crazy", "😃"]

        if str(lower_content).startswith(msg_list[0]) and message.author != self.bot.user:
            await message.reply("kiro*")
        elif str(lower_content).startswith(msg_list[1]) and message.author != self.bot.user:
            await message.reply("Crazy?")
            await self.wait_crazy(message)
        elif msg_list[2] in lower_content and message.author != self.bot.user:
            await message.add_reaction("✈️")

    async def wait_crazy(self, message):
        def check(m):
            return m.author == message.author and m.channel == message.channel

        crazy_list = ["i was crazy once", "a rubber room", "and rats make me crazy"]
        response = await self.bot.wait_for('message', check=check)
        response_lower = response.content.lower()
        if response_lower.startswith(crazy_list[0]):
            await response.reply("They locked me in a room.")
            response = await self.bot.wait_for('message', check=check)
            response_lower = response.content.lower()
            if response_lower.startswith(crazy_list[1]):
                await response.reply("A rubber room with rats.")
                response = await self.bot.wait_for('message', check=check)
                response_lower = response.content.lower()
                if response_lower.startswith(crazy_list[2]):
                    await response.reply("Crazy?")


async def setup(bot):
    await bot.add_cog(Message(bot))