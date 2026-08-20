import asyncio
import datetime
import enum
import typing

import aiohttp
from discord import Color, Embed, Interaction, Member, TextChannel, app_commands
from discord.ext import commands, tasks

from chii import Config
from chii.data import AniListTracker, AniListUser, BotUser
from chii.utils import CustomChecks, Logger, SimpleUtils, T_Activity_Batch, T_Json


class MediaStatus(enum.Enum):
    COMPLETED = "Completed"
    DROPPED = "Dropped"
    PAUSED = "Paused"

    WATCHED = "Watched"
    REWATCHED = "Rewatched"

    READ = "Read"
    REREAD = "Reread"


class AniListCog(Logger, commands.GroupCog, group_name="anilist"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot
        self.session: aiohttp.ClientSession | None = None

    @typing.override
    async def cog_load(self) -> None:
        self.session = aiohttp.ClientSession()
        self.update_loop_task.start()

        self.logger.info(f"{self.__class__.__name__} loaded, HTTP session opened and update loop task started")

    @typing.override
    async def cog_unload(self) -> None:
        self.logger.debug("Cancelling update loop task")
        self.update_loop_task.cancel()
        self.logger.debug("Update loop task cancelled")

        if self.session:
            self.logger.debug("Closing HTTP session")
            await self.session.close()
            self.logger.debug("HTTP session closed")

            self.session = None

    @tasks.loop(seconds=Config.ANILIST_UPDATE_LOOP_TIME_SECONDS)
    async def update_loop_task(self) -> None:
        self.logger.debug("Running update loop task")
        await self._run_update_loop()
        self.logger.debug("Update loop task finished")

    @update_loop_task.before_loop
    async def before_update_loop_task(self) -> None:
        await self.bot.wait_until_ready()

    @app_commands.command(name="force", description="Manually force an AniList update check for all linked users.")
    @app_commands.check(predicate=CustomChecks.is_bot_owner)
    async def anilist_force(self, interaction: Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        try:
            async with asyncio.timeout(Config.COMMAND_TIMEOUT_SECONDS):
                self.logger.info("Manually forcing AniList update")
                await self._run_update_loop()

        except TimeoutError:
            self.logger.exception("Manually forcing AniList update timed out")
            await interaction.followup.send("The update timed out. Please try again later.", ephemeral=True)

            return

        except Exception:
            self.logger.exception("Manually forcing AniList update failed")
            await interaction.followup.send("Something went wrong while forcing the update.", ephemeral=True)

            return

        self.logger.info(f"Manual AniList update forced by @{interaction.user.global_name} ({interaction.user.id})")

        await interaction.followup.send("Manual AniList update forced by bot owner.", ephemeral=True)

    @app_commands.command(name="channel", description="Set the channel where AniList activity updates will be posted.")
    @app_commands.describe(channel="The text channel that will receive AniList update notifications.")
    @app_commands.check(predicate=CustomChecks.is_bot_owner)
    async def anilist_channel(self, interaction: Interaction, channel: TextChannel) -> None:
        settings = SimpleUtils.get_bot_settings()
        settings.anilist_channel_id = channel.id
        settings.save()

        await interaction.response.send_message(f"AniList notification channel set to {channel.mention}.", ephemeral=True)

        self.logger.info(f"AniList notification channel set to {channel.id}")

    @app_commands.command(name="link", description="Link a Discord user to their AniList account for tracking.")
    @app_commands.describe(member="The Discord user to link the account to.", anilist_username="The AniList username to track.")
    @app_commands.check(predicate=CustomChecks.is_bot_owner)
    async def anilist_link(self, interaction: Interaction, member: Member, anilist_username: str) -> None:
        await interaction.response.defer(ephemeral=True)

        try:
            async with asyncio.timeout(Config.COMMAND_TIMEOUT_SECONDS):
                await self._link_anilist_account(interaction, member, anilist_username)

        except TimeoutError:
            self.logger.exception(f'Linking AniList user "{anilist_username}" timed out')
            await interaction.followup.send("The request timed out. Please try again later.", ephemeral=True)

        except Exception:
            self.logger.exception(f'Linking AniList user "{anilist_username}" failed')
            await interaction.followup.send("Something went wrong while linking that AniList account.", ephemeral=True)

    @app_commands.command(name="unlink", description="Unlink a Discord user's AniList account.")
    @app_commands.describe(member="The Discord user to unlink.")
    @app_commands.check(predicate=CustomChecks.is_bot_owner)
    async def anilist_unlink(self, interaction: Interaction, member: Member) -> None:
        anilist_user = self._get_anilist_user(member.id)

        if not anilist_user:
            await interaction.response.send_message(f"{member.mention} doesn't have a linked AniList account.", ephemeral=True)
            return

        username = anilist_user.username
        anilist_user.delete_instance(recursive=True)

        await interaction.response.send_message(f"Unlinked {member.mention}'s AniList account (**{username}**).", ephemeral=True)

        self.logger.info(f'Unlinked AniList account "{username}" from @{member.global_name} ({member.id}) by @{interaction.user.global_name}')

    @app_commands.command(name="streak", description="Manually set a linked user's AniList streak.")
    @app_commands.describe(
        member="The Discord user whose streak to set.",
        current_streak="The new current streak, in days.",
        longest_streak="The new longest streak, in days. Defaults to the higher of the existing value and current_streak.",
    )
    @app_commands.check(predicate=CustomChecks.is_bot_owner)
    async def anilist_streak(self, interaction: Interaction, member: Member, current_streak: int, longest_streak: int | None = None) -> None:
        if current_streak < 0 or (longest_streak is not None and longest_streak < 0):
            await interaction.response.send_message("Streaks can't be negative.", ephemeral=True)
            return

        anilist_user = self._get_anilist_user(member.id)

        if not anilist_user:
            await interaction.response.send_message(f"{member.mention} doesn't have a linked AniList account.", ephemeral=True)
            return

        anilist_user.current_streak = current_streak
        anilist_user.longest_streak = max(longest_streak if longest_streak is not None else anilist_user.longest_streak, current_streak)

        anilist_user.save()

        await interaction.response.send_message(
            f"Set {member.mention}'s AniList streak to **{anilist_user.current_streak}** (longest: **{anilist_user.longest_streak}**).",
            ephemeral=True,
        )

        self.logger.info(
            f"AniList streak for @{member.global_name} ({member.id}) manually set to {current_streak} "
            f"(longest {anilist_user.longest_streak}) by @{interaction.user.global_name}"
        )

    def _get_anilist_user(self, discord_id: int) -> AniListUser | None:
        bot_user = BotUser.get_or_none(discord_id=discord_id)

        if not bot_user:
            return None

        return AniListUser.get_or_none(bot_user=bot_user)

    async def _link_anilist_account(self, interaction: Interaction, member: Member, anilist_username: str) -> None:
        anilist_user_data = await self._fetch_anilist_user(anilist_username)

        if not anilist_user_data:
            await interaction.followup.send(f'Could not find AniList user "{anilist_username}".', ephemeral=True)
            self.logger.warning(f'Could not find AniList user "{anilist_username}"')

            return

        bot_user: BotUser
        bot_user, _ = BotUser.get_or_create(
            discord_id=member.id,
            defaults={
                "username": member.global_name,
            },
        )

        anilist_user: AniListUser
        anilist_user_exists: AniListUser
        anilist_user, anilist_user_exists = AniListUser.get_or_create(
            bot_user=bot_user,
            defaults={
                "anilist_id": anilist_user_data["id"],
                "username": anilist_user_data["name"],
            },
        )

        if not anilist_user_exists:
            self.logger.debug(f"Creating new AniListUser entry for Discord user @{member.global_name}")

            anilist_user.anilist_id = anilist_user_data["id"]
            anilist_user.username = anilist_user_data["name"]

            anilist_user.synced = False

            anilist_user.last_message_id = None
            anilist_user.last_activity_id = None
            anilist_user.last_activity_at = None

            anilist_user.current_streak = 0
            anilist_user.longest_streak = 0

            anilist_user.save()
            self.logger.info(f'Created new AniListUser entry for @{member.global_name} as "{anilist_user.username}"')

            self.logger.debug(f'Clearing existing trackers for AniList user "{anilist_user.username}"')
            AniListTracker.delete().where(AniListTracker.anilist_user == anilist_user).execute()
            self.logger.debug(f'Cleared existing trackers for AniList user "{anilist_user.username}"')

        self.logger.debug(f'Linking Discord user @{member.global_name} to AniList user "{anilist_username}"')

        await interaction.followup.send(
            f"Linked {member.mention} to [{anilist_user.username}](<https://anilist.co/user/{anilist_user.username}>).",
            ephemeral=True,
        )

        self.logger.info(f'Linked Discord user @{member.global_name} to AniList user "{anilist_username}"')

    async def _run_update_loop(self) -> None:
        self.logger.debug("Finding users to check for updates")
        anilist_users = list(AniListUser.select())
        self.logger.debug(f"Found {len(anilist_users)} users to check for updates")

        if not anilist_users:
            self.logger.info("No users linked for AniList tracking, skipping update cycle")
            return

        bot_settings = SimpleUtils.get_bot_settings()
        notification_channel = SimpleUtils.get_channel(self.bot, bot_settings.anilist_channel_id)

        if not notification_channel:
            self.logger.warning("Invalid AniList notification channel, skipping update cycle")
            return

        activity_batch, account_map = await self._fetch_activity_batch(anilist_users)

        if not activity_batch:
            self.logger.warning("No activity data returned from AniList API")
            return

        if not account_map:
            self.logger.warning("No account map returned from AniList API")
            return

        self.logger.info(f"Running AniList update cycle for {len(anilist_users)} users")

        for alias, activity in activity_batch.items():
            if not activity:
                self.logger.debug(f'No activity payload for alias "{alias}", skipping')
                continue

            account = account_map[alias]

            await self._process_activity(notification_channel, account, activity)

        self.logger.info(f"AniList update cycle completed successfully for {len(anilist_users)} users")

    async def _fetch_anilist_user(self, anilist_username: str) -> T_Json | None:
        self.logger.debug(f'Fetching AniList user "{anilist_username}"')

        query = f"""
            query {{
                User(name: "{anilist_username}") {{
                    id
                    name
                }}
            }}
        """

        data = await self._query_graphql(query)

        if not data:
            self.logger.warning(f'Found no valid data for AniList user "{anilist_username}"')
            return None

        user = data.get("User")
        self.logger.debug(f'Fetched AniList user "{anilist_username}"')

        return user

    async def _fetch_activity_batch(self, anilist_users: list[AniListUser]) -> T_Activity_Batch:
        active_users: dict[str, str] = {}
        users_map: dict[str, AniListUser] = {}

        for i, user in enumerate(anilist_users, start=1):
            user_alias = f"user_{i}"

            active_users[user_alias] = user.username
            users_map[user_alias] = user

        self.logger.debug(f'Fetching batch activity for users: "{active_users}"')

        user_parts: list[str] = []

        for user_alias, username in active_users.items():
            user_parts.append(f"""
                {user_alias}: User(name: "{username}") {{
                    id
                    name
                }}
            """)

        query = f"""
            query {{
                {" ".join(user_parts)}
            }}
        """

        users_data = await self._query_graphql(query)

        if not users_data:
            self.logger.warning("No user data returned from AniList API for batch activity")
            return None, {}

        self.logger.debug("Resolving AniList user IDs for batch activity query")
        id_map = {alias: payload["id"] for alias, payload in users_data.items() if payload}

        if not id_map:
            self.logger.warning("No valid user IDs found in AniList API response")
            return None, {}

        self.logger.debug(f"Resolved {len(id_map)} AniList user IDs for batch activity query")

        activity_parts: list[str] = []

        for user_alias, user_id in id_map.items():
            activity_parts.append(f"""
                {user_alias}: Activity(userId: {user_id}, sort: ID_DESC) {{
                    ... on ListActivity {{
                        id
                        createdAt
                        progress
                        status

                        media {{
                            id
                            idMal
                            type
                            title {{
                                romaji
                            }}
                        }}

                        user {{
                            id
                            name
                            avatar {{
                                medium
                            }}
                        }}
                    }}
                }}
            """)

        query = f"query {{ {' '.join(activity_parts)} }}"

        self.logger.debug("Querying AniList API for user activities batch")
        batch = await self._query_graphql(query)
        self.logger.debug("Queried AniList API for user activities batch")

        return batch, users_map

    async def _query_graphql(self, query: str, variables: T_Json | None = None) -> T_Json | None:
        if self.session is None:
            self.logger.error("AniList HTTP session is not initialized")
            return None

        payload: T_Json = {
            "url": "https://graphql.anilist.co",
            "json": {
                "query": query,
                "variables": variables or {},
            },
        }

        if not variables:
            self.logger.debug("Sending GraphQL query to AniList API with no variables")
        else:
            self.logger.debug(f'Sending GraphQL query to AniList API with variables: "{variables}"')

        try:
            async with self.session.post(**payload) as response:
                self.logger.debug("Sent GraphQL query to AniList API")

                http_ok = 200

                if response.status != http_ok:
                    text = await response.text()
                    self.logger.error(f"AniList API Error {response.status}: {text}")

                    return None

                self.logger.debug("Retrieving data from AniList")
                data = await response.json()

                if "errors" in data:
                    self.logger.error(f"AniList GraphQL Error: {data['errors']}")
                    return None

                self.logger.debug("Retrieved data from AniList")
                return data["data"]

        except Exception:
            self.logger.exception("AniList API Exception")
            return None

    async def _process_activity(self, channel: TextChannel, anilist_user: AniListUser, activity: T_Json) -> None:
        activity_id = activity["id"]
        last_seen = anilist_user.last_activity_id

        if not anilist_user.synced:
            self.logger.debug(f'Syncing AniList user data for "{anilist_user.username}" ({anilist_user.anilist_id})')

            anilist_user.synced = True
            anilist_user.last_activity_id = activity_id
            anilist_user.last_activity_at = datetime.datetime.fromtimestamp(activity["createdAt"], tz=datetime.UTC)

            anilist_user.save()
            self.logger.info(f'Synced data for AniList user "{anilist_user.username}" ({anilist_user.anilist_id})')

            return

        self.logger.debug(f"Activity ID: {activity_id} | Last Seen: {last_seen}")

        if last_seen and activity_id <= last_seen:
            self.logger.debug(f'No new activity for "{anilist_user.username}"')
            return

        anilist_user.last_activity_id = activity_id

        is_progress, old_progress = self._sync_tracker(anilist_user, activity)

        if not is_progress:
            self.logger.debug(f'Activity for "{anilist_user.username}" is not real progress')
            anilist_user.save()

            return

        self._update_streak(anilist_user, activity["createdAt"])

        anilist_user.save()

        embed = await self._build_embed(anilist_user, activity, old_progress)

        self.logger.debug(f'Posting AniList update for "{anilist_user.username}" to #{channel.name}')
        await self._send_update(anilist_user, channel, embed)
        self.logger.info(f'Posted AniList update for "{anilist_user.username}" to #{channel.name}')

    def _sync_tracker(self, account: AniListUser, activity: T_Json) -> tuple[bool, int | None]:
        if not self._is_consumption_activity(activity):
            self.logger.debug("Activity is not a consumption activity. Skipping progress check")
            return False, None

        media = activity["media"]
        new_progress = self._extract_progress(activity)

        self.logger.debug(f"Creating AniListTracker entry for media {media['id']}")

        anilist_tracker: AniListTracker
        anilist_tracker_exists: AniListTracker
        anilist_tracker, anilist_tracker_exists = AniListTracker.get_or_create(
            media_id=media["id"],
            anilist_user=account,
            defaults={
                "type": media["type"],
                "title": media["title"]["romaji"],
            },
        )

        old_progress = anilist_tracker.progress

        if anilist_tracker_exists:
            self.logger.debug(f"Created new AniListTracker entry for media {media['id']}")

        if new_progress is None:
            status = self._extract_status(activity)
            is_progress = status in (MediaStatus.COMPLETED, MediaStatus.DROPPED, MediaStatus.PAUSED)

            if is_progress:
                self.logger.debug("Activity has no numeric progress but it is supported")
            else:
                self.logger.debug("Activity has no numeric progress and it is not supported")

        elif anilist_tracker_exists or new_progress > anilist_tracker.progress:
            self.logger.info(f"Progress of media {media['id']} increased to {new_progress}")

            anilist_tracker.progress = new_progress
            is_progress = True

        else:
            self.logger.debug(f"No progress increase for media {media['id']}")
            is_progress = False

        if not is_progress:
            return False, None

        anilist_tracker.type = media["type"]
        anilist_tracker.title = media["title"]["romaji"]

        anilist_tracker.save()

        return True, old_progress

    def _update_streak(self, anilist_user: AniListUser, timestamp: int) -> None:
        new_activity_at = datetime.datetime.fromtimestamp(timestamp, tz=datetime.UTC)
        last_activity_at = anilist_user.last_activity_at

        if not last_activity_at:
            self.logger.debug(f'Starting new streak for "{anilist_user.username}"')
            anilist_user.current_streak = 1

            self.logger.info(f'New streak started for "{anilist_user.username}"')

        else:
            day_difference = (new_activity_at.date() - last_activity_at.date()).days

            if day_difference == 0:
                self.logger.debug("Activity occurred on the same day. Streak remains unchanged")
                return

            if day_difference == 1:
                self.logger.debug(f'Incrementing streak for "{anilist_user.username}"')
                anilist_user.current_streak += 1
                self.logger.info(f'Streak for "{anilist_user.username}" incremented to {anilist_user.current_streak}')
            else:
                self.logger.debug(f'Resetting streak for "{anilist_user.username}"')
                anilist_user.current_streak = 1
                self.logger.info(f'Streak for "{anilist_user.username}" reset to 1')

        anilist_user.longest_streak = max(anilist_user.longest_streak, anilist_user.current_streak)
        anilist_user.last_activity_at = new_activity_at

    async def _build_embed(self, anilist_user: AniListUser, activity: T_Json, old_progress: int | None) -> Embed:
        self.logger.debug(f'Building embed for "{anilist_user.username}"')

        media = activity["media"]

        title = media["title"]["romaji"]
        status = self._extract_status(activity)
        progress = None

        status_color_map = {
            MediaStatus.COMPLETED: Color.green(),
            MediaStatus.DROPPED: Color.red(),
            MediaStatus.PAUSED: Color.orange(),
        }

        if status in status_color_map:
            title = f"{status.value} {title}"
            color = status_color_map[status]
        else:
            progress = self._extract_progress(activity)
            color = Color.ash_embed()

        media_path = "anime" if media["type"] == "ANIME" else "manga"

        streak_line = f"Current Streak: **{anilist_user.current_streak}** {'day' if anilist_user.current_streak == 1 else 'days'}"

        if progress:
            streak_line = f"\n{streak_line}"

        parts = [
            f"{(status.value if status else 'Unknown')}: **{old_progress} → {progress}**" if progress else None,
            streak_line,
            f"\n\n[**AniList**](https://anilist.co/{media_path}/{media['id']}) | ",
            f"[**MyAnimeList**](https://myanimelist.net/{media_path}/{media['idMal']})",
            f"\n\n<t:{activity['createdAt']}:R>",
        ]

        embed = Embed(color=color, title=title, description="".join(part for part in parts if part))

        user = await self.bot.fetch_user(anilist_user.bot_user.discord_id)

        author_name = f"{activity['user']['name']} (@{user.global_name})" if user else activity["user"]["name"]
        author_url = f"https://anilist.co/user/{activity['user']['id']}"
        author_icon = activity["user"]["avatar"]["medium"]

        embed.set_author(name=author_name, url=author_url, icon_url=author_icon)

        self.logger.debug(f'Built embed for "{anilist_user.username}" ({title})')

        return embed

    async def _send_update(self, anilist_user: AniListUser, channel: TextChannel, embed: Embed) -> None:
        anilist_user.last_message_id = await SimpleUtils.replace_tracked_message(
            self.logger,
            channel,
            anilist_user.last_message_id,
            embed,
            description="update",
        )

        anilist_user.save()

    def _is_consumption_activity(self, activity: T_Json) -> bool:
        status = self._extract_status(activity)

        if not status:
            self.logger.debug("Ignoring non-consumption activity")
            return False

        self.logger.debug(f'Activity "{status}" is a valid consumption activity')

        return True

    def _extract_status(self, activity: T_Json) -> MediaStatus | None:
        self.logger.debug("Extracting status from activity")
        status = activity.get("status", "_").split()[0].capitalize()

        try:
            media_status = MediaStatus(status)
            self.logger.debug(f'Extracted status "{media_status.value}" from activity')

        except ValueError:
            self.logger.warning(f'Unsupported status "{status}" found')
            return None

        else:
            return media_status

    def _extract_progress(self, activity: T_Json) -> int | None:
        self.logger.debug("Extracting progress from activity")
        raw = activity["progress"]

        if not raw:
            self.logger.debug("No progress field found in activity")
            return None

        try:
            text = str(raw).strip()

            if "-" in text:
                text = text.split("-")[-1].strip()

            progress = int(text)
            self.logger.debug(f"Extracted progress value of {progress}")

        except ValueError, TypeError:
            self.logger.warning(f'Failed to extract numeric progress from raw value "{raw}"')
            return None

        else:
            return progress


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AniListCog(bot))
