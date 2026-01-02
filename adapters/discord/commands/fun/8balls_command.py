import random
import asyncio

import discord
from discord.ext import commands


class Eightball(commands.Cog):
    """
    Ask the magic 8-ball your question.  Supports three categories:
      • when-questions (“When”) → time-based replies
      • who-questions  (“Who”)  → pick a random user in the database
      • all others              → classic yes/no/maybe replies
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        self.when = [
            'Now.', 'Right now.', 'In a few minutes only!', 'Just wait a few more hours.',
            'Sometime today.', 'Today.', 'At midnight.', 'Tomorrow.',
            'Surely tomorrow.', 'Tomorrow, possibly at the end of the day.',
            'Possibly tomorrow, if not, after tomorrow.',
            'Possibly in a few days.', 'Wait a few more days.', 'After tomorrow!',
            'Next week!', 'Just wait until next week rolls around!',
            'In exactly {n} days.'.format(n=random.randrange(0, 31)),
            'Most likely in a few weeks only.', 'Probably only next month.',
            'Next month!', 'Next year :P', 'Just be patient man!', 'Never.',
            'Most likely never.', 'That will happen when pigs fly :P',
            'Not in a month of Sundays! :P', "It won't happen.", 'God knows when.',
            'Why are you asking? Just wait.', 'Have you heard of waiting?',
            "When the stars align (and your Wi-Fi behaves).",
            "When your cat gives consent.",
            "When the emulator stops lagging — maybe.",
            "After you sacrifice one sock to the RNG gods.",
            "When the coffee kicks in.",
            "During a leap second — very exclusive timing.",
            "In approximately π days (give or take).",
            "When someone invents a time machine.",
            "When the developer remembers to push the update."
            'Soon™', 'In due time.', 'At an inconvenient hour.'
        ]

        self.yes = [
            'Yes.', 'Yes, surely.', 'It is common knowledge that the answer is yes.',
            'Absolutely!', 'Most likely', 'My sources point to yes.', 'It is certain.',
            'Without a shadow of a doubt!', 'Outlook good', 'Signs point to yes.',
            'You may rely on it.', 'Count on it!', "Definitely — I’d put money on it.",
            "If it were up to me, yes.", "The universe is nodding in agreement.",
            "Green light. Go!"
        ]
        self.neutral = [
            'Maybe, maybe not.', "Can't predict right now.", 'Concentrate and ask again.',
            'I better not tell you right now!', 'Reply hazy, try again mate.', 'Try again later.',
            'Vibes inconclusive.', "Ask me after a nap.", "I need more data (and snacks).",
            "My crystal ball is on the fritz.", "Could go either way — flip a coin?",
            'Ask me again after coffee.', 'The answer is blurred.',
            'Your guess is as good as mine.'
        ]
        self.no = [
            'No.', 'No, surely not.', 'Everyone knows the answer is no!',
            'Absolutely not!', 'Most likely not', 'My sources point to no.',
            'Certainly not.', 'Very doubtful...', 'Outlook not so good.',
            'Evidence points to no.', "Don't rely on it.", "Don't even think about it.",
            "Not today, friend.", "The stars say no.", "Hard pass.",
            "I'd advise against it."
        ]

        self.affirmation = [
            "I'd say", "For sure", "I'd bet on", "My money's on",
            "Chances are", "Putting my chips on", "I'm going with",
            "Lean towards", "Go with", "Strongly recommend",
            "Probably", "99% chance it's", "S-tier pick:", "I'd hazard that it's",
            "If I had to guess (and I do), it's", "I solemnly swear it's"
        ]

        self.rates = {
            "very-low": [
                "This belongs in the dumpster fire museum.",
                "Are you trolling or...?",
                "My disappointment is immeasurable and my day has been ruined.",
                "This is a war crime.",
                "I lost brain cells looking at this.",
                "This is a crime against humanity.",
                "This made my soul leave my body.",
                "I'm reporting this to the authorities.",
                "Some things just shouldn't exist.",
                "A certified flop.",
                "Please delete this from existence.",
                "Even my toaster could do better.",
                "Get outta here!",
                "My eyes are burning!",
                "No. Just no.",
                "Someone help me..."
            ],

            "low": [
                "Ewww!",
                "Yikes.",
                "This is bad.",
                "Are you okay?",
                "Eh... it's giving... disappointment.",
                "Not the worst, but still bad.",
                "I don't wanna hear about it again.",
                "I’ve seen better from a potato.",
                "I respect the attempt. I don’t like it, but I respect it.",
                "This could've been great. It wasn't.",
                "I’ve seen worse... but not by much.",
                "Not great, not terrible… wait no, it's just bad.",
                "Was this an accident?",
                "There's potential, but it's buried deep."
                "This is like a pizza with no cheese.",
            ],

            "mid": [
                "That’s... acceptable.",
                "It works, I guess.",
                "You’re not winning any awards, but hey, it exists.",
                "Middle of the road. Could go either way.",
                "That’s alright.",
                "Meh. Mid-tier vibes.",
                "I’ve seen better. I’ve seen worse.",
                "Like lukewarm tea. Technically fine.",
                "Mid. Like bread with no butter.",
                "That's average Joe territory.",
                "Not bad, not great, just... ok I guess.",
                "Solid mid rating. Like lukewarm soup.",
                "You're doing fine. Ish.",
                "Neutral like Switzerland.",
                "This is... fine.",
                "You know what, sure. It’s fine.",
                "Could use seasoning."
            ],

            "good": [
                "Now we’re talking!",
                "Certified nice!"
                "That’s clean!",
                "You understood the assignment.",
                "Nice!",
                "Respectable! Would recommend.",
                "Yup, that’s a W.",
                "Not bad at all!",
                "This is actually impressive.",
                "Above average, and I’m not just being nice.",
                "Looking sharp!",
                "Now *that’s* what I’m talking about.",
                "Nice work!",
                "This slaps mildly.",
                "High-five worthy.",
                "Pretty solid effort!",
                "That was cleaner than my conscience.",
                "I'm impressed!"
            ],

            "great": [
                "Absolutely stunning!",
                "A masterpiece!",
                "This is peak.",
                "That’s what dreams are made of.",
                "Chef’s kiss!",
                "Perfection. Nothing to add.",
                "Elite. Top 0.1%.",
                "You cracked the code, didn’t you?",
                "Certified GOAT.",
                "This made me believe in humanity again.",
                "Legendary. Iconic. Timeless.",
                "I'm crying. It's beautiful.",
                "You deserve a trophy. Or five.",
                "Massive W."
            ]
        }



    def pick_yesno(self) -> tuple[str, discord.Color]:
        """
        Randomly choose one of Yes / Neutral / No, weighted 40/20/40,
        and return it plus appropriate color.
        """
        roll = random.random()
        if roll < 0.40:
            return random.choice(self.yes), discord.Color.green()
        if roll < 0.6:
            return random.choice(self.neutral), discord.Color.yellow()
        return random.choice(self.no), discord.Color.red()

    @commands.command(
        name="8ball",
        usage="/8ball <question>",
        help=("""
            Ask the magic 8ball for his wisdom.

            Parameters:
            `question`: The question. It must be a yes/no, when, or who type of question. It can also rate stuff!.
    """),
    )
    async def eightball(self, ctx: commands.Context, *, question: str):

        first = question.strip().split(maxsplit=1)[0].lower()


        # When category
        if first == "when" or first == "when's":
            reply = random.choice(self.when)
            color = discord.Color.blue()

        # Who category
        elif first == "who" or first == "who's":
            # Try picking from the database
            user_service = getattr(self.bot, "user_service", None)
            candidate_name = None

            users = await user_service.list_users()
            if users:
                chosen = random.choice(users)
                user = self.bot.get_user(chosen.discord_id) or await self.bot.fetch_user(chosen.discord_id)
                candidate_name = user.display_name

            if not candidate_name:
                # fallback: random non-bot guild member
                members = [m for g in self.bot.guilds for m in g.members if not m.bot]
                if members:
                    candidate_name = random.choice(members).display_name
                else:
                    candidate_name = "someone… maybe you?"

            affirmation = random.choice(self.affirmation)
            reply = f"{affirmation} **{candidate_name}**."
            color = discord.Color.purple()

        elif first == "rate":
            random_rate = random.randint(0, 10)

            match random_rate:
                case 0 | 1:
                    text = random.choice(self.rates.get("very-low"))
                    color = discord.Color.dark_red()
                case 2 | 3:
                    text = random.choice(self.rates.get("low"))
                    color = discord.Color.red()
                case 4 | 5 | 6:
                    text = random.choice(self.rates.get("mid"))
                    color = discord.Color.yellow()
                case 7 | 8:
                    text = random.choice(self.rates.get("good"))
                    color = discord.Color.green()
                case 9 | 10:
                    text = random.choice(self.rates.get("great"))
                    color = discord.Color.brand_green()
                case _:
                    text = "Idk man!"
                    color = discord.Color.magenta()

            reply = f"{text} {random_rate}/10"



        # Yes/No category
        else:
            reply, color = self.pick_yesno()

        # Simulate bot typing
        async with ctx.typing():
            await asyncio.sleep(random.random() * 1.5)

        # Build embed
        embed = discord.Embed(color=color)
        embed.add_field(name=f":question: {ctx.author.display_name} asked...", value=question, inline=False)
        embed.add_field(name=":8ball: responds...", value=reply, inline=False)

        await ctx.send(embed=embed, mention_author=False)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Eightball(bot))
