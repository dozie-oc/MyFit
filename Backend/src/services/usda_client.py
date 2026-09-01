from typing import Any

import httpx

from src.config import Settings


class USDAAPIError(Exception):
    """
    Raised when USDA FoodData Central cannot successfully fulfill
    an API request.

    The service layer/router can translate this into an appropriate
    HTTP/application error without exposing USDA implementation
    details to the client.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
    ):
        super().__init__(message)

        self.message = message
        self.status_code = status_code


class USDAClient:
    """
    Asynchronous client for USDA FoodData Central.

    Responsibilities are intentionally limited to external API
    communication.

    This class does NOT:
        - create database records
        - calculate nutrition
        - manipulate SQLModel objects
        - decide which foods should be stored
        - contain application-specific meal logic

    Those responsibilities belong to FoodService and the routers.

    The client can be used as:

        async with USDAClient(settings) as client:
            result = await client.search_foods("banana")

    The reusable httpx client remains open for the duration of that
    context, allowing connection reuse between multiple USDA calls.
    """

    def __init__(
        self,
        settings: Settings,
    ):
        self.base_url = settings.usda_base_url.rstrip("/")
        self.api_key = settings.usda_api_key

        self.timeout = httpx.Timeout(
            settings.usda_timeout_seconds,
        )

        self._client: httpx.AsyncClient | None = None

    # ============================================================
    # CLIENT LIFECYCLE
    # ============================================================

    async def __aenter__(self) -> "USDAClient":
        """
        Open the underlying HTTP client.

        The client is created lazily rather than during __init__
        because httpx.AsyncClient should be created and closed
        within an appropriate async lifecycle.
        """

        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "Accept": "application/json",
                },
            )

        return self

    async def __aexit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        """
        Close the underlying HTTP client and release connections.
        """

        await self.close()

    async def close(self) -> None:
        """
        Explicitly close the HTTP client.

        This makes the class usable both with an async context
        manager and with an externally managed lifecycle.
        """

        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ============================================================
    # HTTP REQUEST
    # ============================================================

    async def _get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Execute a GET request against FoodData Central.

        Authentication is added centrally so individual API
        methods do not need to repeat it.

        The client must be opened before use.
        """

        if self._client is None:
            raise RuntimeError(
                "USDAClient must be opened before making requests. "
                "Use 'async with USDAClient(...)' or call __aenter__()."
            )

        request_params: dict[str, Any] = {
            "api_key": self.api_key,
        }

        if params:
            request_params.update(params)

        url = (
            f"{self.base_url}/"
            f"{endpoint.lstrip('/')}"
        )

        try:
            response = await self._client.get(
                url,
                params=request_params,
            )

        except httpx.TimeoutException as exc:
            raise USDAAPIError(
                "USDA FoodData Central request timed out."
            ) from exc

        except httpx.RequestError as exc:
            raise USDAAPIError(
                "Unable to connect to USDA FoodData Central."
            ) from exc

        # ========================================================
        # HTTP ERROR HANDLING
        # ========================================================

        if response.status_code == 401:
            raise USDAAPIError(
                "USDA FoodData Central authentication failed.",
                status_code=401,
            )

        if response.status_code == 403:
            raise USDAAPIError(
                "USDA FoodData Central access was denied.",
                status_code=403,
            )

        if response.status_code == 404:
            raise USDAAPIError(
                "USDA resource was not found.",
                status_code=404,
            )

        if response.status_code == 429:
            raise USDAAPIError(
                "USDA FoodData Central rate limit exceeded.",
                status_code=429,
            )

        if response.status_code >= 500:
            raise USDAAPIError(
                "USDA FoodData Central is currently unavailable.",
                status_code=response.status_code,
            )

        if response.status_code >= 400:
            raise USDAAPIError(
                "USDA FoodData Central returned an error.",
                status_code=response.status_code,
            )

        # ========================================================
        # RESPONSE VALIDATION
        # ========================================================

        try:
            data = response.json()

        except ValueError as exc:
            raise USDAAPIError(
                "USDA returned an invalid JSON response."
            ) from exc

        # The endpoints used by this application return JSON
        # objects. Validate that assumption before passing the
        # response to FoodService.
        if not isinstance(data, dict):
            raise USDAAPIError(
                "USDA returned an unexpected response format."
            )

        return data

    # ============================================================
    # FOOD SEARCH
    # ============================================================

    async def search_foods(
        self,
        query: str,
        *,
        page_size: int = 25,
        page_number: int = 1,
        data_types: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Search USDA FoodData Central.

        Pagination and data-type filtering are passed directly to
        USDA. Interpretation of the response belongs to
        FoodService.

        Example:

            await client.search_foods(
                "banana",
                page_size=25,
                page_number=1,
                data_types=["Foundation", "SR Legacy"],
            )
        """

        if not query.strip():
            raise ValueError(
                "Food search query cannot be empty."
            )

        if page_size < 1 or page_size > 200:
            raise ValueError(
                "page_size must be between 1 and 200."
            )

        if page_number < 1:
            raise ValueError(
                "page_number must be greater than zero."
            )

        params: dict[str, Any] = {
            "query": query.strip(),
            "pageSize": page_size,
            "pageNumber": page_number,
        }

        if data_types:
            params["dataType"] = data_types

        return await self._get(
            "/foods/search",
            params=params,
        )

    # ============================================================
    # FOOD DETAILS
    # ============================================================

    async def get_food(
        self,
        fdc_id: int,
    ) -> dict[str, Any]:
        """
        Retrieve complete USDA FoodData Central details for a food.

        The raw USDA response is returned to FoodService, where it
        is normalized into our FoodItem and FoodPortion models.
        """

        if fdc_id <= 0:
            raise ValueError(
                "fdc_id must be greater than zero."
            )

        return await self._get(
            f"/food/{fdc_id}",
        )