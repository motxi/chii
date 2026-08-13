import asyncio
import contextlib
import datetime
import typing
from zoneinfo import ZoneInfo

import aiohttp
from discord import Color, Embed, Interaction, Member, TextChannel, app_commands, ui
from discord.ext import commands, tasks

from chii import Config
from chii.data import BotUser, WaniKaniAuth, WaniKaniStats, WaniKaniUser
from chii.utils import CustomChecks, Logger, SimpleUtils, T_Json

WANIKANI_BASE_URL = "https://api.wanikani.com/v2"
WANIKANI_API_REVISION = "20170710"
WANIKANI_MAX_PAGES = 20
WANIKANI_TOKEN_SETTINGS_URL = "https://www.wanikani.com/settings/personal_access_tokens"


class Summary(typing.NamedTuple):
    review_count: int
    lesson_count: int

    last_review_at: datetime.datetime | None
    last_lesson_at: datetime.datetime | None

    # Only tracked by the daily task.
    # The hourly update loop does not touch streaks.
    streak_broke: bool | None = None


class WaniKaniLinkModal(ui.Modal, title="Link WaniKani Account"):
    token_info = ui.TextDisplay(content=f"Click [Here]({WANIKANI_TOKEN_SETTINGS_URL}) to Generate a Read-Only Token")
    token_label = ui.Label(
        text="WaniKani API Token",
        component=ui.TextInput(placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx", required=True, max_length=100),
    )

    def __init__(self, cog: WaniKaniCog) -> None:
        super().__init__()

        self.cog: WaniKaniCog = cog

    @typing.override
    async def on_submit(self, interaction: Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        token_input = self.token_label.component

        if not isinstance(token_input, ui.TextInput):
            message = "Expected the link modal's component to be a TextInput"
            raise TypeError(message)

        await self.cog.link_wanikani_account(interaction, token_input.value.strip())


class WaniKaniCog(Logger, commands.GroupCog, group_name="wanikani"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot
        self.session: aiohttp.ClientSession | None = None

    @typing.override
    async def cog_load(self) -> None:
        self.session = aiohttp.ClientSession()
        self.update_loop_task.start()
        self.daily_summary_task.start()

        self.logger.info(f"{self.__class__.__name__} loaded, HTTP session opened and update tasks started")

    @typing.override
    async def cog_unload(self) -> None:
        self.logger.debug("Cancelling WaniKani update tasks")
        self.update_loop_task.cancel()
        self.daily_summary_task.cancel()
        self.logger.debug("WaniKani update tasks cancelled")

        if self.session:
            self.logger.debug("Closing HTTP session")
            await self.session.close()
            self.logger.debug("HTTP session closed")

            self.session = None

    @tasks.loop(seconds=Config.WANIKANI_UPDATE_LOOP_TIME_SECONDS)
    async def update_loop_task(self) -> None:
        self.logger.debug("Running WaniKani update loop task")
        await self._run_update_loop()
        self.logger.debug("WaniKani update loop task finished")

    @tasks.loop(time=Config.WANIKANI_DAILY_SUMMARY_TIME.replace(tzinfo=ZoneInfo(Config.WANIKANI_TIMEZONE)))
    async def daily_summary_task(self) -> None:
        self.logger.debug("Running WaniKani daily summary task")
        await self._run_daily_summary()
        self.logger.debug("WaniKani daily summary task finished")

    @app_commands.command(name="channel", description="Set the channel where WaniKani updates will be posted.")
    @app_commands.describe(channel="The text channel that will receive WaniKani notifications.")
    @app_commands.check(predicate=CustomChecks.is_bot_owner)
    async def wanikani_channel(self, interaction: Interaction, channel: TextChannel) -> None:
        settings = SimpleUtils.get_bot_settings()
        settings.wanikani_channel_id = channel.id
        settings.save()

        await interaction.response.send_message(f"WaniKani notification channel set to {channel.mention}.", ephemeral=True)

        self.logger.info(f"WaniKani notification channel set to {channel.id}")

    @app_commands.command(name="allow", description="Authorize a Discord user to link their own WaniKani account.")
    @app_commands.describe(member="The Discord user to authorize.")
    @app_commands.check(predicate=CustomChecks.is_bot_owner)
    async def wanikani_allow(self, interaction: Interaction, member: Member) -> None:
        bot_user: BotUser
        bot_user, _ = BotUser.get_or_create(discord_id=member.id, defaults={"username": member.global_name})

        wanikani_auth_exists: WaniKaniAuth
        _, wanikani_auth_exists = WaniKaniAuth.get_or_create(
            bot_user=bot_user,
            defaults={"authorized_by": interaction.user.id},
        )

        if not wanikani_auth_exists:
            await interaction.response.send_message(f"{member.mention} is already authorized.", ephemeral=True)
            return

        await interaction.response.send_message(f"{member.mention} can now link their WaniKani account.", ephemeral=True)

        self.logger.info(f"@{member.global_name} ({member.id}) authorized to link WaniKani by @{interaction.user.global_name}")

    @app_commands.command(name="revoke", description="Revoke a Discord user's permission to link a WaniKani account.")
    @app_commands.describe(member="The Discord user to revoke.")
    @app_commands.check(predicate=CustomChecks.is_bot_owner)
    async def wanikani_revoke(self, interaction: Interaction, member: Member) -> None:
        bot_user = BotUser.get_or_none(discord_id=member.id)
        deleted = 0

        if bot_user:
            deleted = WaniKaniAuth.delete().where(WaniKaniAuth.bot_user == bot_user).execute()

        if not deleted:
            await interaction.response.send_message(f"{member.mention} wasn't authorized.", ephemeral=True)
            return

        await interaction.response.send_message(f"{member.mention}'s WaniKani linking permission has been revoked.", ephemeral=True)

        self.logger.info(f"@{member.global_name} ({member.id})'s WaniKani linking permission revoked by @{interaction.user.global_name}")

    @app_commands.command(name="link", description="Link your own WaniKani account for tracking.")
    async def wanikani_link(self, interaction: Interaction) -> None:
        bot_user = BotUser.get_or_none(discord_id=interaction.user.id)
        authorized = bot_user is not None and WaniKaniAuth.get_or_none(bot_user=bot_user) is not None

        if not authorized:
            await interaction.response.send_message(
                "You haven't been authorized to link a WaniKani account. Ask the bot owner.",
                ephemeral=True,
            )

            self.logger.warning(f"@{interaction.user.global_name} ({interaction.user.id}) attempted to link WaniKani without authorization")

            return

        await interaction.response.send_modal(WaniKaniLinkModal(self))

    @app_commands.command(name="force", description="Manually force your own WaniKani update check.")
    async def wanikani_force(self, interaction: Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        wanikani_user = self._get_wanikani_user(interaction.user.id)

        if not wanikani_user:
            await interaction.followup.send("You haven't linked a WaniKani account yet.", ephemeral=True)
            return

        bot_settings = SimpleUtils.get_bot_settings()
        notification_channel = SimpleUtils.get_channel(self.bot, bot_settings.wanikani_channel_id)

        if not notification_channel:
            await interaction.followup.send("The WaniKani notification channel hasn't been set up yet.", ephemeral=True)
            self.logger.warning("Invalid WaniKani notification channel, skipping forced check")

            return

        try:
            async with asyncio.timeout(Config.COMMAND_TIMEOUT_SECONDS):
                self.logger.info(f"Manually forcing WaniKani update for @{interaction.user.global_name}")
                await self._check_user_update(notification_channel, wanikani_user)

        except TimeoutError:
            self.logger.exception("Manually forcing WaniKani update timed out")
            await interaction.followup.send("The update timed out. Please try again later.", ephemeral=True)

            return

        except Exception:
            self.logger.exception("Manually forcing WaniKani update failed")
            await interaction.followup.send("Something went wrong while forcing the update.", ephemeral=True)

            return

        self.logger.info(f"Manual WaniKani update forced by @{interaction.user.global_name} ({interaction.user.id})")

        await interaction.followup.send("Manual WaniKani update forced.", ephemeral=True)

    async def link_wanikani_account(self, interaction: Interaction, api_token: str) -> None:
        wanikani_user_data = await self._fetch_wanikani_user(api_token)

        if not wanikani_user_data:
            await interaction.followup.send("Could not verify that WaniKani API token.", ephemeral=True)
            self.logger.warning(f"Could not verify WaniKani API token for @{interaction.user.global_name}")

            return

        bot_user: BotUser
        bot_user, _ = BotUser.get_or_create(
            discord_id=interaction.user.id,
            defaults={"username": interaction.user.global_name},
        )

        wanikani_user: WaniKaniUser
        wanikani_user_exists: WaniKaniUser
        wanikani_user, wanikani_user_exists = WaniKaniUser.get_or_create(
            bot_user=bot_user,
            defaults={
                "wanikani_id": wanikani_user_data["id"],
                "username": wanikani_user_data["username"],
                "api_token": api_token,
            },
        )

        if not wanikani_user_exists:
            self.logger.debug(f"Updating existing WaniKaniUser entry for @{interaction.user.global_name}")

            wanikani_user.wanikani_id = wanikani_user_data["id"]
            wanikani_user.username = wanikani_user_data["username"]
            wanikani_user.api_token = api_token

            wanikani_user.save()

            self.logger.debug(f'Resetting WaniKaniStats for "{wanikani_user.username}"')
            WaniKaniStats.delete().where(WaniKaniStats.wanikani_user == wanikani_user).execute()

        WaniKaniStats.get_or_create(wanikani_user=wanikani_user)

        self.logger.info(f'Linked Discord user @{interaction.user.global_name} to WaniKani user "{wanikani_user.username}"')

        await interaction.followup.send(
            f"Linked your account to [{wanikani_user.username}](<https://www.wanikani.com/users/{wanikani_user.username}>).",
            ephemeral=True,
        )

    def _get_wanikani_user(self, discord_id: int) -> WaniKaniUser | None:
        bot_user = BotUser.get_or_none(discord_id=discord_id)

        if not bot_user:
            return None

        return WaniKaniUser.get_or_none(bot_user=bot_user)

    async def _run_update_loop(self) -> None:
        self.logger.debug("Finding WaniKani users to check for updates")
        wanikani_users = list(WaniKaniUser.select())
        self.logger.debug(f"Found {len(wanikani_users)} WaniKani users to check for updates")

        if not wanikani_users:
            self.logger.info("No users linked for WaniKani tracking, skipping update cycle")
            return

        bot_settings = SimpleUtils.get_bot_settings()
        notification_channel = SimpleUtils.get_channel(self.bot, bot_settings.wanikani_channel_id)

        if not notification_channel:
            self.logger.warning("Invalid WaniKani notification channel, skipping update cycle")
            return

        self.logger.info(f"Running WaniKani update cycle for {len(wanikani_users)} users")

        for wanikani_user in wanikani_users:
            await self._check_user_update(notification_channel, wanikani_user)

        self.logger.info(f"WaniKani update cycle completed for {len(wanikani_users)} users")

    async def _check_user_update(self, channel: TextChannel, wanikani_user: WaniKaniUser) -> None:
        wanikani_stats: WaniKaniStats
        wanikani_stats, _ = WaniKaniStats.get_or_create(wanikani_user=wanikani_user)

        now = datetime.datetime.now(tz=datetime.UTC)

        # Guard against clock skew between this host and WaniKani's servers.
        #
        # An `updated_after` timestamp equal to (or after) "now" is rejected
        # with a 422.
        safe_now = now - datetime.timedelta(seconds=10)

        review_since = wanikani_stats.last_review_notified_at or safe_now
        lesson_since = wanikani_stats.last_lesson_notified_at or safe_now

        review_result = await self._count_reviews_since(wanikani_user.api_token, review_since)
        lesson_items = await self._fetch_started_assignments_since(wanikani_user.api_token, lesson_since)

        if review_result is None or lesson_items is None:
            self.logger.warning(f'Failed to fetch WaniKani data for "{wanikani_user.username}", skipping this check')
            return

        review_count, last_review_at = review_result
        lesson_count = len(lesson_items)

        last_lesson_at = self._latest_lesson_at(lesson_items)

        wanikani_stats.last_review_notified_at = now
        wanikani_stats.last_lesson_notified_at = now

        wanikani_stats.save()

        if not review_count and not lesson_count:
            self.logger.debug(f'No new WaniKani activity for "{wanikani_user.username}"')
            return

        summary = Summary(
            review_count=review_count,
            lesson_count=lesson_count,
            last_review_at=last_review_at,
            last_lesson_at=last_lesson_at,
        )

        embed = await self._build_update_embed(wanikani_user, summary)

        self.logger.debug(f'Posting WaniKani update for "{wanikani_user.username}" to #{channel.name}')
        await channel.send(embed=embed)
        self.logger.info(f'Posted WaniKani update for "{wanikani_user.username}" to #{channel.name}')

    async def _run_daily_summary(self) -> None:
        self.logger.debug("Finding WaniKani users for daily summary")
        wanikani_users = list(WaniKaniUser.select())
        self.logger.debug(f"Found {len(wanikani_users)} WaniKani users for daily summary")

        if not wanikani_users:
            self.logger.info("No users linked for WaniKani tracking, skipping daily summary")
            return

        bot_settings = SimpleUtils.get_bot_settings()
        notification_channel = SimpleUtils.get_channel(self.bot, bot_settings.wanikani_channel_id)

        if not notification_channel:
            self.logger.warning("Invalid WaniKani notification channel, skipping daily summary")
            return

        timezone = ZoneInfo(Config.WANIKANI_TIMEZONE)
        now_local = datetime.datetime.now(tz=timezone)
        start_of_today = now_local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(datetime.UTC)

        self.logger.info(f"Running WaniKani daily summary for {len(wanikani_users)} users")

        for wanikani_user in wanikani_users:
            await self._process_daily_user(notification_channel, wanikani_user, start_of_today)

        self.logger.info(f"WaniKani daily summary completed for {len(wanikani_users)} users")

    async def _process_daily_user(self, channel: TextChannel, wanikani_user: WaniKaniUser, start_of_today: datetime.datetime) -> None:
        wanikani_stats: WaniKaniStats
        wanikani_stats, _ = WaniKaniStats.get_or_create(wanikani_user=wanikani_user)

        review_result = await self._count_reviews_since(wanikani_user.api_token, start_of_today)
        lesson_items = await self._fetch_started_assignments_since(wanikani_user.api_token, start_of_today)

        if review_result is None or lesson_items is None:
            self.logger.warning(f'Failed to fetch WaniKani daily data for "{wanikani_user.username}", skipping summary')
            return

        review_count, last_review_at = review_result
        lesson_count = len(lesson_items)
        last_lesson_at = self._latest_lesson_at(lesson_items)

        review_had_activity = review_count > 0
        lesson_had_activity = lesson_count > 0
        had_activity = review_had_activity or lesson_had_activity

        streak_broke = not had_activity and wanikani_stats.current_streak > 0

        wanikani_stats.current_streak, wanikani_stats.longest_streak = self._advance_streak(
            wanikani_stats.current_streak,
            wanikani_stats.longest_streak,
            had_activity=had_activity,
        )

        wanikani_stats.total_reviews += review_count
        wanikani_stats.total_lessons += lesson_count

        now = datetime.datetime.now(tz=datetime.UTC)

        if review_had_activity:
            wanikani_stats.last_review_at = now
        if lesson_had_activity:
            wanikani_stats.last_lesson_at = now

        summary = Summary(
            review_count=review_count,
            lesson_count=lesson_count,
            last_review_at=last_review_at,
            last_lesson_at=last_lesson_at,
            streak_broke=streak_broke,
        )

        embed = await self._build_daily_embed(wanikani_user, wanikani_stats, summary)

        old_message_id = wanikani_stats.last_message_id

        if old_message_id:
            self.logger.debug(f"Deleting previous WaniKani daily summary message {old_message_id}")

            with contextlib.suppress(Exception):
                await channel.get_partial_message(old_message_id).delete()
                self.logger.debug(f"Deleted previous WaniKani daily summary message {old_message_id}")

        self.logger.debug(f"Sending new WaniKani daily summary to #{channel.name}")
        message = await channel.send(embed=embed)

        wanikani_stats.last_message_id = message.id
        wanikani_stats.save()

        self.logger.info(f'Posted WaniKani daily summary for "{wanikani_user.username}" to #{channel.name}')

    def _advance_streak(self, current: int, longest: int, *, had_activity: bool) -> tuple[int, int]:
        new_current = current + 1 if had_activity else 0
        new_longest = max(longest, new_current)

        return new_current, new_longest

    def _latest_review_at(self, reviews_data: T_Json) -> datetime.datetime | None:
        last_review_at_raw = reviews_data.get("data_updated_at")

        return datetime.datetime.fromisoformat(last_review_at_raw) if last_review_at_raw else None

    def _latest_lesson_at(self, lesson_items: list[T_Json]) -> datetime.datetime | None:
        return max(
            (datetime.datetime.fromisoformat(item["data"]["started_at"]) for item in lesson_items),
            default=None,
        )

    async def _set_wanikani_author(self, embed: Embed, wanikani_user: WaniKaniUser) -> None:
        user = await self.bot.fetch_user(wanikani_user.bot_user.discord_id)

        author_name = f"{wanikani_user.username} (@{user.global_name})" if user else wanikani_user.username
        author_icon = user.display_avatar.url if user else None

        embed.set_author(
            name=author_name,
            url=f"https://www.wanikani.com/users/{wanikani_user.username}",
            icon_url=author_icon,
        )

    async def _build_update_embed(self, wanikani_user: WaniKaniUser, summary: Summary) -> Embed:
        parts = [
            f"Reviews: **{summary.review_count}**\n" if summary.review_count else None,
            f"Lessons: **{summary.lesson_count}**\n" if summary.lesson_count else None,
            f"\nLast review: <t:{int(summary.last_review_at.timestamp())}:R>" if summary.review_count and summary.last_review_at else None,
        ]

        embed = Embed(
            color=Color.ash_embed(),
            title="WaniKani Update",
            description="".join(part for part in parts if part),
        )

        await self._set_wanikani_author(embed, wanikani_user)

        return embed

    async def _build_daily_embed(self, wanikani_user: WaniKaniUser, stats: WaniKaniStats, summary: Summary) -> Embed:
        color = Color.red() if summary.streak_broke else Color.green()

        streak_line = f"Streak: **{stats.current_streak}** {'day' if stats.current_streak == 1 else 'days'}"

        if summary.streak_broke:
            streak_line += " — Streak Broken!"

        parts = [
            f"Reviews: **{summary.review_count}** (Total = **{stats.total_reviews}**)",
            f"\nLessons: **{summary.lesson_count}** (Total = **{stats.total_lessons}**)",
            f"\n\n{streak_line}",
            f"\n\nLast review: <t:{int(summary.last_review_at.timestamp())}:R>" if summary.review_count and summary.last_review_at else None,
            f"\nLast lesson: <t:{int(summary.last_lesson_at.timestamp())}:R>" if summary.lesson_count and summary.last_lesson_at else None,
        ]

        embed = Embed(color=color, title="Daily WaniKani Summary", description="".join(part for part in parts if part))

        await self._set_wanikani_author(embed, wanikani_user)

        return embed

    async def _wanikani_get(self, api_token: str, url: str, params: T_Json | None = None) -> T_Json | None:
        if self.session is None:
            self.logger.error("WaniKani HTTP session is not initialized")
            return None

        headers = {
            "Authorization": f"Bearer {api_token}",
            "Wanikani-Revision": WANIKANI_API_REVISION,
        }

        try:
            async with self.session.get(url, headers=headers, params=params) as response:
                http_ok = 200

                if response.status != http_ok:
                    text = await response.text()
                    self.logger.error(f"WaniKani API Error {response.status}: {text}")

                    return None

                return await response.json()

        except Exception:
            self.logger.exception("WaniKani API Exception")
            return None

    async def _fetch_wanikani_user(self, api_token: str) -> T_Json | None:
        self.logger.debug("Fetching WaniKani user")

        data = await self._wanikani_get(api_token, f"{WANIKANI_BASE_URL}/user")

        if not data:
            self.logger.warning("Found no valid data for WaniKani user")
            return None

        self.logger.debug("Fetched WaniKani user")

        return data.get("data")

    async def _count_reviews_since(self, api_token: str, since: datetime.datetime) -> tuple[int, datetime.datetime | None] | None:
        self.logger.debug(f"Counting WaniKani reviews since {since.isoformat()}")

        data = await self._wanikani_get(api_token, f"{WANIKANI_BASE_URL}/reviews", params={"updated_after": since.isoformat()})

        if data is None:
            return None

        return data.get("total_count", 0), self._latest_review_at(data)

    async def _fetch_started_assignments_since(self, api_token: str, since: datetime.datetime) -> list[T_Json] | None:
        self.logger.debug(f"Fetching WaniKani started assignments since {since.isoformat()}")

        items = await self._paginate_wanikani(
            api_token,
            f"{WANIKANI_BASE_URL}/assignments",
            {"started": "true", "updated_after": since.isoformat()},
        )

        if items is None:
            return None

        started_assignments: list[T_Json] = []

        for item in items:
            started_at_raw = item.get("data", {}).get("started_at")

            if not started_at_raw:
                continue

            started_at = datetime.datetime.fromisoformat(started_at_raw)

            if started_at >= since:
                started_assignments.append(item)

        self.logger.debug(f"Found {len(started_assignments)} WaniKani lessons since {since.isoformat()}")

        return started_assignments

    async def _paginate_wanikani(self, api_token: str, url: str, params: T_Json | None) -> list[T_Json] | None:
        items: list[T_Json] = []
        next_url: str | None = url
        request_params = params

        for _ in range(WANIKANI_MAX_PAGES):
            if next_url is None:
                break

            data = await self._wanikani_get(api_token, next_url, params=request_params)
            request_params = None

            if data is None:
                return None

            items.extend(data.get("data", []))
            next_url = data.get("pages", {}).get("next_url")

        return items


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WaniKaniCog(bot))
