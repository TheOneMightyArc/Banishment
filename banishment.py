import discord
from redbot.core import commands, Config
from typing import Union

# --- Configuration ---
# These are the IDs you provided.
# You can change them here if they ever need updating.
REQUIRED_ROLE_ID = 1004617849807065168  # Role required to use the commands
MUTED_ROLE_ID = 1122374629584027709     # The "Muted" role to apply

# --- Custom Check ---
# This creates a custom check to see if the user has the required role.
# If they don't, it sends the specific message you wanted.
def is_worthy():
    async def predicate(ctx: commands.Context):
        # This check will not work in DMs
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return False
        
        # Check if the required role ID is in the list of the author's role IDs.
        author_role_ids = {role.id for role in ctx.author.roles}
        if REQUIRED_ROLE_ID not in author_role_ids:
            await ctx.send("You are not worthy of the Throne.")
            return False
        return True
    return commands.check(predicate)


class Banishment(commands.Cog):
    """Banish and unbanish members by role-stripping."""

    def __init__(self, bot):
        self.bot = bot
        # Initialize the Config system for this cog.
        self.config = Config.get_conf(
            self, 
            identifier="8675309_Banishment", # Unique ID for this cog's data
            force_registration=True
        )
        # Define the default data structure we'll use for each server (guild).
        default_guild = {
            "banished_users": {}  # e.g. {"user_id": {"saved_role_ids": [id1, id2, ...]}}
        }
        self.config.register_guild(**default_guild)

    @commands.command()
    @commands.guild_only()
    @is_worthy() # Apply the custom permission check
    @commands.bot_has_permissions(manage_roles=True)
    async def banish(self, ctx: commands.Context, *, member_to_banish: discord.Member):
        """Removes all roles from a user and gives them a Muted role."""

        # --- Pre-check validations ---
        if member_to_banish.id == ctx.author.id:
            return await ctx.send("You cannot banish yourself.")
        if member_to_banish.id == ctx.guild.owner_id:
            return await ctx.send("You cannot banish the server owner.")
        if member_to_banish.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            return await ctx.send("You cannot banish someone with an equal or higher role than you.")
        if member_to_banish.top_role >= ctx.guild.me.top_role:
             return await ctx.send("I cannot banish this user. Their role is higher than mine.")
        
        muted_role = ctx.guild.get_role(MUTED_ROLE_ID)
        if not muted_role:
            return await ctx.send(f"Error: The 'Muted' role with ID `{MUTED_ROLE_ID}` was not found on this server. Please create it or check the ID.")

        async with self.config.guild(ctx.guild).banished_users() as banished_users:
            if str(member_to_banish.id) in banished_users:
                return await ctx.send(f"{member_to_banish.mention} is already banished.")

        # --- Save Roles and Banish ---
        try:
            # Get all roles except @everyone, which cannot be removed.
            roles_to_remove = [role for role in member_to_banish.roles if not role.is_default()]
            role_ids_to_save = [role.id for role in roles_to_remove]
            
            # Save the roles to config FIRST
            async with self.config.guild(ctx.guild).banished_users() as banished_users:
                banished_users[str(member_to_banish.id)] = {"saved_role_ids": role_ids_to_save}

            # Perform the role changes
            await member_to_banish.remove_roles(*roles_to_remove, reason=f"Banished by {ctx.author.display_name}")
            await member_to_banish.add_roles(muted_role, reason=f"Banished by {ctx.author.display_name}")

        except discord.Forbidden:
            return await ctx.send("I do not have permissions to modify this user's roles. My role may be too low in the hierarchy.")
        except Exception as e:
            return await ctx.send(f"An unexpected error occurred: {e}")
        
        await ctx.send(f"It has succeeded and that {member_to_banish.mention} has been banished to the corner.")


    @commands.command()
    @commands.guild_only()
    @is_worthy() # Apply the same permission check
    @commands.bot_has_permissions(manage_roles=True)
    async def unbanish(self, ctx: commands.Context, *, member_to_unbanish: discord.Member):
        """Restores a banished user's roles and removes the Muted role."""

        muted_role = ctx.guild.get_role(MUTED_ROLE_ID)
        if not muted_role:
            return await ctx.send(f"Error: The 'Muted' role with ID `{MUTED_ROLE_ID}` was not found on this server. I cannot complete the unbanish process without it.")

        # --- Check if user is banished and get their saved roles ---
        banished_user_data = None
        async with self.config.guild(ctx.guild).banished_users() as banished_users:
            if str(member_to_unbanish.id) in banished_users:
                banished_user_data = banished_users.pop(str(member_to_unbanish.id))
            else:
                return await ctx.send(f"{member_to_unbanish.mention} is not currently banished.")
        
        if not banished_user_data or "saved_role_ids" not in banished_user_data:
            return await ctx.send("Could not find role data for this user. Cannot restore roles.")

        # --- Restore Roles and Unbanish ---
        try:
            saved_role_ids = banished_user_data["saved_role_ids"]
            # Convert role IDs back to role objects, filtering out any that may have been deleted.
            roles_to_restore = [role for role_id in saved_role_ids if (role := ctx.guild.get_role(role_id))]

            # Perform the role changes
            await member_to_unbanish.add_roles(*roles_to_restore, reason=f"Unbanished by {ctx.author.display_name}")
            # Only remove the muted role if they have it
            if muted_role in member_to_unbanish.roles:
                await member_to_unbanish.remove_roles(muted_role, reason=f"Unbanished by {ctx.author.display_name}")

        except discord.Forbidden:
            return await ctx.send("I do not have permissions to modify this user's roles. My role may be too low in the hierarchy. Their roles were not restored, but they are no longer marked as banished.")
        except Exception as e:
            return await ctx.send(f"An unexpected error occurred: {e}")

        await ctx.send(f"It was successful. {member_to_unbanish.mention} has been unbanished and their roles restored.")
