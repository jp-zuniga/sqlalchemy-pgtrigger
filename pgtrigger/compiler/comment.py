"""
The marker written onto every installed trigger.

Autogenerate has no migration state to diff against, so each trigger carries a
fingerprint of its own definition. Reading it back is how a changed declaration,
or a trigger somebody edited by hand, shows up as a difference.
"""

from pgtrigger.consts import COMMENT_PREFIX, TEMPLATE_VERSION

########################################################################################


def format_comment(fingerprint: str) -> str:
    """
    Build the comment written onto an installed trigger.

    Returns:
        str: A `pgtrigger:<version>:<fingerprint>` marker.

    """

    return f"{COMMENT_PREFIX}:{TEMPLATE_VERSION}:{fingerprint}"


########################################################################################


def parse_comment(comment: str | None) -> tuple[int, str] | None:
    """
    Read the version and fingerprint back out of a trigger's comment.

    Anything we did not write, including a comment replaced by hand, reads as
    unrecognised rather than as a mismatch, so nothing is overwritten on the
    strength of a bad parse.

    Returns:
        tuple[int, str] | None: The template version and fingerprint,
                                or `None` if the comment is missing or not ours.

    """

    if not comment:
        return None

    prefix, _, remainder = comment.partition(":")

    if prefix != COMMENT_PREFIX:
        return None

    version, _, fingerprint = remainder.partition(":")

    if not fingerprint or not version.isdigit():
        return None

    return int(version), fingerprint
