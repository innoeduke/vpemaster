
class SessionTypeID:
    """
    Constants for SessionType IDs to avoid hardcoding in the codebase.
    These IDs must match the seed data in scripts/metadata_dump.json.
    """
    TABLE_TOPICS = 7
    KEYNOTE_SPEECH = 20
    PREPARED_SPEECH = 30
    EVALUATION = 31
    TOPICS_SPEECH = 36
    PRESENTATION = 43
    PANEL_DISCUSSION = 44


class ProjectID:
    """
    Constants for Project IDs to avoid hardcoding.
    """
    GENERIC = 60
    TOPICSMASTER_PROJECT = 10
    KEYNOTE_SPEAKER_PROJECT = 51
    MODERATOR_PROJECT = 57
    EVALUATION_PROJECTS = [4, 5, 6]


# Common groupings of SessionType IDs
SPEECH_TYPES_WITH_PROJECT = {
    SessionTypeID.TABLE_TOPICS,
    SessionTypeID.KEYNOTE_SPEECH,
    SessionTypeID.PREPARED_SPEECH,
    SessionTypeID.PANEL_DISCUSSION,
    SessionTypeID.PRESENTATION
}

class RoleID:
    TOPICS_SPEAKER = 9
    KEYNOTE_SPEAKER = 10
    PANEL_MODERATOR = 17
    INDIVIDUAL_EVALUATOR = 3
