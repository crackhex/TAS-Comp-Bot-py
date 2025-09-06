import random

import requests
from discord.ext import commands


class Quote(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    @commands.command(
        name="quote",
        usage="$quote",
        help=("""
            Retrieve a random quote from one of 2 APIs

            Parameters:
            None
    """),
    )
    async def quote(self, ctx):
        api1 = "https://dummyjson.com/quotes/random"
        api2 = "https://quotes-api-self.vercel.app/quote"

        random_api = random.choice([api1, api2])

        request = requests.get(random_api)
        formatted_request = dict(request.json())

        quote = formatted_request.get('quote')
        author = formatted_request.get('author')

        # Capitalize every sentence
        sentences = quote.split(". ")
        quote = ". ".join([s.lower().capitalize() for s in sentences])


        message = f"> {quote}\n -{author}"

        await ctx.send(message)


async def setup(bot) -> None:
    await bot.add_cog(Quote(bot))