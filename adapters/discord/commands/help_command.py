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
        self.help_menu = """**MKWTASCompBot** – A Multi TAS Competition Bot  
        List of commands
    
        **Categories**:
          **help**    -– this
          **comp**    -– Public competition-related commands 
          **misc**    -– Miscellaneous commands
          **fun**     -– Fun commands, such as 8ball
          **host**    -– Host-only commands, for handling tasks.  
          **admin**   -– Admin commands
        
        Write `$help <category>` to view help for a specific category.
        Or write `$help <command>` to view help for a specific command.
    """

        self.comp_menu =  """**MKWTASCompBot** - A Multi TAS Comp Bot
    Competition commands\n
      **collab** -- Team up with someone during a collab task!
      **info** -- Shows information about the status of your submission. (DM only)
      **leaveteam** -- Leave your team during a collab task.
      **requesttask** -- Request the task (sent to your DMs) during a speed task.
      **setteamname** -- Changes your team's name in the submission channel. Only during collab tasks.
      **stop-timer** -- Ends your speed task early.
      **teams** -- View the list of teams during a collab task.
    """

        self.fun_menu = """**MKWTASCompBot** - A Multi TAS Comp Bot
    Fun commands 👀\n
    **Commands**:
      **8ball** -- Have a question? Ask the bot for his wisdom!
      **slots** -- Play the famous slot machine. Default number of emotes is 3.
    """

        self.misc_menu = """**MKWTASCompBot** - A Multi TAS Comp Bot
    Miscellaneous commands\n
      **quote** -- Read an inspirational quote!
    """
        self.host_menu = """**MKWTASCompBot** - A Multi TAS Comp Bot
    Host commands :P\n
      **delete-submission** -- Delete someone's submission. 
      **/dm** -- Make the bot dm someone!
      **/edit-submission** -- Edits someone's submission status: time, dq (True/False), dq reason
      **end-task** -- Ends the current task (Warning: No confirmation). This does not clear submissions.
      **get-results** -- Prints the results of the current (ended or not) task. Valid and DQ'ed runs
      **get-submissions** -- Your bread and butter for starting to judge and time runs!
      **hostdissolve** -- Dissolve a team.
      **set-deadline** -- Change the deadline. Time in UNIX!
      **speed-task-desc** -- Set the description of a speed task.
      **speed-task-length** -- Set the duration competitors have to submit to a speed task.
      **speed-task-reminders** -- Set the reminders for a speed task. Up to 4 reminders.
      **stop-timer** -- Ends someone else's speed task early.
      **/start-task** -- Starts a new task. Warning: this deletes last task's stored submissions, results, and 'Current submission' message.
      **/submit** -- Submit a file for someone.
    """

        self.admin_menu = """**MKWTASCompBot** - A Multi TAS Comp Bot
    Admin commands \n
      **config** -- Configure the different roles and channels
      **say** -- Make the bot say something in a channel!
      **set-comp** -- Associate the discord server with a type of competition (mkw, sm64, etc)
      **set-file** -- Set the accepted fie extension for submissions.
      **setname** -- Change someone's name for the submission channel.
      **sync** -- Synchronize the bot's slash commands.
      """

    @commands.command(name="help")
    async def help(self, ctx: commands.Context, *, topic: str = None):
        """
        If called without arguments, show the top-level help menu.
        If `topic` matches a category or command name, dispatch there.
        """
        if topic is None:
            return await ctx.send(self.help_menu)

        match topic.lower():
            case "comp":
                return await ctx.send(self.comp_menu)
            case "fun":
                return await ctx.send(self.fun_menu)
            case "misc":
                return await ctx.send(self.misc_menu)
            case "host":
                return await ctx.send(self.host_menu)
            case "admin":
                return await ctx.send(self.admin_menu)

            # continue code below
            case _:
                pass

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
