class ShopTokenStore:
    """Holds the Admin API access token for every shop that installed us.

    Provided, and deliberately in memory: the tokens are gone when the process
    restarts. A real deployment stores them encrypted, in a database, which is
    one of the things worth writing about in your notes rather than building
    here.
    """

    def __init__(self) -> None:
        self._tokens: dict[str, str] = {}

    def save(self, shop_domain: str, access_token: str) -> None:
        self._tokens[shop_domain] = access_token

    def get(self, shop_domain: str) -> str | None:
        return self._tokens.get(shop_domain)

    def forget(self, shop_domain: str) -> None:
        self._tokens.pop(shop_domain, None)

    @property
    def installed_shops(self) -> list[str]:
        return sorted(self._tokens)


shop_token_store = ShopTokenStore()
