class Maybe:
    """A simple Maybe monad."""

    def __init__(self, value):
        self._value = value

    def map(self, func):
        if self._value is None:
            return self
        return Maybe(func(self._value))

    def flat_map(self, func):
        if self._value is None:
            return self
        return func(self._value)

    def get(self):
        return self._value

    def is_empty(self):
        return self._value is None

    def __bool__(self):
        return not self.is_empty()

    def __repr__(self):
        return f'Maybe({self._value})'
