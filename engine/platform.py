"""The one place that knows which platform this engine is for."""
import re

NAME = "YouTube"
SITE = "youtube.com"
_POST_RX = re.compile(r"(?:v=|youtu\.be/|/shorts/)([A-Za-z0-9_-]{11})")


def profile_url(handle_or_id):
    return "https://www.youtube.com/channel/%s" % handle_or_id if handle_or_id.startswith("UC") and len(handle_or_id) == 24 else "https://www.youtube.com/@%s" % handle_or_id


def post_url(video_id):
    return "https://www.youtube.com/watch?v=%s" % video_id


def post_id(url):
    m = _POST_RX.search(url or "")
    return m.group(1) if m else None
