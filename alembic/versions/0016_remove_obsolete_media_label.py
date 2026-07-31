"""merge the obsolete visual scam label into SCAM

Revision ID: 0016_remove_obsolete_media_label
Revises: 0015_ai_enforcement_metrics
"""

from alembic import op

revision = "0016_remove_obsolete_media_label"
down_revision = "0015_ai_enforcement_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    obsolete_label = "IMAGE_" + "SCAM"
    op.execute(
        f"""
        UPDATE ai_moderation_settings
        SET policy_json = jsonb_set(
            policy_json #- ARRAY['labels', '{obsolete_label}'],
            '{{labels,SCAM}}',
            COALESCE(
                policy_json#>'{{labels,SCAM}}',
                policy_json#>ARRAY['labels', '{obsolete_label}']
            ),
            true
        )
        WHERE policy_json#>ARRAY['labels', '{obsolete_label}'] IS NOT NULL
        """
    )
    _replace_label_array("ai_moderation_events", "labels_json", obsolete_label)
    _replace_label_array("ai_moderation_review_items", "labels_json", obsolete_label)
    op.execute(
        "UPDATE ai_moderation_events SET primary_label = 'SCAM' WHERE primary_label = "
        f"'{obsolete_label}'"
    )


def downgrade() -> None:
    # The removed value has been merged into SCAM and cannot be reconstructed
    # without inventing provenance that old rows did not retain.
    return None


def _replace_label_array(table_name: str, column_name: str, obsolete_label: str) -> None:
    op.execute(
        f"""
        UPDATE {table_name}
        SET {column_name} = (
            SELECT jsonb_agg(label ORDER BY label)
            FROM (
                SELECT DISTINCT CASE
                    WHEN value = '{obsolete_label}' THEN 'SCAM'
                    ELSE value
                END AS label
                FROM jsonb_array_elements_text({column_name})
            ) AS normalized
        )
        WHERE {column_name} @> jsonb_build_array('{obsolete_label}')
        """
    )
