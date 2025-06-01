SERVICES_URL = [
    "/services/v1/economy/fiscal",
    "/services/v1/economy/macro",
    "/services/v1/economy/monetary",
    "/services/v1/finance/crypto",
    "/services/v1/finance/downtrend",
    "/services/v1/finance/sector",
    "/services/v1/finance/stocks",
    "/services/v1/finance/volume",
]
SOURCE_SERVICES_URL = "/services/v1/ingestion/collect"
SOURCE_SERVICES_TARGET = [
        "/services/v1/economy/fiscal",
        "/services/v1/economy/macro",
        "/services/v1/economy/monetary",
        "/services/v1/finance/crypto",
        "/services/v1/finance/downtrend",
        "/services/v1/finance/sector",
        "/services/v1/finance/stocks",
        "/services/v1/finance/volume",
    ]
SOURCE_SERVICES_CLEAN = {
    "/services/v1/finance/volume": {
        "type": "list_of_dicts",
        "keys_to_remove": ["symbol"]
    },
    "/services/v1/finance/stocks": {
        "type": "list_of_dicts",
        "keys_to_remove": ["type", "symbol", "exchangeShortName"]
    },
    "/services/v1/finance/downtrend": {
        "type": "list_of_dicts",
        "keys_to_remove": ["symbol"]
    },
    "/services/v1/finance/crypto": {
        "type": "list_of_dicts",
        "keys_to_remove": ["symbol", "stockExchange", "exchangeShortName"]
    },
    "/services/v1/economy/monetary": {
        "type": "dict_with_feed",
        "feed_keys_to_remove": ["url", "source", "author", "authors", "banner_image", "source_domain"]
    },
    "/services/v1/economy/fiscal": {
        "type": "dict_with_feed",
        "feed_keys_to_remove": ["url", "source", "author", "authors", "banner_image", "source_domain"]
    },
    "/services/v1/economy/macro": {
        "type": "dict_with_feed",
        "feed_keys_to_remove": ["url", "source", "author", "authors", "banner_image", "source_domain"]
    },
}
SERVICES_TRANSFORMATION_PATH = "/services/v1/cleaning/collect"
SERVICES_VISUALIZATION_PATH = "/services/v1/transformation/collect"
