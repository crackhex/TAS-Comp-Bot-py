import random
from discord.ext import commands

class Slots(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    @commands.command(
        name="slots",
        usage="$slots [number]",
        help=("""
            Play the famous slots with `number` reels!

            Parameters:
            `number`: The number of reels
    """),
    )
    async def slots(self, ctx: commands.Context, number: int = 3):
        """
        Spin a slot machine of n emojis.
        Max n is 20 to avoid Discord’s 2000-char limit.
        You win if every reel shows the same emoji.
        """
        # 0) Validate count
        if number <= 0:
            return await ctx.reply("What did you think would happen, huh? 🤔")
        if number > 20:
            return await ctx.send(
                "Please use a smaller number! It's not like you would win slots with that many reels anyway..."
            )

        # 1) Gather emojis
        emojis = ctx.guild.emojis
        emojis_list = [str(e) for e in emojis]

        # 2) Roll
        random_emojis = random.choices(emojis_list, k=number)
        display = " ".join(random_emojis)

        # 3) Truncate if over Discord’s 2000-char limit
        if len(display) > 2000:
            while len(display) > 2000 and random_emojis:
                random_emojis.pop()
                display = " ".join(random_emojis)
            await ctx.reply(f"{display}\n*(message truncated)*")
        else:
            await ctx.reply(display)

        # 4) Determine outcome
        # Single-slot “win”
        if number == 1:
            return await ctx.send("You won... I guess?")

        # Multi-slot: all the same → win
        if all(symbol == random_emojis[0] for symbol in random_emojis):
            # Probability: 1 in (len(emojis_list)^(number-1))
            denom = len(emojis_list) ** (number - 1)
            prob = 1 / denom if denom else 0
            pct  = prob * 100
            return await ctx.send(
                f"🏆 You won! Probability was **{pct:.2f}%** (1 in {denom})."
            )

        # Otherwise lose
        return await ctx.send("You lost! Please play again")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Slots(bot))
