from __future__ import annotations


class PostgresSchema:
    @staticmethod
    def statements() -> tuple[str, ...]:
        return (
            """
            CREATE TABLE IF NOT EXISTS messages (
                id BIGINT PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                content TEXT,
                deleted BIGINT DEFAULT 0,
                edited BIGINT DEFAULT 0,
                edited_content TEXT,
                ai_flagged BIGINT DEFAULT 0,
                ai_reason TEXT,
                reply_to_message_id BIGINT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel_id)",
            "CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_messages_deleted ON messages(deleted)",
            "CREATE INDEX IF NOT EXISTS idx_messages_guild_time ON messages(guild_id, timestamp)",
            """
            CREATE TABLE IF NOT EXISTS punishments (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                mod_id BIGINT,
                type TEXT NOT NULL,
                reason TEXT,
                duration TEXT,
                expires_at TIMESTAMP,
                active BIGINT DEFAULT 1,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                guild_id BIGINT,
                moderator_id BIGINT,
                duration_seconds BIGINT,
                is_active BIGINT,
                created_at TIMESTAMP,
                retention_until TIMESTAMP
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_punishments_user ON punishments(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_punishments_active ON punishments(active)",
            "CREATE INDEX IF NOT EXISTS idx_punishments_expires ON punishments(expires_at)",
            """
            CREATE TABLE IF NOT EXISTS streamers (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                guild_id BIGINT NOT NULL DEFAULT 0,
                platform TEXT NOT NULL CHECK(platform IN ('twitch', 'youtube', 'kick')),
                channel_url TEXT NOT NULL,
                channel_name TEXT,
                template TEXT,
                ping_role_id BIGINT,
                active BIGINT DEFAULT 1,
                last_stream_id TEXT,
                last_check TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, guild_id, platform)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_streamers_user ON streamers(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_streamers_platform ON streamers(platform)",
            "CREATE INDEX IF NOT EXISTS idx_streamers_active ON streamers(active)",
            "CREATE INDEX IF NOT EXISTS idx_streamers_guild ON streamers(guild_id)",
            """
            CREATE TABLE IF NOT EXISTS server_stats (
                id BIGSERIAL PRIMARY KEY,
                date TEXT UNIQUE,
                members_total BIGINT DEFAULT 0,
                members_online BIGINT DEFAULT 0,
                members_voice BIGINT DEFAULT 0,
                messages_count BIGINT DEFAULT 0,
                voice_hours DOUBLE PRECISION DEFAULT 0,
                new_members BIGINT DEFAULT 0,
                left_members BIGINT DEFAULT 0,
                top_channel_id BIGINT,
                top_channel_count BIGINT
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_stats_date ON server_stats(date)",
            """
            CREATE TABLE IF NOT EXISTS roles (
                role_id BIGINT PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                name TEXT NOT NULL,
                color BIGINT,
                position BIGINT,
                is_auto_assign BIGINT DEFAULT 0,
                is_public BIGINT DEFAULT 1,
                display_emoji TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_roles_guild ON roles(guild_id)",
            "CREATE INDEX IF NOT EXISTS idx_roles_auto_assign ON roles(is_auto_assign)",
            """
            CREATE TABLE IF NOT EXISTS channel_config (
                channel_id BIGINT PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                is_ai_whitelisted BIGINT DEFAULT 0,
                welcome_enabled BIGINT DEFAULT 1,
                slowmode_override BIGINT,
                auto_delete_after BIGINT,
                custom_name TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_channel_guild ON channel_config(guild_id)",
            "CREATE INDEX IF NOT EXISTS idx_channel_whitelist ON channel_config(is_ai_whitelisted)",
            """
            CREATE TABLE IF NOT EXISTS ai_moderation_channels (
                guild_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, channel_id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_ai_moderation_channels_guild ON ai_moderation_channels(guild_id)",
            """
            CREATE TABLE IF NOT EXISTS ai_moderation_settings (
                guild_id BIGINT PRIMARY KEY,
                policy_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS ai_moderation_events (
                id BIGSERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                message_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                risk_score DOUBLE PRECISION NOT NULL,
                decision_action TEXT NOT NULL,
                proposed_action TEXT,
                primary_label TEXT NOT NULL,
                labels_json JSONB NOT NULL DEFAULT '[]'::jsonb,
                confidence DOUBLE PRECISION NOT NULL DEFAULT 0,
                latency_ms INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (guild_id, message_id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_ai_moderation_events_guild_created ON ai_moderation_events(guild_id, created_at DESC)",
            """
            CREATE TABLE IF NOT EXISTS ai_moderation_review_items (
                id BIGSERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                message_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                message_text TEXT NOT NULL,
                risk_score DOUBLE PRECISION NOT NULL,
                severity INTEGER NOT NULL DEFAULT 0,
                action TEXT NOT NULL,
                labels_json JSONB NOT NULL DEFAULT '[]'::jsonb,
                status TEXT NOT NULL DEFAULT 'OPEN',
                revision INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP,
                resolved_by BIGINT,
                UNIQUE (guild_id, message_id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_ai_review_open ON ai_moderation_review_items(guild_id, status, created_at DESC)",
            "ALTER TABLE ai_moderation_review_items ADD COLUMN IF NOT EXISTS revision INTEGER NOT NULL DEFAULT 1",
            "ALTER TABLE ai_moderation_review_items ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
            """
            CREATE TABLE IF NOT EXISTS ai_moderation_review_audit (
                id BIGSERIAL PRIMARY KEY,
                review_item_id BIGINT NOT NULL REFERENCES ai_moderation_review_items(id) ON DELETE CASCADE,
                guild_id BIGINT NOT NULL,
                actor_id BIGINT NOT NULL,
                action TEXT NOT NULL,
                before_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                after_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_ai_review_audit_item ON ai_moderation_review_audit(review_item_id, created_at DESC)",
            """
            CREATE TABLE IF NOT EXISTS ai_moderation_role_restorations (
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                role_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb,
                restore_at TIMESTAMP NOT NULL,
                restored_at TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, user_id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_ai_role_restorations_due ON ai_moderation_role_restorations(restore_at) WHERE restored_at IS NULL",
            """
            CREATE TABLE IF NOT EXISTS ai_moderation_metrics_access (
                guild_id BIGINT PRIMARY KEY,
                granted_by BIGINT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS user_stats (
                user_id BIGINT NOT NULL,
                guild_id BIGINT NOT NULL,
                messages_count BIGINT DEFAULT 0,
                voice_minutes BIGINT DEFAULT 0,
                warnings_count BIGINT DEFAULT 0,
                last_message TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, guild_id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_user_stats_messages ON user_stats(messages_count DESC)",
            """
            CREATE TABLE IF NOT EXISTS role_panel_messages (
                id BIGSERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                message_id BIGINT NOT NULL,
                embed_title TEXT DEFAULT 'Выберите свою роль',
                embed_description TEXT DEFAULT 'Нажмите на кнопку, чтобы получить или снять роль',
                embed_color BIGINT DEFAULT 65280,
                created_by BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BIGINT DEFAULT 1,
                interaction_mode TEXT NOT NULL DEFAULT 'buttons',
                view_fingerprint TEXT,
                last_rendered_fingerprint TEXT,
                UNIQUE(guild_id, channel_id, message_id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_role_panel_messages_guild ON role_panel_messages(guild_id)",
            "CREATE INDEX IF NOT EXISTS idx_role_panel_messages_active ON role_panel_messages(is_active)",
            """
            CREATE TABLE IF NOT EXISTS role_panel_buttons (
                id BIGSERIAL PRIMARY KEY,
                panel_message_id BIGINT NOT NULL REFERENCES role_panel_messages(id) ON DELETE CASCADE,
                role_id BIGINT NOT NULL,
                role_name TEXT NOT NULL,
                emoji TEXT,
                position BIGINT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(panel_message_id, role_id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_role_panel_buttons_panel ON role_panel_buttons(panel_message_id)",
            """
            CREATE TABLE IF NOT EXISTS message_logs (
                id BIGSERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                message_id BIGINT NOT NULL,
                author_id BIGINT NOT NULL,
                author_name TEXT NOT NULL,
                content TEXT,
                event_type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                retention_until TIMESTAMP
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_message_logs_guild ON message_logs(guild_id)",
            "CREATE INDEX IF NOT EXISTS idx_message_logs_event ON message_logs(event_type)",
            "CREATE INDEX IF NOT EXISTS idx_message_logs_retention ON message_logs(retention_until)",
            """
            CREATE TABLE IF NOT EXISTS guild_event_logs (
                id BIGSERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                channel_id BIGINT,
                actor_id BIGINT,
                actor_name TEXT,
                target_id BIGINT,
                target_name TEXT,
                event_type TEXT NOT NULL,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                retention_until TIMESTAMP
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_guild_event_logs_guild ON guild_event_logs(guild_id)",
            "CREATE INDEX IF NOT EXISTS idx_guild_event_logs_event ON guild_event_logs(event_type)",
            "CREATE INDEX IF NOT EXISTS idx_guild_event_logs_retention ON guild_event_logs(retention_until)",
            """
            CREATE TABLE IF NOT EXISTS server_channel_purposes (
                id BIGSERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                purpose TEXT NOT NULL,
                channel_id BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(guild_id, purpose)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_scp_guild ON server_channel_purposes(guild_id)",
            "CREATE INDEX IF NOT EXISTS idx_scp_purpose ON server_channel_purposes(purpose)",
            """
            CREATE TABLE IF NOT EXISTS welcome_config (
                guild_id BIGINT PRIMARY KEY,
                title TEXT DEFAULT 'Добро пожаловать!',
                description TEXT,
                thumbnail_url TEXT,
                footer_text TEXT,
                footer_icon_url TEXT,
                color BIGINT DEFAULT 5763719,
                is_enabled BIGINT DEFAULT 1,
                rules_channel_id BIGINT,
                roles_channel_id BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS voice_rooms (
                channel_id BIGINT PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                owner_id BIGINT NOT NULL,
                admin_id BIGINT,
                name TEXT NOT NULL,
                is_persistent BIGINT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_voice_rooms_guild ON voice_rooms(guild_id)",
            "CREATE INDEX IF NOT EXISTS idx_voice_rooms_owner ON voice_rooms(owner_id)",
            "CREATE INDEX IF NOT EXISTS idx_voice_rooms_admin ON voice_rooms(admin_id)",
            """
            CREATE TABLE IF NOT EXISTS voice_room_members (
                channel_id BIGINT NOT NULL,
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(channel_id, user_id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_voice_room_members_guild ON voice_room_members(guild_id)",
            "CREATE INDEX IF NOT EXISTS idx_voice_room_members_user ON voice_room_members(user_id)",
            """
            CREATE TABLE IF NOT EXISTS voice_config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS voice_sessions (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                guild_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                joined_at TIMESTAMP NOT NULL,
                left_at TIMESTAMP,
                duration_seconds BIGINT DEFAULT 0
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_vs_guild ON voice_sessions(guild_id)",
            "CREATE INDEX IF NOT EXISTS idx_vs_user ON voice_sessions(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_vs_channel ON voice_sessions(channel_id)",
            "CREATE INDEX IF NOT EXISTS idx_vs_left ON voice_sessions(left_at)",
            """
            CREATE TABLE IF NOT EXISTS server_role_purposes (
                id BIGSERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                purpose TEXT NOT NULL,
                role_id BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(guild_id, purpose)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_srp_guild ON server_role_purposes(guild_id)",
            "CREATE INDEX IF NOT EXISTS idx_srp_purpose ON server_role_purposes(purpose)",
            """
            CREATE TABLE IF NOT EXISTS activity_synced_roles (
                id BIGSERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                role_id BIGINT NOT NULL,
                name TEXT NOT NULL,
                color BIGINT DEFAULT 0,
                position BIGINT DEFAULT 0,
                permissions BIGINT DEFAULT 0,
                is_admin BIGINT DEFAULT 0,
                managed BIGINT DEFAULT 0,
                mentionable BIGINT DEFAULT 0,
                synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(guild_id, role_id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_activity_synced_roles_guild ON activity_synced_roles(guild_id)",
            "CREATE INDEX IF NOT EXISTS idx_activity_synced_roles_admin ON activity_synced_roles(guild_id, is_admin)",
            """
            CREATE TABLE IF NOT EXISTS activity_access_roles (
                id BIGSERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                slug TEXT NOT NULL,
                name TEXT NOT NULL,
                is_builtin BIGINT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(guild_id, slug),
                UNIQUE(guild_id, name)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_activity_access_roles_guild ON activity_access_roles(guild_id)",
            """
            CREATE TABLE IF NOT EXISTS activity_access_role_modules (
                id BIGSERIAL PRIMARY KEY,
                access_role_id BIGINT NOT NULL REFERENCES activity_access_roles(id) ON DELETE CASCADE,
                module_key TEXT NOT NULL,
                permission TEXT NOT NULL,
                UNIQUE(access_role_id, module_key)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_activity_access_role_modules_role ON activity_access_role_modules(access_role_id)",
            """
            CREATE TABLE IF NOT EXISTS activity_synced_role_assignments (
                id BIGSERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                discord_role_id BIGINT NOT NULL,
                access_role_id BIGINT NOT NULL REFERENCES activity_access_roles(id) ON DELETE CASCADE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(guild_id, discord_role_id, access_role_id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_activity_synced_role_assignments_guild_role ON activity_synced_role_assignments(guild_id, discord_role_id)",
            """
            CREATE TABLE IF NOT EXISTS dev_blog_posts (
                id BIGSERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                message_id BIGINT,
                author_id BIGINT NOT NULL,
                title TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'published',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_dev_blog_posts_guild ON dev_blog_posts(guild_id)",
            "CREATE INDEX IF NOT EXISTS idx_dev_blog_posts_author ON dev_blog_posts(author_id)",
            """
            CREATE TABLE IF NOT EXISTS creator_alert_subscriptions (
                id BIGSERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                platform TEXT NOT NULL CHECK(platform IN ('twitch', 'youtube', 'kick')),
                channel_url TEXT NOT NULL,
                channel_name TEXT,
                external_channel_id TEXT,
                alert_kind TEXT NOT NULL DEFAULT 'stream',
                title_template TEXT NOT NULL,
                description_template TEXT NOT NULL,
                button_label TEXT NOT NULL DEFAULT 'Watch',
                color BIGINT NOT NULL DEFAULT 5793266,
                ping_role_id BIGINT,
                active BIGINT DEFAULT 1,
                last_event_id TEXT,
                last_checked_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(guild_id, user_id, platform, channel_url, alert_kind)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_creator_alerts_guild ON creator_alert_subscriptions(guild_id)",
            "CREATE INDEX IF NOT EXISTS idx_creator_alerts_user ON creator_alert_subscriptions(guild_id, user_id)",
            "CREATE INDEX IF NOT EXISTS idx_creator_alerts_active ON creator_alert_subscriptions(active)",
        )
