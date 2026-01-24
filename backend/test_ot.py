import httpx
import asyncio

query = """
query Search($queryString: String!) {
  search(queryString: $queryString, entityNames: ["target", "disease"], page: {index: 0, size: 5}) {
    hits {
      id
      name
      entity
    }
  }
}
"""


async def test_ot():
    async with httpx.AsyncClient() as client:
        # 1. Search for an entity (e.g. "KRAS")
        resp = await client.post(
            "https://api.platform.opentargets.org/api/v4/graphql",
            json={"query": query, "variables": {"queryString": "KRAS"}},
        )
        print("Search Results:", resp.json())


if __name__ == "__main__":
    asyncio.run(test_ot())
