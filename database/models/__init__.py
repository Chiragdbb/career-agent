from .base import Base

# Import side-effect models so Base.metadata is populated when using
# `import database.models`.
from . import schema  # noqa: F401
