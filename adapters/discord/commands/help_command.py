# src/adapters/discord/commands/help_command.py

import discord
from discord.ext import commands

class HelpCommand(commands.Cog):
    """
    Replaces the default help to provide a custom overview menu.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Define your top-level help text here
        self.help_menu = """
        **Categories**:
          **help** — this
          **fun** — Fun commands, such as 8ball
          **comp** — Public competition-related commands 
          **host** — Host-only commands, for handling tasks.
          **admin** — Admin commands
        
        Write `$help <category>` to view help for a specific category.
        Or write `$help <command>` to view help for a specific command.
    """

        self.comp_menu =  """
      **info** — Shows information about the status of your submission. (DM only)
      
      **collab** — Team up with someone during a collab task!
      **setteamname** — Changes your team's name during collab tasks.
      **leaveteam** — Leave your team during a collab task.
      **teams** — View the list of teams during a collab task.

      **requesttask** — Request the task (sent to your DMs) during a speed task.
      **stop-timer** — Ends your speed task early.
      
-# Use **$help <command>** for detailed usage
    """

        self.fun_menu = """
      **8ball** — Have a question? Ask the bot for his wisdom!
      **slots** — Play the famous slot machine. Default number of emotes is 3.
      
-# Use **$help <command>** for detailed usage
    """

        self.host_menu = """
      **/dm** — Make the bot dm someone!
      
      **/start-task** — Starts a new task. Warning: this resets last task's data.
      **set-deadline** — Change the deadline. Time in UNIX!
      **end-task** — Ends the current task (Warning: No confirmation).
    
      **/submit** — Submit a file for someone.
      **/edit-submission** — Edits someone's submission status: time, dq (T/F), dq reason
      **delete-submission** — Delete someone's submission.
      **get-submissions** — Your bread and butter for starting to judge and time runs!
      **get-results** — Prints the results of the current (ended or not) task.

      **hostkick** — Kick a specific user from their team.
      **hostdissolve** — Dissolve a team.
      
      **speed-task-desc** — Set the description of a speed task.
      **speed-task-length** — Set the time duration of a speed task session.
      **speed-task-reminders** — Set the reminders for a speed task. Up to 4 reminders.
      **stop-timer** — Ends someone else's speed task early.
      
-# Use **$help <command>** for detailed usage
    """

        self.admin_menu = """
      **say** — Make the bot say something in a channel!
      **setname** — Change someone's name for the submission channel.
      
      **sync** — Synchronize the bot's slash commands.
      **config** — Configure the different roles and channels
      **set-comp** — Associate the server with a type of competition (mkw, sm64, etc)
      **set-file** — Set the accepted fie extension for submissions.
      
-# Use **$help <command>** for detailed usage
      """

    @commands.command(name="help")
    async def help(self, ctx: commands.Context, *, topic: str = None):
        """
        If called without arguments, show the top-level help menu.
        If `topic` matches a category or command name, dispatch there.
        """
        if topic is None:
            embed = discord.Embed(
                title=f":book: Help menu",
                description=self.help_menu,
                colour=discord.Colour.from_rgb(0, 255, 255)
            )

            # Retrieve guild (to get server icon)
            guild_list = await ctx.bot.config_service.list_guild_configs()
            guild_id = guild_list[0].guild_id
            guild = self.bot.get_guild(guild_id)

            embed.set_footer(text="MKWTASCompBot - A Multi TAS Comp Bot", icon_url=guild.icon.url if guild.icon else None)
            return await ctx.send(embed=embed)

        topic = topic.lower()
        if topic in ("comp", "fun", "host", "admin"):
            # choose the right text
            text = {
                "comp": self.comp_menu,
                "fun": self.fun_menu,
                "host": self.host_menu,
                "admin": self.admin_menu,
            }[topic]

            embed = discord.Embed(
                title=f":book: {topic.capitalize()} Commands",
                description=text,
                colour=discord.Colour.from_rgb(0, 255, 255)
            )
            # Retrieve guild (to get server icon)
            guild_list = await ctx.bot.config_service.list_guild_configs()
            guild_id = guild_list[0].guild_id
            guild = self.bot.get_guild(guild_id)

            embed.set_footer(text="MKWTASCompBot - A Multi TAS Comp Bot", icon_url=guild.icon.url if guild.icon else None)
            return await ctx.send(embed=embed)

        # Try to fetch a command by name
        cmd: commands.Command = self.bot.get_command(topic)
        if cmd:
            # Build an embed with its signature (usage) and text help
            embed = discord.Embed(
                title=f"`{cmd.qualified_name}`",
                colour=discord.Colour.green()
            )
            # signature
            usage = cmd.usage or f"{ctx.prefix}{cmd.name} {cmd.signature}"
            embed.add_field(
                name="Usage",
                value=f"`{usage}`",
                inline=False
            )
            # description / help
            desc = cmd.help or "No description available."
            embed.add_field(name="Description", value=desc, inline=False)
            # any aliases?
            if cmd.aliases:
                embed.add_field(name="Aliases", value=", ".join(cmd.aliases), inline=False)
            return await ctx.send(embed=embed)

        return await ctx.send(f"❓ No help available for `{topic}`. Try `$help` for a list of topics.")

async def setup(bot: commands.Bot) -> None:
    bot.remove_command("help")
    await bot.add_cog(HelpCommand(bot))
