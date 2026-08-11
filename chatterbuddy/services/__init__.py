"""Services own every conversation with the outside world: the filesystem, the
network, and the clock. Nothing above this layer imports ``requests`` or
touches a file path."""
