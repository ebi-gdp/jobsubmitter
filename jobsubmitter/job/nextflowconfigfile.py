""" A representation of a simple nextflow config file, using simple key-value notation e.g.:

     process.executor='k8s'
     k8s.serviceaccount='default'

     Scopes aren't implemented (i.e. no curly brackets!).

     Represented as a string for easy storage in ConfigMaps datafields.
"""


class NextflowConfigFile:
    """ A nextflow configuration file that uses simple key='value' notation, one key per line"""

    def __init__(self, data=''):
        assert isinstance(data, str), "Data must be a string"
        self.data = data

    @classmethod
    def from_dict(cls, d: dict[str, str]):
        l: list[list[str]] = [[k, '=', v] for k, v in d.items()]
        params: str = '\n'.join([''.join(x) for x in l])
        return cls(params)

    def update(self, params: dict[str, str]):
        """ Update data with a dictionary """
        return self.from_dict(self.to_dict() | params)

    def to_dict(self) -> dict[str, str]:
        params: list[list[str]] = [x.split('=') for x in self.data.strip().split("\n")]
        return {k[0]: k[1] for k in params}

