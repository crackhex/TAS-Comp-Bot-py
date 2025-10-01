"""
Collaborative Team Invite Command
=================================

Module path:
    src/adapters/discord/commands/comp/collab_command.py

Summary:
    Provides a `/collab` command that lets a user invite one or more members to
    join (or form) a team. Each invitee gets an interactive message with
    Accept / Decline buttons; the inviter can also Cancel. When all invitees
    have answered (or the view times out), the service either creates the team
    or adds accepted members to the inviter's existing team.

Responsibilities:
    - Validate that a team competition is active.
    - Prevent self-invites and inviting users already in a team.
    - Enforce the team size limit.
    - Track invite decisions per inviter until all invitees respond (or timeout).
    - Call TeamService to create a team or add members accordingly.
"""

from __future__ import annotations

from typing import Callable, Awaitable, Dict

import discord
from discord.ext import commands
from discord.ext.commands import Greedy

from application.services.team_service import TeamService
from application.services.task_manager import TaskManager


class AcceptDeclineCancelView(discord.ui.View):
    """
    A Discord UI view with Accept / Decline / Cancel buttons for a single invitee.

    Expected callback:
        on_decision(invitee_id: int, accepted: bool) -> Awaitable[None]

    Attributes:
        target (discord.Member): The invitee who is allowed to Accept/Decline.
        inviter_id (int): The inviter's Discord ID; only they can Cancel.
        on_decision (Callable[[int, bool], Awaitable[None]]): Decision callback.
        handled (bool): Whether the invitation has been handled/closed.
        message (discord.Message): The message object holding this view (set after send).
    """

    def __init__(
        self,
        target: discord.Member,
        inviter_id: int,
        on_decision: Callable[[int, bool], Awaitable[None]],
    ):
        """
        Initialize the interactive view.

        Args:
            target: The invitee member.
            inviter_id: The inviter's Discord user ID.
            on_decision: Async callback invoked with (invitee_id, accepted).
        """
        super().__init__(timeout=12 * 3600)  # 12 hours
        self.target = target
        self.inviter_id = inviter_id
        self.on_decision = on_decision
        self.handled = False
        self.message: discord.Message  # will be assigned after sending

    def _disable(self) -> None:
        """Disable all buttons and mark the view as handled."""
        for btn in self.children:
            btn.disabled = True
        self.handled = True

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Accept the invitation (only the invitee can press).

        Effects:
            - Disables the view and edits the message to reflect acceptance.
            - Triggers on_decision(invitee_id, True).
        """
        if interaction.user.id != self.target.id:
            return await interaction.response.send_message(
                "You may not click here!", ephemeral=True
            )
        self._disable()
        await interaction.response.edit_message(
            content=f"{self.target.mention} has **accepted**!", view=self
        )
        await self.on_decision(self.target.id, True)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Decline the invitation (only the invitee can press).

        Effects:
            - Disables the view and edits the message to reflect refusal.
            - Triggers on_decision(invitee_id, False).
        """
        if interaction.user.id != self.target.id:
            return await interaction.response.send_message(
                "You may not click here!", ephemeral=True
            )
        self._disable()
        await interaction.response.edit_message(
            content=f"{self.target.mention} has **declined**!", view=self
        )
        await self.on_decision(self.target.id, False)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.gray)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Cancel the invitation (only the inviter can press).

        Effects:
            - Disables the view and edits the message to reflect cancellation.
            - Treated as a refusal for aggregation purposes.
        """
        if interaction.user.id != self.inviter_id:
            return await interaction.response.send_message(
                "Only the person who invited can cancel!", ephemeral=True
            )
        self._disable()
        await interaction.response.edit_message(
            content=f"Invite to {self.target.mention} cancelled.", view=self
        )
        # Treat cancel as a decline
        await self.on_decision(self.target.id, False)

    async def on_timeout(self) -> None:
        """
        When the view times out, disable controls, edit the message if possible,
        and treat the lack of response as a refusal.
        """
        if not self.handled:
            self._disable()
            try:
                await self.message.edit(
                    content=f"The invite to {self.target.mention} has timed out.",
                    view=self
                )
            except Exception:
                # Message might have been deleted or permissions changed — ignore
                pass
            await self.on_decision(self.target.id, False)


class CollabCommand(commands.Cog):
    """
    Cog exposing the `/collab` command for team collaboration invitations.

    Attributes:
        team_svc (TeamService): Team-related operations (create/add).
        task_mgr (TaskManager): Provides access to the active task.
        _pending (dict[int, dict[int, bool|None]]): Per-inviter decision map.
            Structure: { inviter_id: { invitee_id: Optional[bool] } }
            where None = pending, True = accepted, False = declined.
    """

    def __init__(self, team_svc: TeamService, task_mgr: TaskManager):
        self.team_svc = team_svc
        self.task_mgr = task_mgr
        # pending : {inviter_id: {invitee_id: Optional[bool]}}
        self._pending: Dict[int, Dict[int, bool | None]] = {}

    @commands.command(
        name="collab",
        usage="$collab <member>",
        help=("""
            Invites one or more people to form a team during a collab task.

            Parameters:
            `member`: Competitors to invite (ping them, or write their handle). You may invite more than one at once, if applicable! 
    """),
    )
    async def collab(
        self,
        ctx: commands.Context,
        users: Greedy[discord.Member],
    ):
        """
        Invite one or more members to join the caller's team.

        Flow:
            1) Ensure a team competition is active.
            2) Validate invite list (not empty, no self-invite).
            3) Ensure invitees are not already in teams.
            4) Check the final size does not exceed the limit.
            5) Track pending decisions for the inviter.
            6) Send an interactive Accept/Decline/Cancel view for each invitee.
            7) When everyone has responded (or timed out), create the team or
               add members accordingly via TeamService.

        Args:
            ctx (commands.Context): Command context.
            users (Greedy[discord.Member]): One or more mentioned members.

        Returns:
            None. Sends progress and result messages to the channel.
        """
        author_id = ctx.author.id

        # 1) Must be an active team competition
        task = await self.task_mgr.get_active_task()
        if not task:
            return await ctx.send("There is no ongoing task!")
        if task.team_size <= 1:
            return await ctx.send("This is a solo task. You may **NOT** collaborate!")

        # 2) Validate invite list
        if not users:
            return await ctx.send("You must mention at least one competitor.")
        if any(u.id == author_id for u in users):
            return await ctx.send("You can't invite yourself, silly!")

        # 3) Invitees must not already be in a team
        for u in users:
            if await self.team_svc.get_team_by_member(u.id):
                return await ctx.send(f"❌ {u.display_name} is already in a team.")

        # 4) Enforce max team size (current + invited <= team_size)
        existing_team = await self.team_svc.get_team_by_member(author_id)
        initial_count = len(existing_team.members) if existing_team else 1  # author alone if no team yet
        final_size = initial_count + len(users)
        if final_size > task.team_size:
            return await ctx.send(f"You have exceeded the max team size allowed, which is {task.team_size} maximum.")

        # 5) Initialize pending decisions for this inviter
        self._pending[author_id] = {u.id: None for u in users}

        # 6) Decision callback for each invitee
        async def on_decision(invitee_id: int, accepted: bool):
            pend = self._pending.get(author_id)
            if pend is None:
                return
            pend[invitee_id] = accepted

            # When everyone answered (accepted/declined), aggregate the result
            if all(v is not None for v in pend.values()):
                accepted_ids = [uid for uid, v in pend.items() if v]
                if accepted_ids:
                    existing = await self.team_svc.get_team_by_member(author_id)
                    if existing:
                        # Add all accepted members to the existing team
                        for uid in accepted_ids:
                            await self.team_svc.add_member(existing.id, uid)
                        await ctx.send("Member(s) successfully added to your team!")
                    else:
                        # Create a new team with the author as leader
                        await self.team_svc.create_team(
                            leader_discord_id=author_id,
                            member_ids=accepted_ids,
                            name=None
                        )
                        await ctx.send("Your team has been successfully created!")
                else:
                    await ctx.send("No accepts; the team has not been created.")
                # Cleanup the pending state for this inviter
                del self._pending[author_id]

        # 7) Send the interactive view per invitee
        for u in users:
            view = AcceptDeclineCancelView(
                target=u,
                inviter_id=author_id,
                on_decision=on_decision,
            )
            message = await ctx.send(
                f"{u.mention}, would you like to collaborate with {ctx.author.mention}?",
                view=view,
                allowed_mentions=discord.AllowedMentions.none(),
                suppress_embeds=True,
            )
            # Keep a reference so on_timeout / cancel can edit the original message
            view.message = message


async def setup(bot: commands.Bot):
    await bot.add_cog(
        CollabCommand(
            team_svc=bot.team_service,
            task_mgr=bot.task_manager,
        )
    )
