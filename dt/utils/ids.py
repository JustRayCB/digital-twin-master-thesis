import uuid


def new_correlation_id() -> str:
    """Generate a new correlation ID.

    A correlation ID is a unique identifier used to trace and correlate events
    or requests across different systems or components. In this system, it is
    used to trace the lifecycle of an event from sensor readings to alerts,
    actions, and auditing.

    Returns
    -------
    str
        A new, unique correlation ID as a string.

    Examples
    --------
    >>> correlation_id = new_correlation_id()
    >>> print(correlation_id)
    'a1b2c3d4-e5f6-7890-1234-567890abcdef'
    """
    return str(uuid.uuid4())
