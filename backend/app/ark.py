import networkx as nx
import httpx
import asyncio
from typing import List, Dict, Any, Optional

OT_API_URL = "https://api.platform.opentargets.org/api/v4/graphql"


class OpenTargetsClient:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)

    async def search_entity(self, query_str: str) -> Optional[Dict[str, str]]:
        """
        Searches for a Target or Disease and returns the top hit.
        """
        query = """
        query Search($queryString: String!) {
          search(queryString: $queryString, entityNames: ["target", "disease"], page: {index: 0, size: 1}) {
            hits {
              id
              name
              entity
            }
          }
        }
        """
        try:
            resp = await self.client.post(
                OT_API_URL,
                json={"query": query, "variables": {"queryString": query_str}},
            )
            data = resp.json()
            hits = data.get("data", {}).get("search", {}).get("hits", [])
            if hits:
                return hits[0]
            return None
        except Exception as e:
            print(f"OT Search Error: {e}")
            return None

    async def get_target_associations(self, ensembl_id: str) -> List[Dict]:
        """
        Get diseases associated with a target.
        """
        query = """
        query TargetAssociations($ensemblId: String!) {
          target(ensemblId: $ensemblId) {
            id
            approvedSymbol
            associatedDiseases(page: {size: 10}) {
              rows {
                disease {
                  id
                  name
                }
                score
              }
            }
          }
        }
        """
        try:
            resp = await self.client.post(
                OT_API_URL,
                json={"query": query, "variables": {"ensemblId": ensembl_id}},
            )
            data = resp.json()
            rows = (
                data.get("data", {})
                .get("target", {})
                .get("associatedDiseases", {})
                .get("rows", [])
            )
            return [
                {
                    "id": r["disease"][
                        "name"
                    ],  # Use name as ID for visualization simplicity
                    "type": "Disease",
                    "score": r["score"],
                }
                for r in rows
            ]
        except Exception as e:
            print(f"OT Target Assoc Error: {e}")
            return []

    async def get_disease_associations(self, efo_id: str) -> List[Dict]:
        """
        Get targets associated with a disease.
        """
        query = """
        query DiseaseAssociations($efoId: String!) {
          disease(efoId: $efoId) {
            id
            name
            associatedTargets(page: {size: 10}) {
              rows {
                target {
                  id
                  approvedSymbol
                }
                score
              }
            }
          }
        }
        """
        try:
            resp = await self.client.post(
                OT_API_URL, json={"query": query, "variables": {"efoId": efo_id}}
            )
            data = resp.json()
            rows = (
                data.get("data", {})
                .get("disease", {})
                .get("associatedTargets", {})
                .get("rows", [])
            )
            return [
                {
                    "id": r["target"]["approvedSymbol"],
                    "type": "Gene",
                    "score": r["score"],
                }
                for r in rows
            ]
        except Exception as e:
            print(f"OT Disease Assoc Error: {e}")
            return []


class OncoGraph:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.ot_client = OpenTargetsClient()

    async def build_from_query(self, query_text: str):
        """
        Dynamically builds the graph based on the user's query.
        """
        self.graph.clear()

        # 1. Identify the primary entity from the query
        # We assume the query contains a gene or disease name.
        # Simple extraction heuristic: search the whole string
        seed_entity = await self.ot_client.search_entity(query_text)

        if not seed_entity:
            # Fallback to mock data if OT fails or returns nothing
            self.load_mock_data()
            return

        seed_id = seed_entity["id"]
        seed_name = seed_entity["name"]
        seed_type = "Gene" if seed_entity["entity"] == "target" else "Disease"

        self.graph.add_node(seed_name, type=seed_type)

        # 2. Fetch Neighbors (Associations)
        neighbors = []
        if seed_type == "Gene":
            neighbors = await self.ot_client.get_target_associations(seed_id)
        else:
            neighbors = await self.ot_client.get_disease_associations(seed_id)

        # 3. Add to Graph
        for n in neighbors:
            self.graph.add_node(n["id"], type=n["type"])
            self.graph.add_edge(
                seed_name, n["id"], weight=n["score"], relation="associated_with"
            )

            # Optional: Fetch 2nd hop? (Maybe too slow for prototype)

    def load_mock_data(self):
        # ... (Keep existing mock data as fallback)
        genes = ["KRAS", "EGFR", "TP53", "STK11", "YAP1"]
        diseases = ["Lung Adenocarcinoma", "Melanoma"]
        for g in genes:
            self.graph.add_node(g, type="Gene")
        for d in diseases:
            self.graph.add_node(d, type="Disease")
        self.graph.add_edge(
            "KRAS", "Lung Adenocarcinoma", relation="driver", weight=0.9
        )
        self.graph.add_edge(
            "STK11", "Lung Adenocarcinoma", relation="driver", weight=0.8
        )

    def get_subgraph_data(self):
        """
        Returns JSON-serializable graph data with layout.
        """
        if self.graph.number_of_nodes() == 0:
            return {"nodes": [], "links": []}

        pos = nx.spring_layout(self.graph, seed=42)
        data = nx.node_link_data(self.graph)

        # Ensure 'links' key exists for Pydantic compatibility
        if "links" not in data:
            data["links"] = []

        for node in data["nodes"]:
            node_id = node["id"]
            if node_id in pos:
                node["x"] = float(pos[node_id][0]) * 350 + 400
                node["y"] = float(pos[node_id][1]) * 250 + 300
        return data
