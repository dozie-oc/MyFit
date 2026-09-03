from typing import Any

import httpx

from src.config import Settings


class USDAAPIError(Exception):
    """
    Raised when USDA FoodData Central cannot successfully fulfill
    an API request.
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
    """

    def __init__(
        self,
        settings: Settings,
    ):
        self.base_url = settings.usda_base_url.rstrip("/")
        self.api_key = settings.usda_api_key.strip()
        self.timeout = httpx.Timeout(
            settings.usda_timeout_seconds,
        )
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "USDAClient":
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
        await self.close()

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError(
                "USDAClient must be opened before making requests."
            )

        request_params: dict[str, Any] = {
            "api_key": self.api_key,
        }
        if params:
            request_params.update(params)

        url = f"{self.base_url}/{endpoint.lstrip('/')}"

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

        if response.status_code >= 400:
            try:
                error_data = response.json()
            except ValueError:
                error_data = response.text

            raise USDAAPIError(
                (
                    "USDA FoodData Central request failed. "
                    f"Status: {response.status_code}. "
                    f"Response: {error_data}"
                ),
                status_code=response.status_code,
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise USDAAPIError(
                "USDA returned an invalid JSON response."
            ) from exc

        if not isinstance(data, dict):
            raise USDAAPIError(
                "USDA returned an unexpected response format."
            )

        return data

    async def _post(
        self,
        endpoint: str,
        json_data: dict[str, Any],
    ) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError(
                "USDAClient must be opened before making requests."
            )

        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            response = await self._client.post(
                url,
                params={"api_key": self.api_key},
                json=json_data,
            )
        except httpx.TimeoutException as exc:
            raise USDAAPIError(
                "USDA FoodData Central request timed out."
            ) from exc
        except httpx.RequestError as exc:
            raise USDAAPIError(
                "Unable to connect to USDA FoodData Central."
            ) from exc

        if response.status_code >= 400:
            try:
                error_data = response.json()
            except ValueError:
                error_data = response.text

            raise USDAAPIError(
                (
                    "USDA FoodData Central request failed. "
                    f"Status: {response.status_code}. "
                    f"Response: {error_data}"
                ),
                status_code=response.status_code,
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise USDAAPIError(
                "USDA returned an invalid JSON response."
            ) from exc

        if not isinstance(data, dict):
            raise USDAAPIError(
                "USDA returned an unexpected response format."
            )

        return data

    async def search_foods(
        self,
        query: str,
        *,
        page_size: int = 25,
        page_number: int = 1,
        data_types: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Search USDA FoodData Central using POST /foods/search.
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

        payload: dict[str, Any] = {
            "query": query.strip(),
            "pageSize": page_size,
            "pageNumber": page_number,
        }

        if data_types:
            payload["dataType"] = data_types

        return await self._post(
            "/foods/search",
            json_data=payload,
        )

    async def get_food(
        self,
        fdc_id: int,
    ) -> dict[str, Any]:
        """
        Retrieve complete USDA FoodData Central details for a food.
        """
        if fdc_id <= 0:
            raise ValueError(
                "fdc_id must be greater than zero."
            )

        return await self._get(
            f"/food/{fdc_id}",
        )