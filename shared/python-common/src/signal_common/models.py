from enum import Enum


class ArtistStatus(str, Enum):
    TRACKED = "TRACKED"
    FOLLOWING = "FOLLOWING"
    PUBLISHED = "PUBLISHED"
    BLACKLISTED = "BLACKLISTED"
