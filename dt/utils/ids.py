import uuid


def new_correlation_id() -> str:
    """Generate a new correlation ID.
    A correlation ID is a unique identifier used to trace and correlate events or requests across different systems or components.
    In our case it will trace  from the readings -> alerts -> actions -> audit.

    Returns
    -------
    str
        A new correlation ID.

    """
    return str(uuid.uuid4())
